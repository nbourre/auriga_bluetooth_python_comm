# MakeBlock Bluetooth Communication

A comprehensive suite of Python and Arduino tools for communicating with MakeBlock robots over Bluetooth Low Energy (BLE), without relying on the MakeBlock proprietary software.

**Key Advantage:** Now you can program your MakeBlock robot with Arduino IDE and control it entirely through custom Python scripts!

## Project Structure

```
python_auriga_bluetooth/
├── arduino/                    # Arduino sketches for MakeBlock robots
│   ├── auriga_ble_test/       # Main firmware for BLE communication
│   └── beep_when_found/       # Utility for identifying robots
├── cli_apps/                   # Command-line tools
│   ├── scan_robots.py         # Discover and catalog robots
│   ├── identify_bots.py       # Identify specific robot by beeping
│   ├── ble_logger.py          # Log device characteristics
│   ├── makeblock_bluetooth.py # Interactive terminal
│   ├── makeblock_ble_lite.py  # Lightweight CLI
│   └── auriga_firmware.py     # Firmware protocol interface
├── gui_apps/                   # GUI applications
│   ├── gui_ble.py             # Basic send/receive interface
│   ├── gui_ble_wasd.py        # Keyboard-controlled robot
│   ├── gui_ble_pygame.py      # Real-time Pygame interface
│   └── gui_ble_telemetry.py   # Sensor data visualization
├── monogame_ranger/            # C# MonoGame controller
│   └── MonoGame_ranger/        # Desktop GL implementation
└── README.md                   # This file
```

## Quick Start

### Installation
```bash
# Clone the repository
git clone <repository-url>
cd python_auriga_bluetooth

# Install Python dependencies
pip install bleak pygame tkinter

# For Arduino sketches:
# - Install Arduino IDE
# - Install MakeBlock libraries
# - Upload auriga_ble_test.ino to your robot
```

### First Time Setup
1. **Upload firmware** to your MakeBlock Auriga:
   - Open `arduino/auriga_ble_test/auriga_ble_test.ino` in Arduino IDE
   - Select correct board (MakeBlock Auriga)
   - Upload to robot

2. **Discover your robot:**
   ```bash
   python cli_apps/scan_robots.py
   ```
   This creates `makeblock_robots.csv` with available devices.

3. **Identify your specific robot:**
   ```bash
   python cli_apps/identify_bots.py
   ```
   Listen for beeping to identify which robot is which.

4. **Start communicating:**
   ```bash
   python gui_apps/gui_ble.py        # Basic communication
   python gui_apps/gui_ble_wasd.py   # Keyboard control
   ```

## Documentation

### Component Documentation
- **[Arduino Sketches](arduino/README.md)** - Firmware for MakeBlock robots
- **[CLI Applications](cli_apps/README.md)** - Command-line tools for scanning, logging, and communication
- **[GUI Applications](gui_apps/README.md)** - Full-featured interfaces for control and monitoring
- **[MonoGame Controller](monogame_ranger/README.md)** - C# alternative for Windows

### Quick Reference

#### GUI Applications
#### GUI Applications

| Application | Framework | Purpose | Use Case |
|---|---|---|---|
| **gui_ble.py** | Tkinter | Basic send/receive | General communication |
| **gui_ble_wasd.py** | Tkinter | WASD keyboard control | Robot movement |
| **gui_ble_pygame.py** | Pygame | Real-time streaming | High-performance control |
| **gui_ble_telemetry.py** | Pygame | Sensor visualization | Data monitoring |

See [GUI Applications](gui_apps/README.md) for detailed documentation.

#### CLI Applications

| Tool | Purpose | Typical Usage |
|---|---|---|
| **scan_robots.py** | Discover and catalog robots | Initial setup |
| **identify_bots.py** | Identify specific robot by beeping | Find which robot is which |
| **ble_logger.py** | Log device services/characteristics | Debugging/discovery |
| **makeblock_bluetooth.py** | Interactive terminal interface | Manual testing |
| **makeblock_ble_lite.py** | Lightweight CLI alternative | Resource-constrained use |
| **auriga_firmware.py** | Firmware protocol interface | Sensor/motor control |

See [CLI Applications](cli_apps/README.md) for detailed documentation.

#### Arduino Sketches

| Sketch | Purpose | Features |
|---|---|---|
| **auriga_ble_test** | Main firmware | BLE communication, LED/buzzer control |
| **beep_when_found** | Robot identification | Beeps on command for identification |

See [Arduino Sketches](arduino/README.md) for detailed documentation.

## Common Tasks

### Task: Send Simple Command to Robot
```bash
python gui_apps/gui_ble.py
# 1. Click "Scan Devices"
# 2. Select your robot
# 3. Type "F" (forward) and click Send
```

### Task: Control Robot with Keyboard
```bash
python gui_apps/gui_ble_wasd.py
# 1. Connect to robot
# 2. Hold W/A/S/D to drive
# 3. Adjust frequency with +/- keys
```

### Task: Identify Which Robot is Which
```bash
python cli_apps/identify_bots.py
# Listen for beeping - each beep indicates which robot is being identified
```

### Task: Discover Device Characteristics
```bash
python cli_apps/ble_logger.py
# Creates device_log.json with all services and characteristics
```

### Task: Program Custom Robot Behavior
1. Edit `arduino/auriga_ble_test/auriga_ble_test.ino`
2. Upload to robot via Arduino IDE
3. Test with any Python CLI or GUI app

## Configuration Files

### actions.json
Defines custom commands and directions for WASD apps:
```json
{
  "header": [255, 85],
  "directions": {
    "w": "F",
    "a": "L",
    "s": "B",
    "d": "R",
    "e": "E",
    "stop": "STOP"
  },
  "actions": [
    {
      "key": "q",
      "data": "LIGHT_TOGGLE",
      "label": "Light"
    }
  ]
}
```

### last_connected_device.json
Automatically created - stores last connected device for quick reconnection:
```json
{
  "name": "Makeblock_LE10a5622dd32e"
}
```

## Technical Details

### BLE Characteristics
Default MakeBlock UUIDs:
- **Write:** `0000ffe3-0000-1000-8000-00805f9b34fb`
- **Notify:** `0000ffe2-0000-1000-8000-00805f9b34fb`

### Message Format
```
[HEADER] [DATA] [LINE_ENDING]
```
- **Header:** Optional 0xFF 0x55 (configurable)
- **Data:** Command payload (string, bytes, or mixed)
- **Line Ending:** \n, \r, \r\n, or none (configurable)

### Baud Rate (Serial)
All sketches use **115200 baud** for serial communication.

## Requirements

### Python
- Python 3.7 or higher
- pip package manager

### Python Libraries
```bash
pip install bleak pygame
```

Optional:
```bash
pip install tkinter  # Usually pre-installed on most systems
```

### Arduino
- Arduino IDE 1.8.0+
- MakeBlock Auriga board support
- MeAuriga library

### Hardware
- MakeBlock Auriga robot
- Bluetooth 4.0+ compatible device (PC, laptop, Raspberry Pi)
- USB cable for uploading firmware

## Getting Help

### Common Issues

**"No Bluetooth adapter found"**
- Check Bluetooth is enabled on your system
- On Linux: `sudo systemctl start bluetooth`
- On Mac/Windows: Enable Bluetooth in system settings

**"Device not found"**
- Run `scan_robots.py` to verify robot is discoverable
- Ensure robot is powered on
- Check if Bluetooth is not already connected to another app

**"Cannot connect to device"**
- Verify correct device name
- Try scanning again with `scan_robots.py`
- Check if device is in range (usually ~10 meters)

**"Garbled messages received"**
- Check line ending setting matches device
- Verify baud rate is 115200 (for serial sketches)
- Try different line ending options

For more detailed troubleshooting, see:
- [CLI Applications Troubleshooting](cli_apps/README.md#troubleshooting)
- [GUI Applications Troubleshooting](gui_apps/README.md#troubleshooting)
- [Arduino Sketches Troubleshooting](arduino/README.md#troubleshooting)

## Contributing

Contributions welcome! Areas for improvement:
- Additional GUI applications
- More robot sketches
- Performance optimizations
- Documentation improvements
- Bug fixes and testing

## License

[Specify your license here]

## References

- [Bleak BLE Library](https://bleak.readthedocs.io/)
- [MakeBlock Auriga](https://www.makeblock.com/products/mbot-ranger-audriga)
- [Pygame Documentation](https://www.pygame.org/docs/)
- [Arduino Reference](https://www.arduino.cc/reference/)
- [Bluetooth Low Energy Overview](https://www.bluetooth.com/specifications/specs/core-specification/)

## Project Status

✅ **Alpha Stage** - Core functionality working, documentation improving
- ✅ BLE device scanning and connection
- ✅ Basic send/receive communication
- ✅ Keyboard-based robot control
- ✅ Sensor data logging
- ✅ Multiple GUI frameworks
- ⏳ Comprehensive test suite (in progress)
- ⏳ Mobile app support (planned)
- ⏳ Advanced telemetry visualization (in progress)

## Changelog

### Version 0.2 (Current)
- Added CLI tools for device discovery
- Added multiple GUI applications
- Added C# MonoGame controller
- Improved documentation with separate README files for each component
- Support for custom action configurations

### Version 0.1
- Initial Python BLE communication tools
- Basic GUI application

---

For detailed information about each component, see the respective README files:
- [Arduino Sketches](arduino/README.md)
- [CLI Applications](cli_apps/README.md)
- [GUI Applications](gui_apps/README.md)
- [MonoGame Controller](monogame_ranger/README.md)

