import time
import tkinter as tk
from tkinter import messagebox
from typing import Any, Callable, Dict, Optional

from actions_config import DIRECTION_KEYS, ActionsConfig
from ble_connection import BleConnection
from ble_widgets import ConnectionPanel, LogView, MessageSender, ScannerPanel
from drive_controller import DEFAULT_FREQUENCY_HZ, DriveController


# -----------------------------
# Actions panel
# -----------------------------
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
    """Tk adapter: feeds key events to a DriveController.

    Tk (X11 in particular) generates a release/press pair for every auto-repeat,
    so direction key releases are debounced: a release only counts if the key was
    not pressed again within `release_delay_s`.
    """

    def __init__(self, root: tk.Misc, conn: BleConnection, config: ActionsConfig,
                 end_data: Callable[[], bytes], release_delay_s: float = 0.03) -> None:
        self.root = root
        self.drive = DriveController(conn, config, end_data)
        self.release_delay_s = release_delay_s

        self.enabled_var = tk.BooleanVar(value=True)
        self.frequency_var = tk.StringVar(value=str(DEFAULT_FREQUENCY_HZ))

        self._pending_release: Dict[str, float] = {}  # key -> time of its last unconfirmed release

    def bind(self) -> None:
        self.root.bind_all("<KeyPress>", self._on_key_press, add=True)
        self.root.bind_all("<KeyRelease>", self._on_key_release, add=True)

    def trigger_action(self, act: Dict[str, Any]) -> None:
        self.drive.trigger_action(act)

    def shutdown(self) -> None:
        self.drive.shutdown()

    def _apply_frequency(self) -> None:
        try:
            self.drive.set_frequency(float(self.frequency_var.get()))
        except ValueError:
            self.frequency_var.set(str(DEFAULT_FREQUENCY_HZ))
            self.drive.set_frequency(DEFAULT_FREQUENCY_HZ)

    def _on_key_press(self, event: tk.Event) -> Optional[str]:
        if not self.enabled_var.get():
            return None
        key = (event.keysym or '').lower()
        self._pending_release.pop(key, None)  # a new press cancels a pending release
        if key in DIRECTION_KEYS:
            self._apply_frequency()
        return "break" if self.drive.key_down(key) else None

    def _on_key_release(self, event: tk.Event) -> Optional[str]:
        key = (event.keysym or '').lower()
        if key not in DIRECTION_KEYS:
            self.drive.key_up(key)
            return None
        t = time.time()
        self._pending_release[key] = t
        self.root.after(int(self.release_delay_s * 1000), lambda: self._confirm_release(key, t))
        return "break" if self.enabled_var.get() else None

    def _confirm_release(self, key: str, ts: float) -> None:
        if self._pending_release.get(key) == ts:
            del self._pending_release[key]
            self.drive.key_up(key)


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
        return self.actions_config.with_header(payload) if self.use_header_var.get() else payload

    def _describe_sent(self, message: str) -> str:
        header_info = f" (with header {self.actions_config.header})" if self.use_header_var.get() else ""
        return f"Sent to robot : {message}{header_info}"

    def on_closing(self) -> None:
        self.keyboard.shutdown()
        self.conn.shutdown()
        self.destroy()


if __name__ == "__main__":
    Application().mainloop()
