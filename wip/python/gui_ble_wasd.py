import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import time
from bleak import BleakClient, BleakScanner
import asyncio
import threading
from typing import Any, Dict, List, Optional, Union

# -----------------------------
# BLE characteristic UUIDs (adjust if your device differs)
# -----------------------------
CHARACTERISTIC_NOTIFY_UUID = "0000ffe2-0000-1000-8000-00805f9b34fb"  # notifications
CHARACTERISTIC_WRITE_UUID  = "0000ffe3-0000-1000-8000-00805f9b34fb"  # write

# -----------------------------
# App constants
# -----------------------------
DEVICE_FILE = "last_connected_device.json"
ACTIONS_FILE = "actions.json"  # same folder as script

END_DATA_OPTIONS = {
    'NL': b'\n',
    'CR': b'\r',
    'BOTH': b'\r\n',
    'NONE': b''
}

DEFAULT_FREQUENCY_HZ = 10  # default global frequency for WASD
DEFAULT_HEADER = [0xFF, 0x55]  # default header bytes

# -----------------------------
# Helpers to convert configured payloads to bytes
# -----------------------------
PayloadType = Union[str, int, List[int]]

def to_bytes(payload: PayloadType) -> bytes:
    """Convert a payload (string/char/int list) to bytes.
    - str: utf-8 encoded
    - int: single byte (0..255)
    - List[int]: sequence of bytes
    """
    if isinstance(payload, str):
        return payload.encode('utf-8')
    if isinstance(payload, int):
        return bytes([payload & 0xFF])
    if isinstance(payload, list):
        return bytes([int(x) & 0xFF for x in payload])
    raise TypeError(f"Unsupported payload type: {type(payload)}")

# -----------------------------
# Main Application
# -----------------------------
class Application(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("BLE Robot Controller")
        self.geometry("780x560")

        # BLE state
        self.ble_client: Optional[BleakClient] = None
        self.discovered_devices: Dict[str, Dict[str, Any]] = {}

        # Asyncio in a dedicated thread
        self.asyncio_thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.loop_running: bool = False

        self.start_asyncio_thread()

        # Config loaded from actions.json
        self.config_directions: Dict[str, PayloadType] = {}
        self.config_stop: Optional[PayloadType] = None
        self.config_actions: List[Dict[str, Any]] = []
        self.config_header: List[int] = DEFAULT_HEADER.copy()

        # Keyboard control state
        self.keyboard_enabled_var = tk.BooleanVar(value=True)  # checkbox
        self.frequency_var = tk.StringVar(value=str(DEFAULT_FREQUENCY_HZ))
        self.line_endings_var = tk.StringVar(value="BOTH")
        self.use_header_var = tk.BooleanVar(value=False)  # header option

        # Key tracking (avoid autorepeat flood)
        self._pressed_keys: set[str] = set()

        # Direction loop state
        self._current_dir_key: Optional[str] = None   # one of 'w','a','s','d'
        self._dir_payload: Optional[bytes] = None
        self._dir_period_s: float = 1.0 / DEFAULT_FREQUENCY_HZ
        self._dir_thread_stop = threading.Event()
        self._dir_thread = threading.Thread(target=self._direction_sender_loop, daemon=True)
        self._dir_thread.start()

        # Build UI
        self._build_ui()
        self._bind_keys()
        
        # Set initial state of message entry based on keyboard control
        self._on_keyboard_control_changed()

        # Load persisted device + actions.json at startup
        self._load_last_connected_device()
        self._reload_actions_from_disk()

    # -----------------------------
    # Asyncio loop thread
    # -----------------------------
    def start_asyncio_thread(self) -> None:
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop_running = True
            try:
                self.loop.run_forever()
            finally:
                self.loop_running = False
        self.asyncio_thread = threading.Thread(target=run_loop, daemon=True)
        self.asyncio_thread.start()
        time.sleep(0.1)

    def run_in_loop(self, coro):
        if self.loop and self.loop_running:
            return asyncio.run_coroutine_threadsafe(coro, self.loop)
        return None

    # -----------------------------
    # UI
    # -----------------------------
    def _build_ui(self) -> None:
        top = tk.Frame(self)
        top.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)

        # Scan + device dropdown
        scan_row = tk.Frame(top)
        scan_row.pack(side=tk.TOP, fill=tk.X)

        self.scan_button = tk.Button(scan_row, text="Scan Devices", command=self._start_scan_devices)
        self.scan_button.pack(side=tk.LEFT)

        self.selected_device = tk.StringVar()
        self.device_dropdown = ttk.Combobox(scan_row, textvariable=self.selected_device, values=[], state="readonly", width=45)
        self.device_dropdown.pack(side=tk.LEFT, padx=6, fill=tk.X, expand=True)
        self.device_dropdown.bind("<<ComboboxSelected>>", self._on_device_selected)

        # Manual name + connect/disconnect
        conn_row = tk.Frame(top)
        conn_row.pack(side=tk.TOP, fill=tk.X, pady=(6, 0))

        self.device_name_entry = tk.Entry(conn_row)
        self.device_name_entry.insert(0, "Or enter device name manually")
        self.device_name_entry.config(fg="grey")
        self.device_name_entry.bind("<FocusIn>", lambda e: self._entry_focus_in(self.device_name_entry, "Or enter device name manually"))
        self.device_name_entry.bind("<FocusOut>", lambda e: self._entry_focus_out(self.device_name_entry, "Or enter device name manually"))
        self.device_name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.connect_button = tk.Button(conn_row, text="Connect", command=self._start_connect_device)
        self.connect_button.pack(side=tk.LEFT, padx=4)

        self.disconnect_button = tk.Button(conn_row, text="Disconnect", command=self._start_disconnect_device)
        self.disconnect_button.pack(side=tk.LEFT)

        # Status
        status_row = tk.Frame(top)
        status_row.pack(side=tk.TOP, fill=tk.X, pady=(6, 0))
        self.status_label = tk.Label(status_row, text="Status: Disconnected", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Message send row (manual)
        msg_row = tk.Frame(top)
        msg_row.pack(side=tk.TOP, fill=tk.X, pady=(8, 0))

        self.message_entry = tk.Entry(msg_row)
        self.message_entry.insert(0, "Enter your text here")
        self.message_entry.config(fg="grey")
        self.message_entry.bind("<FocusIn>", lambda e: self._entry_focus_in(self.message_entry, "Enter your text here"))
        self.message_entry.bind("<FocusOut>", lambda e: self._entry_focus_out(self.message_entry, "Enter your text here"))
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.line_endings_dropdown = ttk.Combobox(msg_row, textvariable=self.line_endings_var, values=["NL","CR","BOTH","NONE"], width=6, state="readonly")
        self.line_endings_dropdown.pack(side=tk.LEFT, padx=6)

        self.header_checkbox = tk.Checkbutton(msg_row, text="Header", variable=self.use_header_var)
        self.header_checkbox.pack(side=tk.LEFT, padx=6)

        self.send_button = tk.Button(msg_row, text="Send", command=self._send_manual_message)
        self.send_button.pack(side=tk.LEFT)

        # Keyboard control row
        kb_row = tk.Frame(top)
        kb_row.pack(side=tk.TOP, fill=tk.X, pady=(10, 0))

        self.kb_checkbox = tk.Checkbutton(kb_row, text="Enable Keyboard Control (W/A/S/D + action keys)", variable=self.keyboard_enabled_var, command=self._on_keyboard_control_changed)
        self.kb_checkbox.pack(side=tk.LEFT)

        freq_frame = tk.Frame(kb_row)
        freq_frame.pack(side=tk.RIGHT)
        tk.Label(freq_frame, text="Frequency:").pack(side=tk.LEFT)
        self.freq_entry = tk.Entry(freq_frame, width=6, textvariable=self.frequency_var)
        self.freq_entry.pack(side=tk.LEFT)
        tk.Label(freq_frame, text="Hz").pack(side=tk.LEFT, padx=(2,0))

        # Actions panel header
        actions_header = tk.Frame(top)
        actions_header.pack(side=tk.TOP, fill=tk.X, pady=(10, 0))
        tk.Label(actions_header, text="Actions (from actions.json)", font=("TkDefaultFont", 10, "bold")).pack(side=tk.LEFT)
        tk.Button(actions_header, text="Reload Actions", command=self._reload_actions_from_disk).pack(side=tk.RIGHT)

        # Actions panel
        self.actions_panel = tk.Frame(top)
        self.actions_panel.pack(side=tk.TOP, fill=tk.X, pady=(4, 0))

        # Received data box
        self.received_data_text = tk.Text(self, height=14)
        self.received_data_text.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=8)

    def _bind_keys(self) -> None:
        # Bind on the toplevel so it catches regardless of focus, but we respect the checkbox
        self.bind_all("<KeyPress>", self._on_key_press, add=True)
        self.bind_all("<KeyRelease>", self._on_key_release, add=True)
    
    def _on_keyboard_control_changed(self) -> None:
        """Called when the keyboard control checkbox state changes."""
        if self.keyboard_enabled_var.get():
            # Keyboard control enabled - disable text entry
            self.message_entry.config(state="disabled")
        else:
            # Keyboard control disabled - enable text entry
            self.message_entry.config(state="normal")

    # -----------------------------
    # Placeholder helpers
    # -----------------------------
    @staticmethod
    def _entry_focus_in(entry: tk.Entry, placeholder: str) -> None:
        if entry.get() == placeholder and entry.cget('fg') == 'grey':
            entry.delete(0, tk.END)
            entry.config(fg='black')

    @staticmethod
    def _entry_focus_out(entry: tk.Entry, placeholder: str) -> None:
        if entry.get().strip() == "":
            entry.delete(0, tk.END)
            entry.insert(0, placeholder)
            entry.config(fg='grey')

    # -----------------------------
    # Device scanning/connection
    # -----------------------------
    def _start_scan_devices(self) -> None:
        self.scan_button.config(state="disabled", text="Scanning…")
        self.run_in_loop(self._scan_devices())

    async def _scan_devices(self) -> None:
        timeout = 10.0
        try:
            self._append_text(f"Scanning for devices for {timeout} seconds...\n")
            devices = await BleakScanner.discover(timeout=timeout)
            self.discovered_devices.clear()
            names: List[str] = []
            for d in devices:
                if d.name:
                    display = f"{d.name} ({d.address})"
                    self.discovered_devices[display] = {"name": d.name, "address": d.address}
                    names.append(display)
            self.after(0, lambda: self._update_device_dropdown(sorted(names)))
        except Exception as e:
            self._append_text(f"Scan error: {e}\n")
        finally:
            self.after(0, lambda: self.scan_button.config(state="normal", text="Scan Devices"))

    def _update_device_dropdown(self, values: List[str]) -> None:
        self.device_dropdown['values'] = values
        self._append_text(f"Found {len(values)} device(s).\n" if values else "No devices found.\n")

    def _on_device_selected(self, _=None) -> None:
        sel = self.selected_device.get()
        if sel in self.discovered_devices:
            name = self.discovered_devices[sel]['name']
            self.device_name_entry.delete(0, tk.END)
            self.device_name_entry.insert(0, name)
            self.device_name_entry.config(fg='black')

    def _start_connect_device(self) -> None:
        selected = self.selected_device.get()
        manual = self.device_name_entry.get().strip()
        dev_name: Optional[str] = None
        dev_addr: Optional[str] = None
        if selected in self.discovered_devices:
            dev_name = self.discovered_devices[selected]['name']
            dev_addr = self.discovered_devices[selected]['address']
        elif manual and manual.lower() != "or enter device name manually":
            dev_name = manual
        else:
            self._append_text("Please select or enter a device name.\n")
            return
        self.connect_button.config(state="disabled", text="Connecting…")
        self.run_in_loop(self._async_connect(dev_name, dev_addr))

    async def _async_connect(self, device_name: str, address: Optional[str]) -> None:
        try:
            if not address:
                # try to discover by name
                devices = await BleakScanner.discover(timeout=6.0)
                for d in devices:
                    if d.name == device_name:
                        address = d.address
                        break
            if not address:
                self._append_text(f"Device '{device_name}' not found.\n")
                return

            if self.ble_client and self.ble_client.is_connected:
                await self.ble_client.disconnect()

            self.ble_client = BleakClient(address)
            await self.ble_client.connect()

            if self.ble_client.is_connected:
                self._append_text(f"Connected to {device_name} ({address}).\n")
                self.status_label.config(text=f"Status: Connected to {device_name}")
                self._save_last_connected_device(device_name)
                await self._start_notifications()
            else:
                self._append_text("Connection failed.\n")
                self.status_label.config(text="Status: Connection failed")
        except Exception as e:
            self._append_text(f"Connect error: {e}\n")
            self.status_label.config(text="Status: Connection error")
        finally:
            self.connect_button.config(state="normal", text="Connect")

    async def _start_notifications(self) -> None:
        async def handler(sender, data: bytes):
            try:
                decoded = data.decode('utf-8', errors='ignore')
            except Exception:
                decoded = str(data)
            self._append_text(f"Received: {decoded}\n")
        try:
            if self.ble_client:
                await self.ble_client.start_notify(CHARACTERISTIC_NOTIFY_UUID, handler)
                self._append_text("Started listening for notifications.\n")
        except Exception as e:
            self._append_text(f"Failed to start notifications: {e}\n")

    def _start_disconnect_device(self) -> None:
        self.disconnect_button.config(state="disabled", text="Disconnecting…")
        self.run_in_loop(self._async_disconnect())

    async def _async_disconnect(self) -> None:
        try:
            if self.ble_client and self.ble_client.is_connected:
                await self.ble_client.disconnect()
                self._append_text("Disconnected.\n")
                self.status_label.config(text="Status: Disconnected")
            else:
                self._append_text("No active connection to disconnect.\n")
        except Exception as e:
            self._append_text(f"Disconnect error: {e}\n")
            self.status_label.config(text="Status: Disconnect error")
        finally:
            self.disconnect_button.config(state="normal", text="Disconnect")

    # -----------------------------
    # Manual message send
    # -----------------------------
    def _send_manual_message(self) -> None:
        if not (self.ble_client and self.ble_client.is_connected):
            self._append_text("Not connected to any device.\n")
            return
        msg = self.message_entry.get()
        if msg.strip() == "" or msg == "Enter your text here":
            self._append_text("Please enter a message to send.\n")
            return
        end = END_DATA_OPTIONS.get(self.line_endings_var.get(), b'')
        data = msg.encode('utf-8') + end
        use_header = self.use_header_var.get()
        self.run_in_loop(self._async_write(data))
        
        header_info = f" (with header {self.config_header})" if use_header else ""
        self._append_text(f"Sent: {msg}{header_info}\n")
        self.message_entry.delete(0, tk.END)

    async def _async_write(self, payload: bytes, use_header: bool = None) -> None:
        try:
            if self.ble_client:
                # Use parameter if provided, otherwise use GUI checkbox
                add_header = use_header if use_header is not None else self.use_header_var.get()
                
                final_payload = payload
                if add_header and self.config_header:
                    header_bytes = bytes(self.config_header)
                    final_payload = header_bytes + payload
                    
                await self.ble_client.write_gatt_char(CHARACTERISTIC_WRITE_UUID, final_payload)
        except Exception as e:
            self._append_text(f"Send error: {e}\n")

    # -----------------------------
    # Actions loading (JSON)
    # -----------------------------
    def _reload_actions_from_disk(self) -> None:
        path = os.path.join(os.getcwd(), ACTIONS_FILE)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except FileNotFoundError:
            # create a minimal template if missing
            cfg = {
                "header": [255, 85],
                "directions": {"w": "F", "a": "L", "s": "B", "d": "R", "stop": "DIR_STOP"},
                "actions": [
                    {"key": "q", "data": "LIGHT_TOGGLE", "label": "Toggle Light"},
                    {"key": "e", "data": [255, 85], "label": "Special Command"}
                ]
            }
            with open(path, 'w', encoding='utf-8') as wf:
                json.dump(cfg, wf, indent=2)

        # validate + store
        try:
            dirs = cfg.get("directions", {})
            stop = dirs.get("stop")
            if not all(k in dirs for k in ("w","a","s","d")) or stop is None:
                raise ValueError("'directions' must define w,a,s,d and stop")
            self.config_directions = {k: dirs[k] for k in ("w","a","s","d")}
            self.config_stop = stop

            # Load header configuration
            header_cfg = cfg.get("header", DEFAULT_HEADER)
            if isinstance(header_cfg, list) and all(isinstance(x, int) for x in header_cfg):
                self.config_header = header_cfg
            else:
                self.config_header = DEFAULT_HEADER.copy()

            actions_raw = cfg.get("actions", [])
            self.config_actions = []
            for item in actions_raw:
                key = str(item.get("key", "")).lower()
                if not key:
                    continue
                self.config_actions.append({
                    "key": key,
                    "data": item.get("data"),
                    "label": item.get("label", key.upper())
                })
            self._rebuild_actions_panel()
            header_hex = ' '.join(f'0x{b:02X}' for b in self.config_header)
            self._append_text(f"Actions loaded. Header configured: [{header_hex}]\n")
        except Exception as e:
            messagebox.showerror("actions.json error", str(e))

    def _rebuild_actions_panel(self) -> None:
        for w in self.actions_panel.winfo_children():
            w.destroy()
        if not self.config_actions:
            tk.Label(self.actions_panel, text="No actions configured.").pack(anchor=tk.W)
            return
        # Create buttons in a grid
        columns = 3
        for idx, act in enumerate(self.config_actions):
            
            label = act.get("label") or act.get("key", "?").upper()
            if act.get("label"):
                label += f" ({act['key'].upper()})"
            b = tk.Button(self.actions_panel, text=label, width=22,
                          command=lambda a=act: self._trigger_action(a))
            r = idx // columns
            c = idx % columns
            b.grid(row=r, column=c, padx=4, pady=4, sticky="ew")
        # make columns expand
        for c in range(columns):
            self.actions_panel.grid_columnconfigure(c, weight=1)

    def _trigger_action(self, act: Dict[str, Any]) -> None:
        if not (self.ble_client and self.ble_client.is_connected):
            self._append_text("Not connected to any device.\n")
            return
        data = act.get("data")
        try:
            payload = to_bytes(data)
        except Exception as e:
            self._append_text(f"Invalid action payload: {e}\n")
            return
        self.run_in_loop(self._async_write(payload))
        shown = act.get("label") or act.get("key", "?").upper()
        self._append_text(f"Action sent: {shown}\n")

    # -----------------------------
    # Keyboard handling for WASD + action keys
    # -----------------------------
    def _on_key_press(self, event: tk.Event) -> Optional[str]:
        if not self.keyboard_enabled_var.get():
            return None  # allow normal typing
        key = (event.keysym or '').lower()
        if key in self._pressed_keys:
            return "break"  # suppress repeats if we handle it

        # Direction keys
        if key in ('w','a','s','d'):
            self._pressed_keys.add(key)
            self._start_direction_stream(key)
            return "break"

        # Action keys (one-shot)
        for act in self.config_actions:
            if act.get("key") == key:
                self._pressed_keys.add(key)
                self._trigger_action(act)
                return "break"
        return None

    def _on_key_release(self, event: tk.Event) -> Optional[str]:
        key = (event.keysym or '').lower()
        if key in self._pressed_keys:
            self._pressed_keys.discard(key)
            # If a direction key is released and it was the active one, send stop
            if key == self._current_dir_key:
                self._send_dir_stop()
                self._current_dir_key = None
                self._dir_payload = None
            return "break" if self.keyboard_enabled_var.get() else None
        return None

    def _start_direction_stream(self, key: str) -> None:
        # Take a snapshot of current frequency; changes apply on next press
        try:
            hz = max(1.0, float(self.frequency_var.get()))
        except Exception:
            hz = float(DEFAULT_FREQUENCY_HZ)
            self.frequency_var.set(str(DEFAULT_FREQUENCY_HZ))
        period = 1.0 / hz

        # Determine payload from config
        raw = self.config_directions.get(key)
        if raw is None:
            self._append_text(f"No payload configured for '{key}'.\n")
            return
        try:
            payload = to_bytes(raw)
        except Exception as e:
            self._append_text(f"Invalid direction payload for '{key}': {e}\n")
            return

        # Switch current direction
        self._current_dir_key = key
        self._dir_payload = payload
        self._dir_period_s = period

    def _send_dir_stop(self) -> None:
        if not (self.ble_client and self.ble_client.is_connected):
            return
        if self.config_stop is None:
            return
        try:
            payload = to_bytes(self.config_stop)
        except Exception as e:
            self._append_text(f"Invalid stop payload: {e}\n")
            return
        self.run_in_loop(self._async_write(payload))
        self._append_text("Sent: DIR_STOP\n")

    def _direction_sender_loop(self) -> None:
        last_sent = 0.0
        while not self._dir_thread_stop.is_set():
            now = time.time()
            # If a direction is active and BLE is connected, send at the configured snapshot rate
            if self._current_dir_key and self._dir_payload and self.ble_client and self.ble_client.is_connected:
                if now - last_sent >= self._dir_period_s:
                    self.run_in_loop(self._async_write(self._dir_payload))
                    last_sent = now
            time.sleep(0.005)  # 5ms tick to keep CPU low

    # -----------------------------
    # Persistence
    # -----------------------------
    def _save_last_connected_device(self, device_name: str) -> None:
        try:
            with open(DEVICE_FILE, 'w', encoding='utf-8') as f:
                json.dump({"device_name": device_name}, f)
        except Exception:
            pass

    def _load_last_connected_device(self) -> None:
        try:
            if not os.path.exists(DEVICE_FILE):
                return
            with open(DEVICE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            last = data.get("device_name", "")
            if last:
                self.device_name_entry.delete(0, tk.END)
                self.device_name_entry.insert(0, last)
                self.device_name_entry.config(fg='black')
        except Exception:
            pass

    # -----------------------------
    # Text helper
    # -----------------------------
    def _append_text(self, text: str) -> None:
        if not self.winfo_exists():
            return
        self.received_data_text.insert(tk.END, text)
        self.received_data_text.see(tk.END)

    # -----------------------------
    # Closing
    # -----------------------------
    def on_closing(self) -> None:
        try:
            self._dir_thread_stop.set()
            if self.ble_client and self.ble_client.is_connected:
                fut = self.run_in_loop(self.ble_client.disconnect())
                if fut:
                    fut.result(timeout=2.0)
        except Exception:
            pass
        if self.loop and self.loop_running:
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.asyncio_thread and self.asyncio_thread.is_alive():
            self.asyncio_thread.join(timeout=1.0)
        self.destroy()


if __name__ == "__main__":
    app = Application()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
