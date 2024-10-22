import asyncio
from bleak import BleakClient

# Replace with your MakeBlock Ranger's Bluetooth address
DEVICE_ADDRESS = "00:1B:10:FA:FB:43"
CHARACTERISTIC_NOTIFY_UUID = "0000ffe2-0000-1000-8000-00805f9b34fb"  # UUID for notifications
CHARACTERISTIC_WRITE_UUID = "0000ffe3-0000-1000-8000-00805f9b34fb"  # UUID for writing

# Helper function to construct the command based on the updated structure
def construct_command(idx, action, device, port, slot, data=None):
    command = bytearray([0xFF, 0x55])
    data_len = 5 + (len(data) if data else 0)
    command.append(data_len)
    command.append(idx)
    command.append(action)
    command.append(device)
    command.append(port)
    command.append(slot)
    if data:
        command.extend(data)
    return command

# Handler to print received notifications
def notification_handler(sender, data):
    print(f"Notification from {sender}: {data.hex()}")

async def main():
    async with BleakClient(DEVICE_ADDRESS) as client:
        print(f"Connected to {DEVICE_ADDRESS}")

        # Subscribe to notifications
        await client.start_notify(CHARACTERISTIC_NOTIFY_UUID, notification_handler)
        
        # Command to run the motor forward (index=1, action=2 for RUN, device=61 for motor, port=0, slot=1)
        forward_command = construct_command(
            idx=1,
            action=2,  
            device=61,  
            port=0,    
            slot=2,    
            data=[0]  
        )

        # Write the command to the characteristic
        await client.write_gatt_char(CHARACTERISTIC_WRITE_UUID, forward_command)
        print(f"Sent forward command: {forward_command.hex()}")

        # Keep the connection alive to receive notifications
        await asyncio.sleep(10)
        await client.stop_notify(CHARACTERISTIC_NOTIFY_UUID)

# Run the main function
asyncio.run(main())
