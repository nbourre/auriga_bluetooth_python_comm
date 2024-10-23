import asyncio
import struct
import sys
import platform
import json
from bleak import BleakClient, BleakScanner

# Configuration Bluetooth
DEVICE_NAME = "Makeblock_LE001b10672dfc"
DEVICE_FILE = "last_connected_device.json"
CHARACTERISTIC_NOTIFY_UUID = "0000ffe2-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_WRITE_UUID = "0000ffe3-0000-1000-8000-00805f9b34fb"

# Options de données de fin
END_DATA_OPTIONS = {
    'NL': b'\n',  # Nouvelle ligne (0x0A)
    'CR': b'\r',  # Retour chariot (0x0D)
    'BOTH': b'\r\n',  # CR + NL
    'NONE': b''  # Pas de données de fin
}

# Global variables
is_user_input_active = False
incomplete_message = b''

def load_last_device():
    """Load the last connected device from a JSON file."""
    try:
        with open(DEVICE_FILE, 'r') as f:
            data = json.load(f)
            return data.get("device_address")
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def save_last_device(device_address):
    """Save the last connected device to a JSON file."""
    with open(DEVICE_FILE, 'w') as f:
        json.dump({"device_address": device_address}, f)

def calculate_crc(data):
    """Calcule le CRC en effectuant un XOR de tous les octets."""
    crc = 0
    for byte in data:
        crc ^= byte
    return crc

def parse_data(data):
    """Analyse les données reçues du robot (pour l'instant, les affiche simplement)."""
    global incomplete_message

    # Concatenate with any previous incomplete message
    data = incomplete_message + data
    lines = data.split(b'\n')

    # Process each line except the last (it might be incomplete)
    for line in lines[:-1]:
        print(f"Données reçues : {line.hex()}")

    # Keep the last line as an incomplete message if it's not complete
    incomplete_message = lines[-1]

async def notification_handler(sender, data):
    """Gère les notifications entrantes en envoyant les données à parseData."""
    global is_user_input_active

    if is_user_input_active:
        return  # Skip handling if user input is active

    try:
        message = data.decode('utf-8').strip()
        if message:
            print(f"Message série : {message}")
            return
    except UnicodeDecodeError:
        pass
    
    parse_data(data)

async def find_device():
    """Scan and find the MakeBlock Ranger based on the OS."""
    devices = await BleakScanner.discover()
    for device in devices:
        if platform.system() == "Darwin":  # Check if it's macOS
            if device.name == DEVICE_NAME:
                print(f"Device found on macOS: {device.name}, UUID: {device.address}")
                return device.address
        else:
            if device.name == DEVICE_NAME and ":" in device.address:  # Match MAC address on Windows
                print(f"Device found on Windows: {device.name}, MAC: {device.address}")
                return device.address

    print("Device not found.")
    return None

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
        activation_input = await asyncio.get_event_loop().run_in_executor(None, input, "Tapez ':' puis Entrée pour entrer des données (ou 'quit' pour quitter) : ")
        
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
    
    device_address = load_last_device()
    if not device_address:
        device_address = await find_device()
        if not device_address:
            print("Unable to find the device.")
            return
        save_last_device(device_address)

    async with BleakClient(device_address) as client:
        print(f"Connecté à {device_address}")

        await client.start_notify(CHARACTERISTIC_NOTIFY_UUID, notification_handler)

        try:
            print("En attente de notifications... (Appuyez sur Ctrl+C pour arrêter)")

            user_input_task = asyncio.create_task(listen_for_user_input(client))

            await user_input_task

        except KeyboardInterrupt:
            print("\nDéconnexion en cours...")
        finally:
            await client.stop_notify(CHARACTERISTIC_NOTIFY_UUID)
            print("Déconnecté.")

# Exécuter la fonction principale
asyncio.run(main())
