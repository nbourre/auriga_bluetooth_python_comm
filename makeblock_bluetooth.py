import asyncio
import struct
import sys
from bleak import BleakClient

# Configuration Bluetooth
DEVICE_ADDRESS = "5F412FC3-B013-FB3D-9B7B-3D7370B5BDE7"  # Remplacez par l'adresse Bluetooth de votre MakeBlock Ranger
CHARACTERISTIC_NOTIFY_UUID = "0000ffe2-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_WRITE_UUID = "0000ffe3-0000-1000-8000-00805f9b34fb"

# Options de données de fin
END_DATA_OPTIONS = {
    'NL': b'\n',  # Nouvelle ligne (0x0A)
    'CR': b'\r',  # Retour chariot (0x0D)
    'BOTH': b'\r\n',  # CR + NL
    'NONE': b''  # Pas de données de fin
}

# Global flag to control notification printing
is_user_input_active = False

'''
TODO :
  - Concaténer les messages textes jusqu'à la fin de la ligne
  - Trouver comment avoir le chrono des tâches (équivalent du millis() en Arduino)
  - Ajouter la sauvegarde des données dans un fichier
  - Sauvegarder le dernier appareil connecté dans un fichier json pour une reconnexion automatique
'''

def calculate_crc(data):
    """Calcule le CRC en effectuant un XOR de tous les octets."""
    crc = 0
    for byte in data:
        crc ^= byte
    return crc

def parse_data(data):
    """Analyse les données reçues du robot (pour l'instant, les affiche simplement)."""
    print(f"Données brutes reçues : {data.hex()}")

async def notification_handler(sender, data):
    """Gère les notifications entrantes en envoyant les données à parseData."""
    
    """Gère les notifications entrantes en envoyant les données à parseData."""
    global is_user_input_active

    if is_user_input_active:
        return  # Skip handling if user input is active
    
    try:
        # Tentative de décodage des données en texte pour détecter les messages Serial.print
        message = data.decode('utf-8').strip()
        if message:
            print(f"Message série : {message}")
            return
    except UnicodeDecodeError:
        # Si les données ne sont pas du texte, continuer le traitement normal
        pass
    
    parse_data(data)

async def send_data(client, data, end_data='BOTH'):
    """
    Envoie des données au robot avec un en-tête et un CRC.
    
    Paramètres :
    - client : Instance de BleakClient.
    - data : Bytearray des données à envoyer.
    - end_data : Clé de chaîne optionnelle pour sélectionner les données de fin (NL, CR, BOTH ou NONE).
    """
    if end_data not in END_DATA_OPTIONS:
        end_data = 'BOTH'  # Par défaut à BOTH si l'option fournie est invalide
    
    # Construire le paquet complet avec en-tête, données, CRC et données de fin
    packet = bytearray([0xFF, 0x55])  # En-tête
    packet.extend(data)  # Données principales
    crc = calculate_crc(packet)  # Calculer le CRC
    packet.append(crc)  # Ajouter l'octet de CRC
    packet.extend(END_DATA_OPTIONS[end_data])  # Ajouter les données de fin sélectionnées

    # Écrire le paquet dans la caractéristique
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
            is_user_input_active = True  # Set the flag to pause notifications
            
            # Demander l'entrée de l'utilisateur
            user_input = await asyncio.get_event_loop().run_in_executor(None, input, "Entrez des données à envoyer (ou 'quit' pour quitter) : ")
            
            if user_input.lower() == 'quit':
                break

            is_user_input_active = False  # Clear the flag after processing input

            # Envoyer les données saisies par l'utilisateur au robot
            data_to_send = bytearray(user_input, 'utf-8')
            await send_data(client, data_to_send)

async def main():
    print("Tapez ':' pour activer l'entrée utilisateur.")
    async with BleakClient(DEVICE_ADDRESS) as client:
        print(f"Connecté à {DEVICE_ADDRESS}")

        # S'abonner aux notifications
        await client.start_notify(CHARACTERISTIC_NOTIFY_UUID, notification_handler)

        try:
            print("En attente de notifications... (Appuyez sur Ctrl+C pour arrêter)")

            # Créer une tâche pour écouter les entrées utilisateur
            user_input_task = asyncio.create_task(listen_for_user_input(client))

            # Garder la connexion active en attendant les notifications
            await user_input_task

        except KeyboardInterrupt:
            print("\nDéconnexion en cours...")
        finally:
            await client.stop_notify(CHARACTERISTIC_NOTIFY_UUID)
            print("Déconnecté.")

# Exécuter la fonction principale
asyncio.run(main())
