'''
Test code to communicate with the MakeBlock Ranger with the Firmware_for_Auriga sketch over Bluetooth Low Energy (BLE) using the Bleak library
'''

import asyncio
import struct
from bleak import BleakClient

# Constants for Actions
ACTION_GET = 1  # GET action
ACTION_RUN = 2  # RUN action

# Constants for Sensors and Devices
VERSION = 0
ULTRASONIC_SENSOR = 1
TEMPERATURE_SENSOR = 2
LIGHT_SENSOR = 3
POTENTIOMETER = 4
JOYSTICK = 5
GYRO = 6
SOUND_SENSOR = 7
RGBLED = 8
SEVSEG = 9
MOTOR = 10
SERVO = 11
ENCODER = 12
IR = 13
IRREMOTE = 14
PIRMOTION = 15
INFRARED = 16
LINEFOLLOWER = 17
IRREMOTECODE = 18
SHUTTER = 20
LIMITSWITCH = 21
BUTTON = 22
HUMITURE = 23
FLAMESENSOR = 24
GASSENSOR = 25
COMPASS = 26
TEMPERATURE_SENSOR_1 = 27
DIGITAL = 30
ANALOG = 31
PWM = 32
SERVO_PIN = 33
TONE = 34
BUTTON_INNER = 35
ULTRASONIC_ARDUINO = 36
PULSEIN = 37
STEPPER = 40
LEDMATRIX = 41
TIMER = 50
TOUCH_SENSOR = 51
JOYSTICK_MOVE = 52
COMMON_COMMONCMD = 60
ENCODER_BOARD = 61
ENCODER_PID_MOTION = 62
PM25SENSOR = 63
SMARTSERVO = 64

# Ports
PORT_1 = 1
PORT_2 = 2
PORT_3 = 3
PORT_4 = 4
PORT_10 = 10

# Replace with your MakeBlock Ranger's Bluetooth address
DEVICE_ADDRESS = "10:A5:62:0A:24:E7"
CHARACTERISTIC_NOTIFY_UUID = "0000ffe2-0000-1000-8000-00805f9b34fb"  # UUID for notifications
CHARACTERISTIC_WRITE_UUID = "0000ffe3-0000-1000-8000-00805f9b34fb"  # UUID for writing
CHARACTERISTIC_READ_UUID = "0000ffe5-0000-1000-8000-00805f9b34fb"  # Example for read characteristic
CHARACTERISTIC_INDICATE_UUID = "0000ffe4-0000-1000-8000-00805f9b34fb"  # Example for indication characteristic

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
def construct_command(idx, action, device, port=None, slot=None, data=None):
    """
    Constructs a command for the MakeBlock device.

    Parameters:
        idx (int): Index or identifier for this command.
        action (int): Action to perform (e.g., GET, RUN).
        device (int): Device identifier.
        port (int, optional): Port number. Defaults to None.
        slot (int, optional): Slot number. Defaults to None.
        data (list or bytearray, optional): Additional data bytes. Defaults to None.

    Returns:
        bytearray: The constructed command as a bytearray.
    """
    # Start with the header
    command = bytearray([0xFF, 0x55])
    
    # Calculate the length dynamically based on provided parameters
    length = 3  # Starts with idx, action, device
    if port is not None:
        length += 1
    if slot is not None:
        length += 1
    if data:
        length += len(data)
    
    # Add length to the command
    command.append(length)
    
    # Add core parameters
    command.append(idx)
    command.append(action)
    command.append(device)

    # Add optional port and slot if provided
    if port is not None:
        command.append(port)
    if slot is not None:
        command.append(slot)

    # Add additional data if provided
    if data:
        command.extend(data)

    return command

# Handler for incoming notifications
def notification_handler(sender, data):
    try:
        # Attempt to decode data as text to detect any Serial.print messages
        message = data.decode('utf-8').strip()
        if message:
            print(f"Serial message: {message}")
            return
    except UnicodeDecodeError:
        # If data is not text, continue processing as usual
        pass
    
    # Print received data for debugging
    print(f"Raw data received: {data.hex()}")

    if data == b'\xff\x55\x0d\x0a':
        print("Received callOK acknowledgment")
        
    # Check if the data starts with the expected header and contains enough bytes for a float
    elif data[:2] == b'\xff\x55' and len(data) >= 8:
        # Extract the type byte to determine the data format
        index_byte = data[2]
        data_type = data[3]

        if data_type == 2 or (data_type == 1 and index_byte == 1):
            # Extract the 4 bytes that represent the float
            float_bytes = data[4:8]
            # Convert the bytes into a float using struct.unpack
            distance = struct.unpack('<f', float_bytes)[0]
            print(f"Received Distance: {distance:.2f} cm")
        else:
            print(f"Unexpected data type or index: index={index_byte}, type={data_type}")
    else:
        print(f"Unexpected data format: {data.hex()}")

async def main():
    async with BleakClient(DEVICE_ADDRESS) as client:
        print(f"Connected to {DEVICE_ADDRESS}")

        # Subscribe to notifications
        await client.start_notify(CHARACTERISTIC_NOTIFY_UUID, notification_handler)
        
        # # Command to run the motor forward (index=1, action=2 for RUN, device=61 for motor, port=0, slot=1)
        # command = construct_command(
        #     idx=1,
        #     action=2,  
        #     device=61,  
        #     port=0,    
        #     slot=2,    
        #     data=[12]  
        # )
        
        # # Command to reset the Auriga
        # reset_command = construct_command(
        #     idx=1,
        #     action=4,
        #     device=61,
        #     port=0,
        #     slot=2
        # )
        
        # command = construct_command(
        #     idx=1,
        #     action=ACTION_GET,
        #     device=DEVICE_ULTRASONIC_SENSOR,
        #     port=PORT_10
        # )
        
        # Command to set the RGB LED to purple        
        command = construct_command(
            idx=1,
            action=2,  
            device=8,  
            port=0,    
            slot=1,
            data=[10, 20, 0, 20]  # RGB values for purple
        )


        # Write the command to the characteristic
        await client.write_gatt_char(CHARACTERISTIC_WRITE_UUID, command)
        print(f"Sent command: {command.hex()}")

        try:
            print("Waiting for notifications... (Press Ctrl+C to stop)")
            while True:
                # Keep the connection alive to receive notifications
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("Disconnecting...")
            await client.stop_notify(CHARACTERISTIC_NOTIFY_UUID)
        

# Run the main function
asyncio.run(main())
