# Arduino Sketches

This folder contains Arduino sketches for the MakeBlock Auriga robot, enabling BLE communication and firmware interaction.

## Sketches

### 1. auriga_ble_test

**Location:** `auriga_ble_test/auriga_ble_test.ino`

**Purpose:** Test sketch for communicating with the MakeBlock Auriga robot over BLE using the custom firmware.

**Features:**
- Buzzer control via pin 45
- LED ring control via pin 44 (12 LEDs)
- Serial event parsing for incoming BLE data
- State manager for handling robot tasks
- Communication task interface

**Hardware Requirements:**
- MakeBlock Auriga robot
- Buzzer connected to pin 45
- LED ring connected to pin 44

**How to Use:**
1. Upload the sketch to your MakeBlock Auriga using Arduino IDE
2. Use the Python CLI or GUI apps to send commands over BLE
3. The sketch parses incoming serial data and executes commands

**Dependencies:**
- `MeAuriga.h` library (included with MakeBlock)

**Baud Rate:** 115200

---

### 2. beep_when_found

**Location:** `beep_when_found/beep_when_found.ino`

**Purpose:** Simple utility sketch for identifying a robot by sending a beep command.

**Features:**
- Listens for a specific BLE command pattern (0xFF 0x55 followed by "9999")
- Triggers a buzzer tone when the pattern is detected
- Echo the received command back via serial for debugging

**Hardware Requirements:**
- MakeBlock Auriga robot
- Buzzer connected to pin 45

**How to Use:**
1. Upload this sketch to your MakeBlock Auriga
2. Run the Python `identify_bots.py` script to scan and beep all robots
3. Listen for the beep to identify which robot responds

**Command Format:**
```
Header: 0xFF 0x55
Data: "9999"
```

**Buzzer Specifications:**
- Frequency: 1000 Hz
- Duration: 200 ms

**Baud Rate:** 115200

---

## Communication Protocol

### Default Header
Most sketches use the header:
```
0xFF 0x55
```

### Serial Configuration
- **Baud Rate:** 115200
- **Data Bits:** 8
- **Stop Bits:** 1
- **Parity:** None

### Command Structure
```
[HEADER] [DATA] [LINE_ENDING]
```

- **HEADER** (optional): 0xFF 0x55
- **DATA**: Command or sensor data
- **LINE_ENDING**: \n, \r, \r\n, or none (configurable)

---

## Python Integration

### Uploading Sketches
Use Arduino IDE or command-line tools:
```bash
arduino-cli upload --fqbn makeblockofficial:mbot_ranger_audriga:ranger_auriga <sketch_name>
```

### Communicating with Sketches
Use any of the Python CLI or GUI apps:
- **cli_apps/scan_robots.py** - Find connected robots
- **cli_apps/identify_bots.py** - Identify specific robots by beeping
- **gui_apps/gui_ble.py** - Basic communication
- **gui_apps/gui_ble_wasd.py** - Keyboard-controlled movement

---

## Troubleshooting

### Sketch Won't Upload
- Check USB connection
- Verify correct board selection in Arduino IDE
- Ensure MakeBlock Auriga is in bootloader mode

### Buzzer Not Working
- Verify buzzer pin is correct (default: 45)
- Check buzzer is properly connected
- Test with Arduino's tone() function directly

### Serial Communication Issues
- Verify baud rate is 115200
- Check serial monitor for received data
- Use `identify_bots.py` to test BLE connection first

---

## References
- [MakeBlock Auriga Documentation](https://www.makeblock.com/products/mbot-ranger-auriga)
- [Arduino Reference](https://www.arduino.cc/reference/)
- [MeAuriga Library](https://github.com/Makeblock-official/mbot_ranger_audriga)
