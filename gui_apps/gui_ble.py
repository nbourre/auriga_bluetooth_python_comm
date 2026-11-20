import tkinter as tk

from ble_connection import BleConnection
from ble_widgets import ConnectionPanel, LogView, MessageSender, ScannerPanel


class Application(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("BLE Communication App")
        self.geometry("600x450")

        self.conn = BleConnection()

        top = tk.Frame(self)
        top.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)

        scanner = ScannerPanel(top, self.conn)
        scanner.pack(side=tk.TOP, fill=tk.X)

        link = ConnectionPanel(top, self.conn)
        link.pack(side=tk.TOP, fill=tk.X, pady=(6, 0))
        scanner.on_selected = link.set_target

        MessageSender(top, self.conn).pack(side=tk.TOP, fill=tk.X, pady=(8, 0))

        LogView(self, self.conn).pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self) -> None:
        self.conn.shutdown()
        self.destroy()


if __name__ == "__main__":
    Application().mainloop()
