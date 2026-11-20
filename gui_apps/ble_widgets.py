"""Standalone Tk widgets for a `BleConnection`.

Each widget receives the connection as a parameter, subscribes to its signals
and moves the updates back onto the Tk thread. They can be freely assembled:

    conn = BleConnection()
    scanner = ScannerPanel(root, conn)
    link = ConnectionPanel(root, conn)
    scanner.on_selected = link.set_target
    MessageSender(root, conn)
    LogView(root, conn)
"""
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional

from ble_connection import (END_DATA_OPTIONS, BleConnection, DiscoveredDevice, default_history_path,
                            load_history, load_last_device, save_history)


class PlaceholderEntry(tk.Entry):
    def __init__(self, master=None, placeholder="PLACEHOLDER", color='grey', **kwargs):
        super().__init__(master, **kwargs)

        self.default = placeholder
        self.placeholder_color = color
        self.default_color = self['fg']

        self.bind("<FocusIn>", self.foc_in)
        self.bind("<FocusOut>", self.foc_out)

        self.put_placeholder()

    def put_placeholder(self):
        self.delete(0, 'end')
        self.insert(0, self.default)
        self['fg'] = self.placeholder_color

    def foc_in(self, *args):
        if self['fg'] == self.placeholder_color:
            self.delete('0', 'end')
            self['fg'] = self.default_color

    def foc_out(self, *args):
        if not self.get():
            self.put_placeholder()

    def set_text(self, text):
        """Set text directly, bypassing placeholder logic."""
        self.delete(0, 'end')
        self.insert(0, text)
        self['fg'] = self.default_color

    def get_value(self) -> str:
        """Typed text, or '' if the placeholder is showing."""
        if self['fg'] == self.placeholder_color and self.get() == self.default:
            return ""
        return self.get().strip()


class _ThreadSafeMixin:
    """Run a function on the Tk thread from any thread."""

    def _ui(self, func, *args) -> None:
        try:
            self.after(0, func, *args)
        except (tk.TclError, RuntimeError):
            pass  # window closed


class ScannerPanel(_ThreadSafeMixin, tk.Frame):
    """Scan button + list of discovered devices.

    `on_selected(device)` is called when the user picks a device.
    """

    def __init__(self, parent, conn: BleConnection,
                 on_selected: Optional[Callable[[DiscoveredDevice], None]] = None) -> None:
        super().__init__(parent)
        self.conn = conn
        self.on_selected = on_selected
        self._devices: Dict[str, DiscoveredDevice] = {}

        self.scan_button = tk.Button(self, text="Scan Devices", command=conn.scan)
        self.scan_button.pack(side=tk.LEFT)

        self.selected_device = tk.StringVar()
        self.device_dropdown = ttk.Combobox(self, textvariable=self.selected_device,
                                            values=[], state="readonly", width=45)
        self.device_dropdown.pack(side=tk.LEFT, padx=6, fill=tk.X, expand=True)
        self.device_dropdown.bind("<<ComboboxSelected>>", self._on_dropdown_selected)

        conn.scanning.connect(lambda busy: self._ui(self._set_scanning, busy))
        conn.devices_found.connect(lambda devices: self._ui(self._show_devices, devices))

    def _set_scanning(self, busy: bool) -> None:
        self.scan_button.config(state="disabled" if busy else "normal",
                                text="Scanning…" if busy else "Scan Devices")

    def _show_devices(self, devices) -> None:
        self._devices = {d.display: d for d in devices}
        self.device_dropdown['values'] = list(self._devices)

    def _on_dropdown_selected(self, _=None) -> None:
        device = self._devices.get(self.selected_device.get())
        if device and self.on_selected:
            self.on_selected(device)


class ConnectionPanel(_ThreadSafeMixin, tk.Frame):
    """Device name, Connect / Disconnect buttons and status."""

    def __init__(self, parent, conn: BleConnection) -> None:
        super().__init__(parent)
        self.conn = conn
        self._target: Optional[DiscoveredDevice] = None

        row = tk.Frame(self)
        row.pack(side=tk.TOP, fill=tk.X)

        self.device_name_entry = PlaceholderEntry(row, placeholder="Or enter device name manually")
        self.device_name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.connect_button = tk.Button(row, text="Connect", command=self._on_connect)
        self.connect_button.pack(side=tk.LEFT, padx=4)

        self.disconnect_button = tk.Button(row, text="Disconnect", command=conn.disconnect)
        self.disconnect_button.pack(side=tk.LEFT)

        self.status_label = tk.Label(self, text="Status: Disconnected", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.TOP, fill=tk.X, pady=(6, 0))

        conn.connecting.connect(lambda busy: self._ui(self._set_busy, self.connect_button, busy,
                                                      "Connecting…", "Connect"))
        conn.disconnecting.connect(lambda busy: self._ui(self._set_busy, self.disconnect_button, busy,
                                                         "Disconnecting…", "Disconnect"))
        conn.status.connect(lambda text: self._ui(self.status_label.config, {"text": f"Status: {text}"}))

        last = load_last_device()
        if last:
            self.device_name_entry.set_text(last)

    def set_target(self, device: DiscoveredDevice) -> None:
        """Select a discovered device (fills in the name and remembers its address)."""
        self._target = device
        self.device_name_entry.set_text(device.name)

    @staticmethod
    def _set_busy(button: tk.Button, busy: bool, busy_text: str, idle_text: str) -> None:
        button.config(state="disabled" if busy else "normal", text=busy_text if busy else idle_text)

    def _on_connect(self) -> None:
        name = self.device_name_entry.get_value()
        if not name:
            self.conn.log.emit("Please select or enter a device name.\n")
            return
        # The address is only reused if the name was not edited after the selection
        address = self._target.address if self._target and self._target.name == name else None
        self.conn.connect(name, address)


class MessageSender(_ThreadSafeMixin, tk.Frame):
    """Text field + line ending + Send button.

    Other widgets can be added to `self.extras` (placed before the Send button).
    `describe_sent(msg)` customizes the text logged after sending.

    Like the Arduino serial monitor, the Up / Down keys in the text field browse
    the history of sent messages (at most `max_history`). The history is saved in
    the per-user data directory (see `user_data_dir`) so it survives restarts;
    pass `history_file=None` to keep it in memory only.
    """

    def __init__(self, parent, conn: BleConnection,
                 describe_sent: Callable[[str], str] = lambda msg: f"Sent: {msg}",
                 max_history: int = 100,
                 history_file: Optional[str] = default_history_path()) -> None:
        super().__init__(parent)
        self.conn = conn
        self.describe_sent = describe_sent
        self.max_history = max_history
        self.history_file = history_file
        self._history: List[str] = load_history(history_file)[-max_history:] if history_file else []
        self._history_index = len(self._history)  # == len(history) when not browsing
        self._draft = ""          # text being typed before browsing started
        self.line_ending_var = tk.StringVar(value="BOTH")

        self.entry = PlaceholderEntry(self, placeholder="Enter your text here")
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        # Pressing Enter in the text field sends the message
        self.entry.bind("<Return>", lambda _e: self.send())
        self.entry.bind("<KP_Enter>", lambda _e: self.send())
        self.entry.bind("<Up>", lambda _e: self._browse_history(-1))
        self.entry.bind("<Down>", lambda _e: self._browse_history(+1))

        self.line_endings_dropdown = ttk.Combobox(self, textvariable=self.line_ending_var,
                                                  values=list(END_DATA_OPTIONS), width=6, state="readonly")
        self.line_endings_dropdown.pack(side=tk.LEFT, padx=6)

        self.extras = tk.Frame(self)
        self.extras.pack(side=tk.LEFT)

        self.send_button = tk.Button(self, text="Send", command=self.send)
        self.send_button.pack(side=tk.LEFT)

    def end_data(self) -> bytes:
        return END_DATA_OPTIONS.get(self.line_ending_var.get(), b'')

    def set_entry_enabled(self, enabled: bool) -> None:
        self.entry.config(state="normal" if enabled else "disabled")

    def send(self) -> None:
        if not self.conn.is_connected:
            self.conn.log.emit("Not connected to any device.\n")
            return
        msg = self.entry.get_value()
        if not msg:
            self.conn.log.emit("Please enter a message to send.\n")
            return
        self.conn.write(msg.encode('utf-8') + self.end_data())
        self.conn.log.emit(self.describe_sent(msg) + "\n")
        self._add_to_history(msg)
        self.entry.delete(0, tk.END)

    def _add_to_history(self, msg: str) -> None:
        if not self._history or self._history[-1] != msg:  # skip consecutive duplicates
            self._history.append(msg)
            del self._history[:-self.max_history]
            if self.history_file:
                save_history(self.history_file, self._history)
        self._history_index = len(self._history)
        self._draft = ""

    def _browse_history(self, step: int) -> str:
        """Move through the history (-1 = older, +1 = newer) and show the entry in the field."""
        if not self._history:
            return "break"
        if self._history_index == len(self._history):
            self._draft = self.entry.get_value()  # remember what was being typed
        new_index = self._history_index + step
        if new_index < 0 or new_index > len(self._history):
            return "break"
        self._history_index = new_index
        if new_index == len(self._history):
            text = self._draft
        else:
            text = self._history[new_index]
        if text:
            self.entry.set_text(text)
        else:
            self.entry.delete(0, tk.END)
        return "break"  # keep the cursor from jumping inside the field


class LogView(_ThreadSafeMixin, tk.Frame):
    """Log: connection messages and received data.

    line_buffered=False: each received chunk is shown as-is, preceded by `rx_prefix`.
    line_buffered=True:  chunks are reassembled and only complete lines are shown.
    """

    def __init__(self, parent, conn: BleConnection, line_buffered: bool = False,
                 rx_prefix: str = "Received: ", height: int = 14) -> None:
        super().__init__(parent)
        self.line_buffered = line_buffered
        self.rx_prefix = rx_prefix
        self._rx_buffer = ""

        self.text = tk.Text(self, height=height)
        self.text.pack(fill=tk.BOTH, expand=True)

        conn.log.connect(lambda text: self._ui(self.append, text))
        conn.rx.connect(lambda chunk: self._ui(self._on_rx, chunk))
        conn.disconnecting.connect(lambda busy: busy and self._ui(self.flush))

    def append(self, text: str) -> None:
        try:
            self.text.insert(tk.END, text)
            self.text.see(tk.END)
        except tk.TclError:
            pass

    def _on_rx(self, chunk: str) -> None:
        if not self.line_buffered:
            self.append(f"{self.rx_prefix}{chunk}\n")
            return
        self._rx_buffer = (self._rx_buffer + chunk).replace("\r\n", "\n")
        while "\n" in self._rx_buffer:
            line, self._rx_buffer = self._rx_buffer.split("\n", 1)
            self.append(line + "\n")

    def flush(self) -> None:
        """Show whatever is left in the buffer (incomplete line)."""
        if self._rx_buffer:
            self.append(self._rx_buffer)
            self._rx_buffer = ""
