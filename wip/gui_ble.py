import tkinter as tk
from tkinter import ttk
import json
import os
from bleak import BleakClient, BleakScanner, BleakError
import asyncio
from concurrent.futures import ThreadPoolExecutor

DEVICE_NAME_KEY = "device_name"
DEVICE_FILE = "last_connected_device.json"
CHARACTERISTIC_NOTIFY_UUID = "0000ffe2-0000-1000-8000-00805f9b34fb"  # UUID for notifications
CHARACTERISTIC_WRITE_UUID = "0000ffe3-0000-1000-8000-00805f9b34fb"  # UUID for writing
CHARACTERISTIC_READ_UUID = "0000ffe5-0000-1000-8000-00805f9b34fb"  # Example for read characteristic
CHARACTERISTIC_INDICATE_UUID = "0000ffe4-0000-1000-8000-00805f9b34fb"  # Example for indication characteristic
DISCONNECTION_TIMEOUT = 10

# Options de données de fin
END_DATA_OPTIONS = {
    'NL': b'\n',  # Nouvelle ligne (0x0A)
    'CR': b'\r',  # Retour chariot (0x0D)
    'BOTH': b'\r\n',  # CR + NL
    'NONE': b''  # Pas de données de fin
}

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

class Application(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("BLE Communication App")
        self.geometry("600x400")
        
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.loop = asyncio.get_event_loop()

        # Create the controls
        self.create_controls()
        
        # Load the last connected device name if available
        self.load_last_connected_device()
    
    def create_controls(self):
        # Create a frame to hold the controls
        control_frame = tk.Frame(self)
        control_frame.pack(side=tk.TOP, fill=tk.X)
        
        connection_frame = tk.Frame(control_frame)
        connection_frame.pack(side=tk.TOP, fill=tk.X)
        
        # Create the text edit for device name
        self.device_name_entry = PlaceholderEntry(connection_frame, placeholder="Enter device name here")
        self.device_name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Create the connect button
        self.connect_button = tk.Button(connection_frame, text="Connect", command=self.start_connect_device)
        self.connect_button.pack(side=tk.LEFT)
        
        message_frame = tk.Frame(control_frame)
        message_frame.pack(side=tk.TOP, fill=tk.X)

        # Create the text edit for sending messages
        self.message_entry = PlaceholderEntry(message_frame, placeholder="Enter your text here")
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Create the drop down list for line endings
        self.line_endings = tk.StringVar()
        self.line_endings.set("BOTH")  # default value
        line_endings_options = ["NL", "CR", "BOTH", "NONE"]
        self.line_endings_dropdown = ttk.Combobox(message_frame, textvariable=self.line_endings, values=line_endings_options)
        self.line_endings_dropdown.pack(side=tk.LEFT)

        # Create the send button
        self.send_button = tk.Button(message_frame, text="Send", command=self.send_message)
        self.send_button.pack(side=tk.LEFT)

        # Create the text area for received data
        self.received_data_text = tk.Text(self)
        self.received_data_text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def start_connect_device(self):
        # Run the asynchronous BLE connection in a separate thread
        device_name = self.device_name_entry.get()
        self.executor.submit(self.loop.run_until_complete, self.connect_device(device_name))
        
    def load_last_connected_device(self):
        try:
            # Check if 'last_connected_device.json' exists
            if not os.path.exists("last_connected_device.json"):
                print("No last connected device found.")
                return
            
            with open("last_connected_device.json", 'r') as f:
                data = json.load(f)
                last_device_name = data.get("device_name", "")
                self.device_name_entry.set_text(last_device_name)
        except FileNotFoundError:
            pass

    async def find_device(self, device_name):
        devices = await BleakScanner.discover()
        for device in devices:
            if device.name == device_name:
                return device.address
        return None

    async def connect_device(self, device_name):
        try:
            devices = await BleakScanner.discover()
            device_address = next((d.address for d in devices if d.name == device_name), None)
            if device_address:
                async with BleakClient(device_address) as client:
                    print(f"Connected to {device_name}")
                    # Continue with BLE communication logic
            else:
                print(f"Device {device_name} not found")
        except BleakError as e:
            print(f"An error occurred: {e}")

    def on_closing(self):
        self.executor.shutdown(wait=False)
        self.destroy()
            
    async def async_connect_device(self, device_name):
        address = await self.find_device(device_name)
        if not address:
            self.received_data_text.insert(tk.END, f"Device '{device_name}' not found.\n")
            return
        
        self.ble_client = BleakClient(address)
        try:
            await self.ble_client.connect()
            if self.ble_client.is_connected:
                self.received_data_text.insert(tk.END, f"Connected to {device_name}.\n")
                self.save_last_connected_device(device_name)
                asyncio.create_task(self.listen_for_notifications())
        except Exception as e:
            self.received_data_text.insert(tk.END, f"Failed to connect to {device_name}: {e}\n")
            
    async def listen_for_notifications(self):
        def handle_notification(sender, data):
            self.received_data_text.insert(tk.END, f"Received: {data}\n")
            self.received_data_text.see(tk.END)
        
        await self.ble_client.start_notify(CHARACTERISTIC_NOTIFY_UUID, handle_notification)

    def save_last_connected_device(self, device_name):
        with open("last_connected_device.json", "w") as f:
            json.dump({"device_name": device_name}, f)

    
    def send_message(self):
        if self.ble_client and self.ble_client.is_connected:
            message = self.message_entry.get()
            line_ending = self.line_endings.get()
            end_data = {"NL": "\n", "CR": "\r", "BOTH": "\r\n", "NONE": ""}[line_ending]
            full_message = (message + end_data).encode("utf-8")
            asyncio.run(self.ble_client.write_gatt_char(CHARACTERISTIC_WRITE_UUID, full_message))
            self.message_entry.delete(0, tk.END)
        else:
            self.received_data_text.insert(tk.END, "Not connected to any device.\n")

    async def disconnect_device(self):
        if self.ble_client and self.ble_client.is_connected:
            await self.ble_client.disconnect()
            self.received_data_text.insert(tk.END, "Disconnected.\n")

if __name__ == "__main__":
    app = Application()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()