from bleak import BleakScanner
import asyncio
import csv
import os
import platform

async def scan_devices():
    devices = await BleakScanner.discover()
    device_dict = {device.name: device.address for device in devices if device.name}
    return device_dict

def filter_makeblock_devices(device_dict):
    return {name: address for name, address in device_dict.items() if name.startswith("Makeblock")}

def get_mac_address_from_name(robot_name):
    """Extracts and returns the MAC address from the given robot name."""
    if robot_name.startswith("Makeblock_LE"):
        # Extract the MAC address part after 'Makeblock_LE' and insert colons
        embedded_mac = robot_name[len("Makeblock_LE"):]
        # Format MAC address as 'XX:XX:XX:XX:XX:XX'
        mac_address = ':'.join(embedded_mac[i:i+2] for i in range(0, len(embedded_mac), 2))
        return mac_address
    return None

def save_robots_to_csv(robot_dict, file_name="makeblock_robots.csv"):
    file_exists = os.path.isfile(file_name)
    
    # Read existing robots into a dictionary for easier updating
    existing_robots = {}
    if file_exists:
        with open(file_name, mode='r', newline='') as file:
            reader = csv.reader(file)
            next(reader)  # Skip the header
            for row in reader:
                name, mac_address, macos_id, robot_id = row
                existing_robots[name] = {
                    "mac_address": mac_address,
                    "macos_id": macos_id,
                    "id": robot_id
                }

    # Update or add robots to the CSV file
    with open(file_name, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['name', 'mac_address', 'macos_id', 'id'])  # Write header

        # Merge new robots with existing ones
        for name, address in robot_dict.items():
            if name in existing_robots:
                # Update `mac_address` or `macos_id` only if missing or different
                if platform.system() == 'Darwin':
                    existing_robots[name]['macos_id'] = address
                    # If `mac_address` is missing, extract it from the name
                    if not existing_robots[name]['mac_address']:
                        existing_robots[name]['mac_address'] = get_mac_address_from_name(name)
                else:
                    existing_robots[name]['mac_address'] = address
            else:
                # Add new robots based on platform
                if platform.system() == 'Darwin':
                    mac_address = get_mac_address_from_name(name)
                    existing_robots[name] = {"mac_address": mac_address, "macos_id": address, "id": ""}
                else:
                    existing_robots[name] = {"mac_address": address, "macos_id": "", "id": ""}

        # Write all entries to the CSV file
        for name, info in existing_robots.items():
            writer.writerow([name, info["mac_address"], info["macos_id"], info["id"]])


async def main():
    all_devices = await scan_devices()
    makeblock_devices = filter_makeblock_devices(all_devices)
    
    print("All Devices:")
    for name, address in all_devices.items():
        print(f"Device Name: {name}, MAC Address: {address}")
    
    print("\nFiltered Makeblock Devices:")
    for name, address in makeblock_devices.items():
        print(f"Device Name: {name}, MAC Address: {address}")

    # Save Makeblock devices to CSV with id column
    save_robots_to_csv(makeblock_devices)

# Run the main function
asyncio.run(main())
