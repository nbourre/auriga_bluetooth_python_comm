# CLI Applications

Command-line tools for scanning, identifying, and communicating with MakeBlock robots over BLE.

## Applications

### 1. scan_robots.py

**Purpose:** Scan for all available BLE devices and save MakeBlock robots to a CSV file.

**Features:**
- Discovers all BLE devices
- Filters for MakeBlock devices (prefix "Makeblock")
- Extracts MAC addresses from device names
- Saves discovered robots to `makeblock_robots.csv`
- Maintains and updates robot database

**Usage:**
```bash
python scan_robots.py
```

**Output:**
- Creates/updates `makeblock_robots.csv` with discovered robots
- Displays robot names and MAC addresses in console

**CSV Format:**
```csv
name,address
Makeblock_LE10a5622dd32e,10:a5:62:2d:d3:2e
Makeblock_LE001b10672dfc,00:1b:10:67:2d:fc
```

**Notes:**
- Automatically extracts MAC addresses from Makeblock_LE device names
- Avoids duplicate entries when robots are already in CSV
- Useful for discovering new robots or updating device database

---

### 2. identify_bots.py

**Purpose:** Identify a specific robot by sending it a beep command.

**Features:**
- Scans for MakeBlock robots
- Sends a beep command (0xFF 0x55 0x39 0x39 0x39 0x39) to each robot
- Waits between beeps to allow manual identification
- Displays robot name and MAC address when beeping

**Usage:**
```bash
python identify_bots.py
```

**How to Identify a Robot:**
1. Run the script
2. Listen for beeping sounds
3. When you hear the beep, the robot currently beeping is displayed in console
4. Note the robot name and MAC address
5. Use this information in other scripts (e.g., `makeblock_bluetooth.py`)

**Configuration:**
- **WAIT_TIME:** Time to wait after each beep (default: 10 seconds)
- **BEEP_COMMAND:** The command sent to trigger a beep (adjust if robot doesn't respond)
- **CHARACTERISTIC_WRITE_UUID:** UUID for writing to robot (default: "0000ffe3-0000-1000-8000-00805f9b34fb")

**Requirements:**
- Auriga robot must have `beep_when_found.ino` sketch uploaded (see arduino/ folder)

---

### 3. ble_logger.py

**Purpose:** Scan BLE devices and log their services and characteristics to a JSON file.

**Features:**
- Discovers all BLE devices
- Connects to each device and explores services
- Logs all services and characteristics (UUID, description, properties)
- Saves detailed device information to `device_log.json`
- Useful for debugging and discovering device APIs

**Usage:**
```bash
python ble_logger.py
```

**Output:**
- Creates `device_log.json` with detailed device information
- Displays progress in console

**JSON Structure:**
```json
[
  {
    "name": "Device Name",
    "address": "AA:BB:CC:DD:EE:FF",
    "services": [
      {
        "uuid": "service-uuid",
        "description": "Service Description",
        "characteristics": [
          {
            "uuid": "char-uuid",
            "description": "Characteristic Description",
            "properties": ["write", "notify"]
          }
        ]
      }
    ]
  }
]
```

**Use Cases:**
- Discovering characteristic UUIDs for custom devices
- Debugging BLE communication issues
- Documenting device capabilities
- Finding read/write/notify characteristics

---

### 4. makeblock_bluetooth.py

**Purpose:** Interactive terminal for communicating with a MakeBlock robot over BLE.

**Features:**
- Connect to a MakeBlock robot by name
- Send and receive messages
- Multiple line ending options (NL, CR, BOTH, NONE)
- Optional header prefix (0xFF 0x55)
- Remembers last connected device
- Real-time incoming notification display
- Keyboard-based interaction

**Usage:**
```bash
python makeblock_bluetooth.py
```

**Commands:**
- **Type and Enter:** Send message to robot
- **'q':** Quit and disconnect
- **'l':** Clear log
- **'r':** Reload last connected device
- **'+/-':** Adjust frequency (not used in basic mode)
- **Line ending menu:** Choose NL/CR/BOTH/NONE
- **Header toggle:** Enable/disable 0xFF 0x55 prefix

**Configuration:**
- **DEVICE_NAME:** Default robot name (change to your robot's name)
- **CHARACTERISTIC_NOTIFY_UUID:** UUID for receiving messages
- **CHARACTERISTIC_WRITE_UUID:** UUID for sending messages
- **END_DATA_OPTIONS:** Available line ending formats

**File Storage:**
- `last_connected_device.json` - Remembers last robot connection

**Example Session:**
```
Scanning for Makeblock robots...
Found: Makeblock_LE10a5622dd32e
Connecting to Makeblock_LE10a5622dd32e...
Connected!
> F
(Robot moves forward)
> L
(Robot turns left)
> q
Disconnected
```

---

### 5. makeblock_ble_lite.py

**Purpose:** Lightweight version of `makeblock_bluetooth.py` with minimal dependencies.

**Features:**
- Core BLE communication with reduced overhead
- Simplified interface compared to full version
- Same message sending/receiving capabilities
- Line ending support
- Header prefix support
- Last device persistence

**Usage:**
```bash
python makeblock_ble_lite.py
```

**Differences from makeblock_bluetooth.py:**
- Simpler state management
- Fewer command options
- Lighter memory footprint
- Useful for resource-constrained environments

---

### 6. auriga_firmware.py

**Purpose:** Communicate with MakeBlock Auriga using the custom firmware protocol.

**Features:**
- Support for multiple sensor types (ultrasonic, temperature, light, etc.)
- Motor and servo control
- Encoder reading
- Gyroscope and motion sensor integration
- Structured command protocol using binary encoding
- Action types: GET (read), RUN (execute)

**Usage:**
```bash
python auriga_firmware.py
```

**Supported Devices:**
- Ultrasonic Sensor (1)
- Temperature Sensor (2)
- Light Sensor (3)
- Potentiometer (4)
- Joystick (5)
- Gyroscope (6)
- Sound Sensor (7)
- RGB LED (8)
- Seven-Segment Display (9)
- Motor (10)
- Servo (11)
- Encoder (12)
- IR Receiver (13)
- IR Remote (14)
- PIR Motion Sensor (15)
- Infrared (16)

**Command Structure:**
Binary protocol with action type and sensor selection:
- **ACTION_GET (1):** Read sensor value
- **ACTION_RUN (2):** Execute device command

**Example:**
```python
# Read distance from ultrasonic sensor
await get_sensor_value(device_address, ULTRASONIC_SENSOR)

# Run motor
await run_motor(device_address, motor_index, speed)
```

**Notes:**
- Requires custom firmware on Auriga
- Uses struct module for binary encoding
- Async/await pattern for non-blocking operations

---

## Common Configuration

### BLE Characteristic UUIDs
Default MakeBlock UUIDs:
```python
CHARACTERISTIC_NOTIFY_UUID = "0000ffe2-0000-1000-8000-00805f9b34fb"  # Notifications
CHARACTERISTIC_WRITE_UUID  = "0000ffe3-0000-1000-8000-00805f9b34fb"  # Write
```

### Line Ending Options
All scripts support configurable line endings:
- **NL:** \n (0x0A) - Newline only
- **CR:** \r (0x0D) - Carriage return only
- **BOTH:** \r\n - Both (default)
- **NONE:** No line ending

### Header Prefix
Optional 2-byte header prepended to messages:
```
0xFF 0x55
```

---

## Installation

All scripts require Python 3.7+ and the `bleak` library:

```bash
pip install bleak
```

Optional (for enhanced features):
```bash
pip install asyncio
```

---

## Troubleshooting

### "No Bluetooth adapter found"
- Ensure Bluetooth is enabled on your system
- Check if Bluetooth adapter is connected
- Try restarting Bluetooth service

### "Device not found"
- Run `scan_robots.py` to verify robot is discoverable
- Check if robot is powered on
- Ensure robot Bluetooth is not already connected

### "Cannot write to characteristic"
- Verify CHARACTERISTIC_WRITE_UUID is correct for your device
- Use `ble_logger.py` to discover correct UUIDs
- Check if device is connected

### Garbled received messages
- Check line ending setting matches device output
- Verify received data encoding (UTF-8 vs binary)
- Use `ble_logger.py` to inspect characteristic properties

---

## Related Documentation

- [Main README](../README.md)
- [GUI Applications](../gui_apps/README.md)
- [Arduino Sketches](../arduino/README.md)
- [Bleak Documentation](https://bleak.readthedocs.io/)
