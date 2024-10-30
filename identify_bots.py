'''Ce script s'utilise avec le script arduino "beep_when_found.ino" pour trouver un appareil Bluetooth et lui envoyer des données.'''

import asyncio
from bleak import BleakScanner, BleakClient

# Configuration
MAKEBLOCK_PREFIX = "Makeblock_LE"
BEEP_COMMAND = bytearray([0xFF, 0x55, 0x39, 0x39, 0x39, 0x39])  # Example beep command (adjust if needed)
WAIT_TIME = 3  # Time in seconds to wait after each beep
CHARACTERISTIC_WRITE_UUID = "0000ffe3-0000-1000-8000-00805f9b34fb"  # UUID for writing

async def beep_robot(address, name):
    """Connect to a robot, send a beep command, and wait for a response."""
    async with BleakClient(address) as client:
        if client.is_connected:
            print(f"Connected to {name} ({address}). Sending beep command...")
            await client.write_gatt_char(CHARACTERISTIC_WRITE_UUID, BEEP_COMMAND)
            print(f"Beep sent to {name}. Waiting for {WAIT_TIME} seconds...")
            await asyncio.sleep(WAIT_TIME)
            print(f"Robot name: {name}, MAC address: {address}")

async def scan_and_beep():
    """Scan for all Makeblock robots and beep each one."""
    print("Scanning for Makeblock robots...")
    devices = await BleakScanner.discover()
    makeblock_robots = [device for device in devices if device.name and device.name.startswith(MAKEBLOCK_PREFIX)]

    if not makeblock_robots:
        print("No Makeblock robots found.")
        return

    for robot in makeblock_robots:
        try:
            await beep_robot(robot.address, robot.name)
        except Exception as e:
            print(f"Failed to beep {robot.name} ({robot.address}): {e}")

async def main():
    await scan_and_beep()

# Run the main function
asyncio.run(main())
