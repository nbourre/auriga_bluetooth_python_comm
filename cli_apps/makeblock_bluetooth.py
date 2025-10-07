import asyncio
import struct
import sys
import platform
import json
from bleak import BleakClient, BleakScanner, BleakError

# Configuration Bluetooth
DEVICE_NAME = "Makeblock_LE10a5622dd32e"
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

# Global variables
is_user_input_active = False
incomplete_message = ""
last_received_time = None

def load_last_device():
    """Load the last connected device name from a JSON file."""
    try:
        with open(DEVICE_FILE, 'r') as f:
            data = json.load(f)
            return data.get(DEVICE_NAME_KEY)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def save_last_device(device_name):
    """Save the last connected device name to a JSON file."""
    with open(DEVICE_FILE, 'w') as f:
        json.dump({DEVICE_NAME_KEY: device_name}, f)

def calculate_crc(data):
    """Calcule le CRC en effectuant un XOR de tous les octets."""
    crc = 0
    for byte in data:
        crc ^= byte
    return crc

def parse_data(data):
    """Handle and concatenate fragmented messages."""
    global incomplete_message

    try:
        # Update the last received time to the current time when data is received
        last_received_time = asyncio.get_event_loop().time()
        
        # Decode the received data to string
        message = data.decode('utf-8', errors='ignore')
        incomplete_message += message
        
        # Look for complete messages that end with a newline character
        if '\n' in incomplete_message:
            # Split the message on newline to get complete chunks
            lines = incomplete_message.split('\n')
            
            # Process all but the last (possibly incomplete) part
            for line in lines[:-1]:
                #print(f"Message série complet : {line.strip()}")
                print(f"{line.strip()}")
            
            # Keep the last segment as incomplete if it doesn't end with a newline
            incomplete_message = lines[-1]
    except UnicodeDecodeError:
        print(f"Données brutes reçues : {data.hex()}")



async def notification_handler(sender, data):
    """Gère les notifications entrantes en envoyant les données à parseData."""
    global is_user_input_active

    if is_user_input_active:
        return  # Skip handling if user input is active
  
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
    #FIXME : Doesn't reconnect
    attempt = 1
    max_attempts = 5
    connected = False
    reconnect_timeout = 10  # Timeout duration in seconds
    
    # Attempt to reconnect a few times
    while attempt <= max_attempts:
        print(f"Attempting to reconnect... (Attempt {attempt} of {max_attempts})")
        try:
            await asyncio.wait_for(client.connect(), timeout=reconnect_timeout)
            if client.is_connected:
                print("Reconnected successfully.")
                connected = True
                await client.start_notify(CHARACTERISTIC_NOTIFY_UUID, notification_handler)
                break
        except asyncio.TimeoutError:
            print(f"Reconnection attempt {attempt} timed out.")
        except BleakError as e:
            print(f"Reconnection attempt {attempt} failed: {e}")
        except Exception as e:
            print(f"Unexpected error during reconnection attempt {attempt}: {e}")

        attempt += 1
        await asyncio.sleep(1)  # Small delay between attempts

    if not connected:
        print("Failed to reconnect after several attempts. Exiting...")

async def check_connection(client: BleakClient):
    """Periodically check the connection status."""
    try:
        while True:
            await asyncio.sleep(5)
            if not client.is_connected:
                raise BleakError("Device disconnected")
    except BleakError:
        await handle_disconnect(client)


async def check_connection(client: BleakClient):
    """Periodically check the connection status."""
    try:
        while True:
            # Attempt a simple read or write operation to verify connection
            await asyncio.sleep(5)  # Check every 5 seconds
            if not client.is_connected:
                raise BleakError("Device disconnected")
    except BleakError:
        await handle_disconnect(client)

async def check_disconnection(client):
    """Periodically check for disconnection based on data reception time."""
    global last_received_time

    while True:
        await asyncio.sleep(1)
        
        if last_received_time and (asyncio.get_event_loop().time() - last_received_time) > DISCONNECTION_TIMEOUT:
            print(f"No data received for {DISCONNECTION_TIMEOUT} seconds. Disconnecting...")
            await client.disconnect()
            break

async def send_data(client, data, end_data='BOTH'):
    """Envoie des données au robot avec un en-tête et un CRC."""
    if end_data not in END_DATA_OPTIONS:
        end_data = 'BOTH'
    
    packet = bytearray([0xFF, 0x55])
    packet.extend(data)
    crc = calculate_crc(packet)
    packet.append(crc)
    packet.extend(END_DATA_OPTIONS[end_data])

    await client.write_gatt_char(CHARACTERISTIC_WRITE_UUID, packet)
    print(f"Envoyé : {packet.hex()}")

async def listen_for_user_input(client):
    """Écouter les entrées utilisateur sans bloquer la réception des notifications."""
    global is_user_input_active

    while True:
        # Prompt the user to activate input mode
        activation_input = await asyncio.get_event_loop().run_in_executor(None, input, "Tapez ':' puis Entrée pour entrer des données (ou 'quit' pour quitter) :\n")
        
        if activation_input.lower() == 'quit':
            break

        if activation_input == ':':
            is_user_input_active = True

            # Demander l'entrée de l'utilisateur
            user_input = await asyncio.get_event_loop().run_in_executor(None, input, "Entrez des données à envoyer (ou 'quit' pour quitter) : ")
            
            if user_input.lower() == 'quit':
                break

            is_user_input_active = False

            # Envoyer les données saisies par l'utilisateur au robot
            data_to_send = bytearray(user_input, 'utf-8')
            await send_data(client, data_to_send)

async def main():
    print("Tapez ':' pour activer l'entrée utilisateur.")
    
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

            # Créer une tâche pour vérifier la connexion
            user_input_task = asyncio.create_task(listen_for_user_input(client))

            connection_check_task = asyncio.create_task(check_connection(client))

            # Garder la connexion active en attendant les notifications et la déconnexion
            await user_input_task

    except BleakError as e:
        print(f"An error occurred: {str(e)}")
    except KeyboardInterrupt:
        print("\nDéconnexion en cours...")


# Exécuter la fonction principale
asyncio.run(main())
