import asyncio
import json
from bleak import BleakScanner, BleakClient, BleakError
import os
import time

async def scan_devices():
    """Scan for BLE devices and return a list of discovered devices."""
    print("Scanning for BLE devices...")
    devices = await BleakScanner.discover()
    found_devices = [{"name": device.name, "address": device.address} for device in devices]
    print(f"Found {len(found_devices)} device(s).")
    return found_devices

async def explore_device(device, retry_attempts=3):
    """Connect to a BLE device and explore its services and characteristics."""
    device_info = {"name": device["name"], "address": device["address"], "services": []}

    for attempt in range(retry_attempts):
        try:
            async with BleakClient(device["address"], timeout=30.0) as client:
                print(f"Connected to {device['name']} ({device['address']})")

                # Get all services and characteristics
                services = await client.get_services()
                for service in services:
                    service_info = {
                        "uuid": service.uuid,
                        "description": service.description,
                        "characteristics": []
                    }

                    # Get characteristics of this service
                    for characteristic in service.characteristics:
                        characteristic_info = {
                            "uuid": characteristic.uuid,
                            "properties": characteristic.properties,
                        }

                        if "read" in characteristic.properties:
                            try:
                                value = await client.read_gatt_char(characteristic.uuid)
                                characteristic_info["value"] = value.hex() if isinstance(value, bytes) else str(value)
                            except Exception as e:
                                characteristic_info["value"] = f"Could not read: {str(e)}"

                        service_info["characteristics"].append(characteristic_info)

                    device_info["services"].append(service_info)

                return device_info  # Successfully connected and explored services
        except BleakError as e:
            print(f"Connection attempt {attempt + 1} failed: {e}")
            time.sleep(1)  # Wait a bit before retrying

    print(f"Could not explore device {device['name']} ({device['address']}): Max retries reached.")
    return device_info

def load_existing_data(filename):
    """Load existing data from the JSON file if it exists."""
    if os.path.exists(filename):
        with open(filename, "r") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return []  # Return an empty list if the file is corrupted or empty
    return []

async def main():
    # File where the data will be saved
    json_filename = "ble_devices_info.json"
    
    # Step 1: Scan for devices
    found_devices = await scan_devices()
    
    # Load existing data from the JSON file
    all_devices_info = load_existing_data(json_filename)

    # Step 2: Explore each discovered device
    for device in found_devices:
        if device["name"]:
            print(f"Exploring device {device['name']}...")
            device_info = await explore_device(device)
            # Check if the device already exists in the data
            if not any(d["address"] == device_info["address"] for d in all_devices_info):
                all_devices_info.append(device_info)
        else:
            print(f"Skipping unnamed device ({device['address']})")

    # Step 3: Save to JSON file (append new devices)
    with open(json_filename, "w") as json_file:
        json.dump(all_devices_info, json_file, indent=4)
    
    print(f"Device information logged to '{json_filename}'.")

# Run the main function
asyncio.run(main())
