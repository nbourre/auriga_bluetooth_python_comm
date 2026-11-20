"""BLE connection with no dependency on any GUI toolkit.

`BleConnection` manages the asyncio thread, scanning, connecting, notifications
and writing. It talks to the rest of the application through signals (`Signal`)
that any UI (Tk, pygame, CLI) can subscribe to.

Signals are emitted from the asyncio thread (or the calling thread): it is up to
the subscriber to hop back to its own thread when needed.
"""
import asyncio
import json
import os
import sys
import threading
import traceback
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Union

from bleak import BleakClient, BleakScanner

CHARACTERISTIC_NOTIFY_UUID = "0000ffe2-0000-1000-8000-00805f9b34fb"  # notifications
CHARACTERISTIC_WRITE_UUID = "0000ffe3-0000-1000-8000-00805f9b34fb"   # write
DEVICE_FILE = "last_connected_device.json"

END_DATA_OPTIONS = {
    'NL': b'\n',      # New line (0x0A)
    'CR': b'\r',      # Carriage return (0x0D)
    'BOTH': b'\r\n',  # CR + NL
    'NONE': b'',      # No trailing data
}

PayloadType = Union[str, int, List[int]]


def to_bytes(payload: PayloadType) -> bytes:
    """Convert a configured payload (str, int or list of ints) to bytes."""
    if isinstance(payload, str):
        return payload.encode('utf-8')
    if isinstance(payload, int):
        return bytes([payload & 0xFF])
    if isinstance(payload, list):
        return bytes([int(x) & 0xFF for x in payload])
    raise TypeError(f"Unsupported payload type: {type(payload)}")


APP_DIR_NAME = "auriga_ble"
HISTORY_FILE_NAME = "message_history.json"


def user_data_dir(app_name: str = APP_DIR_NAME) -> str:
    """Per-user directory for application data, following each platform's convention.

    Windows: %LOCALAPPDATA%\\<app>   macOS: ~/Library/Application Support/<app>
    Linux/other: $XDG_STATE_HOME/<app> (default ~/.local/state/<app>)
    """
    home = os.path.expanduser("~")
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or home
    elif sys.platform == "darwin":
        base = os.path.join(home, "Library", "Application Support")
    else:
        base = os.environ.get("XDG_STATE_HOME") or os.path.join(home, ".local", "state")
    return os.path.join(base, app_name)


def default_history_path() -> str:
    return os.path.join(user_data_dir(), HISTORY_FILE_NAME)


def load_history(path: str) -> List[str]:
    """Read a list of sent messages from `path` (empty list if missing or corrupt)."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [m for m in data if isinstance(m, str)] if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save_history(path: str, history: List[str]) -> None:
    """Write the history to `path`, creating the directory if needed. Errors are ignored."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False)
    except OSError:
        pass


def load_last_device() -> Optional[str]:
    try:
        if not os.path.exists(DEVICE_FILE):
            return None
        with open(DEVICE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f).get("device_name") or None
    except (OSError, ValueError):
        return None


def save_last_device(device_name: str) -> None:
    try:
        with open(DEVICE_FILE, 'w', encoding='utf-8') as f:
            json.dump({"device_name": device_name}, f)
    except OSError:
        pass


class Signal:
    """Minimal event system: `connect(fn)` to subscribe, `emit(*args)` to notify."""

    def __init__(self) -> None:
        self._subscribers: List[Callable[..., None]] = []

    def connect(self, fn: Callable[..., None]) -> None:
        self._subscribers.append(fn)

    def emit(self, *args: Any) -> None:
        for fn in list(self._subscribers):
            try:
                fn(*args)
            except Exception:
                traceback.print_exc()  # a faulty subscriber must not break the others


@dataclass(frozen=True)
class DiscoveredDevice:
    name: str
    address: str

    @property
    def display(self) -> str:
        return f"{self.name} ({self.address})"


class BleConnection:
    """BLE client running in a dedicated asyncio thread.

    Signals:
      log(text)              message to show to the user
      rx(chunk)              raw text received through notifications
      status(text)           "Connected to X", "Disconnected", ...
      devices_found(list)    list of DiscoveredDevice after a scan
      scanning(bool)         scan started / finished
      connecting(bool)       connection attempt started / finished
      disconnecting(bool)    disconnection started / finished
    """

    def __init__(self) -> None:
        self.log = Signal()
        self.rx = Signal()
        self.status = Signal()
        self.devices_found = Signal()
        self.scanning = Signal()
        self.connecting = Signal()
        self.disconnecting = Signal()

        # Transformation applied to every payload before writing (e.g. prepending a header)
        self.payload_wrapper: Callable[[bytes], bytes] = lambda payload: payload

        self.client: Optional[BleakClient] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._loop_ready = threading.Event()
        self._start_loop_thread()

    # -----------------------------
    # Asyncio loop
    # -----------------------------
    def _start_loop_thread(self) -> None:
        def run() -> None:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self._loop_ready.set()
            self.loop.run_forever()

        self._loop_thread = threading.Thread(target=run, daemon=True)
        self._loop_thread.start()
        self._loop_ready.wait(timeout=2.0)

    def run(self, coro):
        """Schedule a coroutine on the BLE loop. Returns a Future, or None if the loop is stopped."""
        if self.loop and self.loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, self.loop)
        coro.close()
        return None

    @property
    def is_connected(self) -> bool:
        return bool(self.client and self.client.is_connected)

    # -----------------------------
    # Scan
    # -----------------------------
    def scan(self, timeout: float = 10.0) -> None:
        self.scanning.emit(True)
        if not self.run(self._scan(timeout)):
            self.scanning.emit(False)

    async def _scan(self, timeout: float) -> None:
        try:
            self.log.emit(f"Scanning for devices for {timeout:.0f} seconds...\n")
            found = await BleakScanner.discover(timeout=timeout)
            devices = sorted((DiscoveredDevice(d.name, d.address) for d in found if d.name),
                             key=lambda d: d.name.lower())
            self.devices_found.emit(devices)
            self.log.emit(f"Found {len(devices)} device(s).\n" if devices else "No devices found.\n")
        except Exception as e:
            self.log.emit(f"Scan error: {e}\n")
        finally:
            self.scanning.emit(False)

    # -----------------------------
    # Connection
    # -----------------------------
    def connect(self, device_name: str, address: Optional[str] = None) -> None:
        self.connecting.emit(True)
        if not self.run(self._connect(device_name, address)):
            self.connecting.emit(False)

    async def _connect(self, device_name: str, address: Optional[str]) -> None:
        try:
            if not address:
                address = await self._find_address(device_name)
            if not address:
                self.log.emit(f"Device '{device_name}' not found.\n")
                return

            if self.is_connected:
                await self.client.disconnect()

            self.client = BleakClient(address)
            await self.client.connect()

            if self.client.is_connected:
                self.log.emit(f"Connected to {device_name} ({address}).\n")
                self.status.emit(f"Connected to {device_name}")
                save_last_device(device_name)
                await self._start_notifications()
            else:
                self.log.emit(f"Failed to connect to {device_name}.\n")
                self.status.emit("Connection failed")
        except Exception as e:
            self.log.emit(f"Failed to connect to {device_name}: {e}\n")
            self.status.emit("Connection error")
        finally:
            self.connecting.emit(False)

    @staticmethod
    async def _find_address(device_name: str) -> Optional[str]:
        for d in await BleakScanner.discover(timeout=6.0):
            if d.name == device_name:
                return d.address
        return None

    async def _start_notifications(self) -> None:
        def handler(sender, data: bytes) -> None:
            self.rx.emit(data.decode('utf-8', errors='replace'))

        try:
            await self.client.start_notify(CHARACTERISTIC_NOTIFY_UUID, handler)
            self.log.emit("Started listening for notifications.\n")
        except Exception as e:
            self.log.emit(f"Failed to start notifications: {e}\n")

    def disconnect(self) -> None:
        self.disconnecting.emit(True)
        if not self.run(self._disconnect()):
            self.disconnecting.emit(False)

    async def _disconnect(self) -> None:
        try:
            if self.is_connected:
                await self.client.disconnect()
                self.log.emit("Disconnected.\n")
                self.status.emit("Disconnected")
            else:
                self.log.emit("No active connection to disconnect.\n")
        except Exception as e:
            self.log.emit(f"Disconnect error: {e}\n")
            self.status.emit("Disconnect error")
        finally:
            self.disconnecting.emit(False)

    # -----------------------------
    # Writing
    # -----------------------------
    def write(self, payload: bytes):
        """Write a payload (after `payload_wrapper`). Returns the Future, or None."""
        return self.run(self._write(payload))

    async def _write(self, payload: bytes) -> None:
        try:
            if self.client:
                await self.client.write_gatt_char(CHARACTERISTIC_WRITE_UUID, self.payload_wrapper(payload))
        except Exception as e:
            self.log.emit(f"Send error: {e}\n")

    # -----------------------------
    # Shutdown
    # -----------------------------
    def shutdown(self) -> None:
        try:
            if self.is_connected:
                fut = self.run(self.client.disconnect())
                if fut:
                    fut.result(timeout=2.0)
        except Exception as e:
            print(f"Error during disconnect: {e}")
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=1.0)
