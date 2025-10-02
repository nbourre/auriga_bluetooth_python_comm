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
        self.geometry("600x450")
        
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.loop = asyncio.get_event_loop()
        
        # Initialize BLE client and discovered devices
        self.ble_client = None
        self.discovered_devices = {}

        # Create the controls
        self.create_controls()
        
        # Load the last connected device name if available
        self.load_last_connected_device()
    
    def create_controls(self):
        # Create a frame to hold the controls
        control_frame = tk.Frame(self)
        control_frame.pack(side=tk.TOP, fill=tk.X)
        
        # Scanner frame
        scanner_frame = tk.Frame(control_frame)
        scanner_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))
        
        # Create the scan button
        self.scan_button = tk.Button(scanner_frame, text="Scan Devices", command=self.start_scan_devices)
        self.scan_button.pack(side=tk.LEFT)
        
        # Create the device dropdown
        self.selected_device = tk.StringVar()
        self.device_dropdown = ttk.Combobox(scanner_frame, textvariable=self.selected_device, 
                                          values=[], state="readonly", width=40)
        self.device_dropdown.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        self.device_dropdown.bind("<<ComboboxSelected>>", self.on_device_selected)
        
        connection_frame = tk.Frame(control_frame)
        connection_frame.pack(side=tk.TOP, fill=tk.X)
        
        # Create the text edit for device name (keep for manual entry)
        self.device_name_entry = PlaceholderEntry(connection_frame, placeholder="Or enter device name manually")
        self.device_name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Create the connect button
        self.connect_button = tk.Button(connection_frame, text="Connect", command=self.start_connect_device)
        self.connect_button.pack(side=tk.LEFT)
        
        # Create the disconnect button
        self.disconnect_button = tk.Button(connection_frame, text="Disconnect", command=self.start_disconnect_device)
        self.disconnect_button.pack(side=tk.LEFT)
        
        # Status frame
        status_frame = tk.Frame(control_frame)
        status_frame.pack(side=tk.TOP, fill=tk.X, pady=(5, 0))
        
        # Status label
        self.status_label = tk.Label(status_frame, text="Status: Disconnected", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
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

    def start_scan_devices(self):
        """Start the device scanning process in a separate thread."""
        self.scan_button.config(state="disabled", text="Scanning...")
        self.executor.submit(self.run_async_scan)
    
    def run_async_scan(self):
        """Run the async scan in the event loop."""
        asyncio.run(self.scan_devices())
    
    async def scan_devices(self):
        """Scan for BLE devices and populate the dropdown."""
        try:
            self.received_data_text.insert(tk.END, "Scanning for devices...\n")
            self.received_data_text.see(tk.END)
            
            devices = await BleakScanner.discover(timeout=10.0)
            self.discovered_devices = {}
            device_names = []
            
            for device in devices:
                if device.name:  # Only include devices with names
                    display_name = f"{device.name} ({device.address})"
                    self.discovered_devices[display_name] = {
                        'name': device.name,
                        'address': device.address,
                        'rssi': device.rssi if hasattr(device, 'rssi') else 'N/A'
                    }
                    device_names.append(display_name)
            
            # Update the dropdown on the main thread
            self.after(0, self.update_device_dropdown, device_names)
            
        except Exception as e:
            self.after(0, lambda: self.received_data_text.insert(tk.END, f"Scan error: {e}\n"))
        finally:
            self.after(0, lambda: self.scan_button.config(state="normal", text="Scan Devices"))
    
    def update_device_dropdown(self, device_names):
        """Update the device dropdown with discovered devices."""
        self.device_dropdown['values'] = sorted(device_names)
        if device_names:
            self.received_data_text.insert(tk.END, f"Found {len(device_names)} devices.\n")
        else:
            self.received_data_text.insert(tk.END, "No devices found.\n")
        self.received_data_text.see(tk.END)
    
    def on_device_selected(self, event=None):
        """Handle device selection from dropdown."""
        selected = self.selected_device.get()
        if selected and selected in self.discovered_devices:
            device_name = self.discovered_devices[selected]['name']
            self.device_name_entry.set_text(device_name)

    def start_connect_device(self):
        """Start the connection process in a separate thread."""
        # Get device name from either the dropdown selection or manual entry
        selected_display = self.selected_device.get()
        manual_name = self.device_name_entry.get()
        
        device_name = None
        device_address = None
        
        # Prioritize dropdown selection
        if selected_display and selected_display in self.discovered_devices:
            device_info = self.discovered_devices[selected_display]
            device_name = device_info['name']
            device_address = device_info['address']
        elif manual_name and manual_name != self.device_name_entry.default:
            device_name = manual_name
            
        if not device_name:
            self.received_data_text.insert(tk.END, "Please select a device or enter a device name.\n")
            return
            
        self.connect_button.config(state="disabled", text="Connecting...")
        self.executor.submit(self.run_async_connect, device_name, device_address)
    
    def run_async_connect(self, device_name, device_address=None):
        """Run the async connection in the event loop."""
        asyncio.run(self.async_connect_device(device_name, device_address))
    
    def start_disconnect_device(self):
        """Start the disconnection process in a separate thread."""
        self.disconnect_button.config(state="disabled", text="Disconnecting...")
        self.executor.submit(self.run_async_disconnect)
    
    def run_async_disconnect(self):
        """Run the async disconnection in the event loop."""
        asyncio.run(self.disconnect_device())
        
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



    def on_closing(self):
        """Handle application closing."""
        if self.ble_client and self.ble_client.is_connected:
            # Disconnect from device before closing
            asyncio.run(self.ble_client.disconnect())
        self.executor.shutdown(wait=False)
        self.destroy()
            
    async def async_connect_device(self, device_name, device_address=None):
        try:
            # If we don't have the address, find it
            if not device_address:
                address = await self.find_device(device_name)
                if not address:
                    self.after(0, lambda: self.received_data_text.insert(tk.END, f"Device '{device_name}' not found.\n"))
                    return
            else:
                address = device_address
            
            # Disconnect from any existing connection
            if self.ble_client and self.ble_client.is_connected:
                await self.ble_client.disconnect()
            
            self.ble_client = BleakClient(address)
            await self.ble_client.connect()
            
            if self.ble_client.is_connected:
                self.after(0, lambda: self.received_data_text.insert(tk.END, f"Connected to {device_name} ({address}).\n"))
                self.after(0, lambda: self.received_data_text.see(tk.END))
                self.after(0, lambda: self.status_label.config(text=f"Status: Connected to {device_name}"))
                self.save_last_connected_device(device_name)
                
                # Start listening for notifications
                await self.listen_for_notifications()
            else:
                self.after(0, lambda: self.received_data_text.insert(tk.END, f"Failed to connect to {device_name}.\n"))
                self.after(0, lambda: self.status_label.config(text="Status: Connection failed"))
                
        except Exception as e:
            self.after(0, lambda: self.received_data_text.insert(tk.END, f"Failed to connect to {device_name}: {e}\n"))
            self.after(0, lambda: self.received_data_text.see(tk.END))
            self.after(0, lambda: self.status_label.config(text="Status: Connection error"))
        finally:
            self.after(0, lambda: self.connect_button.config(state="normal", text="Connect"))
            
    async def listen_for_notifications(self):
        """Start listening for notifications from the connected device."""
        def handle_notification(sender, data):
            # Use after() to safely update GUI from notification callback
            self.after(0, lambda: self.received_data_text.insert(tk.END, f"Received: {data.decode('utf-8', errors='ignore')}\n"))
            self.after(0, lambda: self.received_data_text.see(tk.END))
        
        try:
            await self.ble_client.start_notify(CHARACTERISTIC_NOTIFY_UUID, handle_notification)
            self.after(0, lambda: self.received_data_text.insert(tk.END, "Started listening for notifications.\n"))
        except Exception as e:
            self.after(0, lambda: self.received_data_text.insert(tk.END, f"Failed to start notifications: {e}\n"))

    def save_last_connected_device(self, device_name):
        with open("last_connected_device.json", "w") as f:
            json.dump({"device_name": device_name}, f)

    
    def send_message(self):
        """Send a message to the connected device."""
        if self.ble_client and self.ble_client.is_connected:
            message = self.message_entry.get()
            if message and message != self.message_entry.default:
                line_ending = self.line_endings.get()
                end_data = END_DATA_OPTIONS[line_ending]
                full_message = message.encode("utf-8") + end_data
                
                # Send message in a separate thread
                self.executor.submit(self.run_async_send, full_message, message)
                self.message_entry.delete(0, tk.END)
            else:
                self.received_data_text.insert(tk.END, "Please enter a message to send.\n")
        else:
            self.received_data_text.insert(tk.END, "Not connected to any device.\n")
    
    def run_async_send(self, full_message, original_message):
        """Run the async send in the event loop."""
        asyncio.run(self.async_send_message(full_message, original_message))
    
    async def async_send_message(self, full_message, original_message):
        """Send message asynchronously."""
        try:
            await self.ble_client.write_gatt_char(CHARACTERISTIC_WRITE_UUID, full_message)
            self.after(0, lambda: self.received_data_text.insert(tk.END, f"Sent: {original_message}\n"))
            self.after(0, lambda: self.received_data_text.see(tk.END))
        except Exception as e:
            self.after(0, lambda: self.received_data_text.insert(tk.END, f"Send error: {e}\n"))
            self.after(0, lambda: self.received_data_text.see(tk.END))

    async def disconnect_device(self):
        try:
            if self.ble_client and self.ble_client.is_connected:
                await self.ble_client.disconnect()
                self.after(0, lambda: self.received_data_text.insert(tk.END, "Disconnected.\n"))
                self.after(0, lambda: self.received_data_text.see(tk.END))
                self.after(0, lambda: self.status_label.config(text="Status: Disconnected"))
            else:
                self.after(0, lambda: self.received_data_text.insert(tk.END, "No active connection to disconnect.\n"))
        except Exception as e:
            self.after(0, lambda: self.received_data_text.insert(tk.END, f"Disconnect error: {e}\n"))
            self.after(0, lambda: self.status_label.config(text="Status: Disconnect error"))
        finally:
            self.after(0, lambda: self.disconnect_button.config(state="normal", text="Disconnect"))

if __name__ == "__main__":
    app = Application()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()