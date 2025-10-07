import asyncio
import json
from bleak import BleakClient, BleakScanner, BleakError

# Bluetooth Configuration
DEVICE_NAME = "Makeblock_LE001b10672dfc"
DEVICE_FILE = "last_connected_device.json"
CHARACTERISTIC_NOTIFY_UUID = "0000ffe2-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_WRITE_UUID = "0000ffe3-0000-1000-8000-00805f9b34fb"
DISCONNECTION_TIMEOUT = 10

# End Data Options
END_DATA_OPTIONS = {
    'NL': b'\n',
    'CR': b'\r',
    'BOTH': b'\r\n',
    'NONE': b''
}

# Global variables
is_user_input_active = False
incomplete_message = ""
last_received_time = None

def load_last_device():
    """Load the last connected device from a JSON file."""
    try:
        with open(DEVICE_FILE, 'r') as f:
            data = json.load(f)
            return data.get("device_name")
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def save_last_device(device_name):
    """Save the last connected device to a JSON file."""
    with open(DEVICE_FILE, 'w') as f:
        json.dump({"device_name": device_name}, f)

def calculate_crc(data):
    """Calculate CRC by XOR-ing all bytes."""
    crc = 0
    for byte in data:
        crc ^= byte
    return crc

def parse_data(data):
    """Handle and concatenate fragmented messages."""
    global incomplete_message, last_received_time

    # Update last received time
    last_received_time = asyncio.get_event_loop().time()
    
    try:
        message = data.decode('utf-8', errors='ignore')
        incomplete_message += message
        
        if '\n' in incomplete_message:
            lines = incomplete_message.split('\n')
            for line in lines[:-1]:
                print(f"Complete message received: {line.strip()}")
            incomplete_message = lines[-1]
    except UnicodeDecodeError:
        print(f"Raw data received: {data.hex()}")

async def notification_handler(sender, data):
    """Handle incoming notifications."""
    global is_user_input_active
    if is_user_input_active:
        return
    parse_data(data)

async def find_device(device_name):
    """Scan and find the MakeBlock Ranger based on the provided device name."""
    devices = await BleakScanner.discover()
    for device in devices:
        if device.name == device_name:
            print(f"Device found: {device.name}, Address: {device.address}")
            return device.address

    print("Device not found.")
    return None

async def handle_disconnect(client: BleakClient):
    """Handle the peripheral disconnection and attempt to reconnect."""
    print("Peripheral device disconnected unexpectedly.")
    attempt = 1
    max_attempts = 5
    reconnect_timeout = 10

    while attempt <= max_attempts:
        print(f"Attempting to reconnect... (Attempt {attempt} of {max_attempts})")
        try:
            await asyncio.wait_for(client.connect(), timeout=reconnect_timeout)
            if client.is_connected:
                print("Reconnected successfully.")
                await client.start_notify(CHARACTERISTIC_NOTIFY_UUID, notification_handler)
                break
        except asyncio.TimeoutError:
            print(f"Reconnection attempt {attempt} timed out.")
        attempt += 1
        await asyncio.sleep(1)
    
    if not client.is_connected:
        print("Failed to reconnect after several attempts.")

async def send_data(client, data, end_data='BOTH'):
    """Send data with a header and CRC."""
    if end_data not in END_DATA_OPTIONS:
        end_data = 'BOTH'
    
    packet = bytearray([0xFF, 0x55])
    packet.extend(data)
    crc = calculate_crc(packet)
    packet.append(crc)
    packet.extend(END_DATA_OPTIONS[end_data])

    await client.write_gatt_char(CHARACTERISTIC_WRITE_UUID, packet)
    print(f"Sent: {packet.hex()}")

async def listen_for_user_input(client):
    """Listen for user input without blocking notifications."""
    global is_user_input_active

    while True:
        activation_input = await asyncio.get_event_loop().run_in_executor(None, input, "Type ':' and Enter to enter data (or 'quit' to exit): ")
        
        if activation_input.lower() == 'quit':
            break

        if activation_input == ':':
            is_user_input_active = True
            user_input = await asyncio.get_event_loop().run_in_executor(None, input, "Enter data to send (or 'quit' to exit): ")
            
            if user_input.lower() == 'quit':
                break

            is_user_input_active = False
            data_to_send = bytearray(user_input, 'utf-8')
            await send_data(client, data_to_send)

async def main():
    print("Type ':' to activate user input.")
    
    device_name = load_last_device()
    if not device_name:
        print("No saved device name found.")
        device_name = input("Enter the device name to connect to: ")
        if not device_name:
            print("No device name provided. Exiting...")
            return

    device_address = await find_device(device_name)
    if not device_address:
        print("Unable to find the device.")
        return
    save_last_device(device_name)

    try:
        async with BleakClient(device_address, timeout=30.0) as client:
            print(f"Connecté à {device_address}")
            
            global last_received_time
            last_received_time = asyncio.get_event_loop().time()

            await client.start_notify(CHARACTERISTIC_NOTIFY_UUID, notification_handler)

            user_input_task = asyncio.create_task(listen_for_user_input(client))
            await user_input_task

    except BleakError as e:
        print(f"An error occurred: {str(e)}")
    except KeyboardInterrupt:
        print("\nDisconnecting...")

# Run the main function
asyncio.run(main())
