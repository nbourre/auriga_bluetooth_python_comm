from bleak import BleakScanner
import asyncio
import csv
import os

async def scan_devices():
    devices = await BleakScanner.discover()
    device_dict = {device.name: device.address for device in devices if device.name}
    return device_dict

def filter_makeblock_devices(device_dict):
    return {name: address for name, address in device_dict.items() if name.startswith("Makeblock")}

def save_robots_to_csv(robot_dict, file_name="makeblock_robots.csv"):
    file_exists = os.path.isfile(file_name)
    
    existing_robots = set()
    if file_exists:
        with open(file_name, mode='r', newline='') as file:
            reader = csv.reader(file)
            next(reader)  # Skip the header
            for row in reader:
                if len(row) == 2:
                    existing_robots.add((row[0], row[1]))

    with open(file_name, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['name', 'mac_address'])
        
        for name, address in robot_dict.items():
            if (name, address) not in existing_robots:
                writer.writerow([name, address])

async def main():
    all_devices = await scan_devices()
    makeblock_devices = filter_makeblock_devices(all_devices)
    
    print("All Devices:")
    for name, address in all_devices.items():
        print(f"Device Name: {name}, MAC Address: {address}")
    
    print("\nFiltered Makeblock Devices:")
    for name, address in makeblock_devices.items():
        print(f"Device Name: {name}, MAC Address: {address}")

    # Save Makeblock devices to CSV
    save_robots_to_csv(makeblock_devices)

# Run the main function
asyncio.run(main())
