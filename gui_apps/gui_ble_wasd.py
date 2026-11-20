import json
import os
import threading
import time
import tkinter as tk
from tkinter import messagebox
from typing import Any, Callable, Dict, List, Optional

from ble_connection import BleConnection, to_bytes
from ble_widgets import ConnectionPanel, LogView, MessageSender, ScannerPanel

ACTIONS_FILE = "actions.json"  # in the current working directory
DEFAULT_FREQUENCY_HZ = 10      # default send frequency for WASD
DEFAULT_HEADER = [0xFF, 0x55]  # default header
DIRECTION_KEYS = ('w', 'a', 's', 'd', 'e')


# -----------------------------
# Configuration (actions.json)
# -----------------------------
class ActionsConfig:
    """Contents of actions.json: header, direction payloads and one-shot actions."""

    def __init__(self, filename: str = ACTIONS_FILE) -> None:
        self.filename = filename
        self.directions: Dict[str, Any] = {}
        self.stop: Any = None
        self.actions: List[Dict[str, Any]] = []
        self.header: List[int] = DEFAULT_HEADER.copy()

    def load(self) -> None:
        """Load the file (creating it with default values if it does not exist).

        Raises ValueError if the content is invalid.
        """
        path = os.path.join(os.getcwd(), self.filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except FileNotFoundError:
            cfg = {
                "header": [255, 85],
                "directions": {"w": "F", "a": "L", "s": "B", "d": "R", "e": "K", "stop": "S"},
                "actions": [
                    {"key": "l", "data": "LIGHT_TOGGLE", "label": "Toggle Light"},
                    {"key": "z", "data": [255, 85], "label": "Special Command"}
                ]
            }
            with open(path, 'w', encoding='utf-8') as wf:
                json.dump(cfg, wf, indent=2)

        dirs = cfg.get("directions", {})
        stop = dirs.get("stop")
        if not all(k in dirs for k in DIRECTION_KEYS) or stop is None:
            raise ValueError("'directions' must define w,a,s,d,e (klaxon) and stop")
        self.directions = {k: dirs[k] for k in DIRECTION_KEYS}
        self.stop = stop

        header = cfg.get("header", DEFAULT_HEADER)
        if isinstance(header, list) and all(isinstance(x, int) for x in header):
            self.header = header
        else:
            self.header = DEFAULT_HEADER.copy()

        self.actions = []
        for item in cfg.get("actions", []):
            key = str(item.get("key", "")).lower()
            if key:
                self.actions.append({"key": key, "data": item.get("data"),
                                     "label": item.get("label", key.upper())})

    @property
    def header_hex(self) -> str:
        return ' '.join(f'0x{b:02X}' for b in self.header)


class ActionsPanel(tk.Frame):
    """Buttons for the configured actions + a reload button."""

    def __init__(self, parent, conn: BleConnection, config: ActionsConfig,
                 on_trigger: Callable[[Dict[str, Any]], None]) -> None:
        super().__init__(parent)
        self.conn = conn
        self.config_data = config
        self.on_trigger = on_trigger

        header = tk.Frame(self)
        header.pack(side=tk.TOP, fill=tk.X)
        tk.Label(header, text="Actions (from actions.json)",
                 font=("TkDefaultFont", 10, "bold")).pack(side=tk.LEFT)
        tk.Button(header, text="Reload Actions", command=self.reload).pack(side=tk.RIGHT)

        self.buttons_frame = tk.Frame(self)
        self.buttons_frame.pack(side=tk.TOP, fill=tk.X, pady=(4, 0))

    def reload(self) -> None:
        try:
            self.config_data.load()
        except Exception as e:
            messagebox.showerror("actions.json error", str(e))
            return
        self._rebuild()
        self.conn.log.emit(f"Actions loaded. Header configured: [{self.config_data.header_hex}]\n")

    def _rebuild(self) -> None:
        for w in self.buttons_frame.winfo_children():
            w.destroy()
        actions = self.config_data.actions
        if not actions:
            tk.Label(self.buttons_frame, text="No actions configured.").pack(anchor=tk.W)
            return
        columns = 3
        for idx, act in enumerate(actions):
            label = act.get("label") or act.get("key", "?").upper()
            if act.get("label"):
                label += f" ({act['key'].upper()})"
            b = tk.Button(self.buttons_frame, text=label, width=22,
                          command=lambda a=act: self.on_trigger(a))
            b.grid(row=idx // columns, column=idx % columns, padx=4, pady=4, sticky="ew")
        for c in range(columns):
            self.buttons_frame.grid_columnconfigure(c, weight=1)


# -----------------------------
# Keyboard control
# -----------------------------
class KeyboardController:
    """Translates W/A/S/D/E keys (continuous stream) and action keys (one-shot) into BLE writes."""

    def __init__(self, root: tk.Misc, conn: BleConnection, config: ActionsConfig,
                 end_data: Callable[[], bytes]) -> None:
        self.root = root
        self.conn = conn
        self.config = config
        self.end_data = end_data

        self.enabled_var = tk.BooleanVar(value=True)
        self.frequency_var = tk.StringVar(value=str(DEFAULT_FREQUENCY_HZ))

        self._pressed_keys: set[str] = set()            # one-shot actions (avoid key repeat)
        self._key_stack: list[str] = []                 # LIFO stack of direction keys
        self._last_release_time: Dict[str, float] = {}  # KeyRelease debounce
        self._release_delay_s: float = 0.03             # 30 ms

        self._dir_payload: Optional[bytes] = None
        self._dir_period_s: float = 1.0 / DEFAULT_FREQUENCY_HZ
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._direction_sender_loop, daemon=True)
        self._thread.start()

    def bind(self) -> None:
        self.root.bind_all("<KeyPress>", self._on_key_press, add=True)
        self.root.bind_all("<KeyRelease>", self._on_key_release, add=True)

    def shutdown(self) -> None:
        self._stop_event.set()

    # --- One-shot actions ---
    def trigger_action(self, act: Dict[str, Any]) -> None:
        if not self.conn.is_connected:
            self.conn.log.emit("Not connected to any device.\n")
            return
        try:
            payload = to_bytes(act.get("data")) + self.end_data()
        except Exception as e:
            self.conn.log.emit(f"Invalid action payload: {e}\n")
            return
        self.conn.write(payload)
        shown = act.get("label") or act.get("key", "?").upper()
        self.conn.log.emit(f"Action sent: {shown}\n")

    # --- Keyboard events (stack model) ---
    def _on_key_press(self, event: tk.Event) -> Optional[str]:
        if not self.enabled_var.get():
            return None
        key = (event.keysym or '').lower()

        if key in DIRECTION_KEYS:
            if key not in self._key_stack:
                self._key_stack.append(key)
                self._snapshot_period()
                self._recompute_from_stack_and_send()
            return "break"

        for act in self.config.actions:
            if act.get("key") == key:
                if key not in self._pressed_keys:
                    self._pressed_keys.add(key)
                    self.trigger_action(act)
                return "break"
        return None

    def _on_key_release(self, event: tk.Event) -> Optional[str]:
        key = (event.keysym or '').lower()
        self._pressed_keys.discard(key)

        if key in DIRECTION_KEYS:
            t = time.time()
            self._last_release_time[key] = t
            self.root.after(int(self._release_delay_s * 1000),
                            lambda k=key, ts=t: self._confirm_release(k, ts))
            return "break" if self.enabled_var.get() else None
        return None

    def _confirm_release(self, key: str, ts: float) -> None:
        # confirm the release only if there was no newer press since ts
        if self._last_release_time.get(key, 0) == ts and key in self._key_stack:
            self._key_stack = [k for k in self._key_stack if k != key]
            self._recompute_from_stack_and_send()

    def _snapshot_period(self) -> None:
        try:
            hz = max(1.0, float(self.frequency_var.get()))
        except Exception:
            hz = float(DEFAULT_FREQUENCY_HZ)
            self.frequency_var.set(str(DEFAULT_FREQUENCY_HZ))
        self._dir_period_s = 1.0 / hz

    def _recompute_from_stack_and_send(self) -> None:
        # empty stack -> STOP, otherwise send the command on top of the stack
        if not self._key_stack:
            self._dir_payload = None
            self._send_stop()
            return
        raw = self.config.directions.get(self._key_stack[-1])
        if raw is None:
            return
        try:
            self._dir_payload = to_bytes(raw) + self.end_data()
            if self.conn.is_connected:
                self.conn.write(self._dir_payload)
        except Exception as e:
            self.conn.log.emit(f"Payload error: {e}\n")

    def _send_stop(self) -> None:
        if not self.conn.is_connected or self.config.stop is None:
            return
        try:
            payload = to_bytes(self.config.stop) + self.end_data()
        except Exception as e:
            self.conn.log.emit(f"Invalid stop payload: {e}\n")
            return
        self.conn.write(payload)
        self.conn.log.emit(f"Sent: {self.config.stop}\n")

    def _direction_sender_loop(self) -> None:
        last_sent = 0.0
        while not self._stop_event.is_set():
            now = time.time()
            payload = self._dir_payload
            if payload and self.conn.is_connected and self._dir_period_s > 0:
                if now - last_sent >= self._dir_period_s:
                    if self.conn.write(payload):
                        last_sent = now
            time.sleep(0.005)


# -----------------------------
# Application
# -----------------------------
class Application(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("BLE Robot Controller")
        self.geometry("780x560")

        self.conn = BleConnection()
        self.actions_config = ActionsConfig()
        self.use_header_var = tk.BooleanVar(value=False)
        self.conn.payload_wrapper = self._add_header

        top = tk.Frame(self)
        top.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)

        scanner = ScannerPanel(top, self.conn)
        scanner.pack(side=tk.TOP, fill=tk.X)

        link = ConnectionPanel(top, self.conn)
        link.pack(side=tk.TOP, fill=tk.X, pady=(6, 0))
        scanner.on_selected = link.set_target

        self.sender = MessageSender(top, self.conn, describe_sent=self._describe_sent)
        self.sender.pack(side=tk.TOP, fill=tk.X, pady=(8, 0))
        tk.Checkbutton(self.sender.extras, text="Header", variable=self.use_header_var).pack(side=tk.LEFT, padx=6)

        self.keyboard = KeyboardController(self, self.conn, self.actions_config, self.sender.end_data)
        self._build_keyboard_row(top)

        self.actions_panel = ActionsPanel(top, self.conn, self.actions_config,
                                          on_trigger=self.keyboard.trigger_action)
        self.actions_panel.pack(side=tk.TOP, fill=tk.X, pady=(10, 0))

        LogView(self, self.conn, line_buffered=True).pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.keyboard.bind()
        self._on_keyboard_control_changed()
        self.actions_panel.reload()  # after LogView so the load message is shown

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _build_keyboard_row(self, parent: tk.Frame) -> None:
        row = tk.Frame(parent)
        row.pack(side=tk.TOP, fill=tk.X, pady=(10, 0))

        tk.Checkbutton(row, text="Enable Keyboard Control (W/A/S/D + action keys)",
                       variable=self.keyboard.enabled_var,
                       command=self._on_keyboard_control_changed).pack(side=tk.LEFT)

        freq = tk.Frame(row)
        freq.pack(side=tk.RIGHT)
        tk.Label(freq, text="Frequency:").pack(side=tk.LEFT)
        tk.Entry(freq, width=6, textvariable=self.keyboard.frequency_var).pack(side=tk.LEFT)
        tk.Label(freq, text="Hz").pack(side=tk.LEFT, padx=(2, 0))

    def _on_keyboard_control_changed(self) -> None:
        self.sender.set_entry_enabled(not self.keyboard.enabled_var.get())

    def _add_header(self, payload: bytes) -> bytes:
        if self.use_header_var.get() and self.actions_config.header:
            return bytes(self.actions_config.header) + payload
        return payload

    def _describe_sent(self, message: str) -> str:
        header_info = f" (with header {self.actions_config.header})" if self.use_header_var.get() else ""
        return f"Sent to robot : {message}{header_info}"

    def on_closing(self) -> None:
        self.keyboard.shutdown()
        self.conn.shutdown()
        self.destroy()


if __name__ == "__main__":
    Application().mainloop()
