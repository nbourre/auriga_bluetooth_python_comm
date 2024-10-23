import asyncio
from bleak import BleakClient

# Constants for Actions
ACTION_GET = 1  # GET action
ACTION_RUN = 2  # RUN action

# Constants for Devices
DEVICE_ULTRASONIC_SENSOR = 1
DEVICE_MOTOR = 10
DEVICE_RGBLED = 8
DEVICE_ENCODER_BOARD = 61

# Ports
PORT_1 = 1
PORT_2 = 2
PORT_3 = 3
PORT_4 = 4
PORT_10 = 10

# Replace with your MakeBlock Ranger's Bluetooth address
DEVICE_ADDRESS = "00:1B:10:FA:FB:43"
CHARACTERISTIC_NOTIFY_UUID = "0000ffe2-0000-1000-8000-00805f9b34fb"  # UUID for notifications
CHARACTERISTIC_WRITE_UUID = "0000ffe3-0000-1000-8000-00805f9b34fb"  # UUID for writing

'''
From the MakeBlock Ranger's firmware code
 * \par Function
 *    parseData
 * \par Description
 *    This function use to process the data from the serial port,
 *    call the different treatment according to its action.
 *    ff 55 len idx action device port  slot  data a
 *    0  1  2   3   4      5      6     7     8
'''
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
        
    print(f"Data length: {data_len}")
    return command

# # Helper function to construct the command based on the updated structure
# def construct_command(idx, action, device, port, slot, led_index, colors):
#     # Start with the header: 0xff 0x55
#     command = bytearray([0xFF, 0x55])
    
#     # Calculate the length of the command (after length byte)
#     data_len = 7 + len(colors)  # 7 = idx + action + device + port + slot + index
    
#     # Add the length field
#     command.append(data_len)
    
#     # Append idx, action, device, port, slot, and led_index
#     command.append(idx)
#     command.append(action)
#     command.append(device)
#     command.append(port)
#     command.append(slot)
#     command.append(led_index)
    
#     # Add color values (R, G, B)
#     command.extend(colors)
    
#     return command

# Handler for incoming notifications
def notification_handler(sender, data):
    # Check if the received data matches the "callOK" acknowledgment pattern
    if data == b'\xff\x55':
        print("Received callOK acknowledgment")
    else:
        print(f"Received data: {data.hex()} from {sender}")

async def main():
    async with BleakClient(DEVICE_ADDRESS) as client:
        print(f"Connected to {DEVICE_ADDRESS}")

        # Subscribe to notifications
        await client.start_notify(CHARACTERISTIC_NOTIFY_UUID, notification_handler)
        
        # # Command to run the motor forward (index=1, action=2 for RUN, device=61 for motor, port=0, slot=1)
        # forward_command = construct_command(
        #     idx=1,
        #     action=2,  
        #     device=61,  
        #     port=0,    
        #     slot=2,    
        #     data=[12]  
        # )
        
        # reset_command = construct_command(
        #     idx=1,
        #     action=4,
        #     device=61,
        #     port=0,
        #     slot=2
        # )
                
        led_command = construct_command(
            idx=1,
            action=2,  
            device=8,  
            port=0,    
            slot=1,
            data=[8, 0, 25, 0]  # RGB values for purple
        )

        # Write the command to the characteristic
        await client.write_gatt_char(CHARACTERISTIC_WRITE_UUID, led_command)
        print(f"Sent command: {led_command.hex()}")

        # Keep the connection alive to receive notifications
        await asyncio.sleep(10)
        await client.stop_notify(CHARACTERISTIC_NOTIFY_UUID)

# Run the main function
asyncio.run(main())
