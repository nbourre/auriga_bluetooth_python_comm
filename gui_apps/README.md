# GUI Applications

Cross-platform graphical interfaces for communicating with MakeBlock robots over BLE.

## Applications Overview

| App | GUI Framework | Features | Use Case |
|-----|---|---|---|
| `gui_ble.py` | Tkinter | Basic send/receive, device scan | General communication |
| `gui_ble_wasd.py` | Tkinter | WASD keyboard control, actions | Robot movement control |
| `gui_ble_pygame.py` | Pygame | Real-time visual display, streaming | High-performance control |
| `gui_ble_telemetry.py` | Pygame | Sensor data visualization, graphs | Telemetry monitoring |

---

## 1. gui_ble.py - Basic BLE Communication GUI

**Purpose:** Simple, user-friendly interface for connecting and communicating with BLE devices.

**Framework:** Tkinter (cross-platform)

**Features:**
- **Device Scanner:** Discover nearby BLE devices with one click
- **Connection Management:** Connect/disconnect with visual feedback
- **Message Sending:** Type and send messages with configurable format
- **Real-time Receiving:** Display incoming messages in real-time
- **Line Ending Options:** Choose NL, CR, BOTH, or NONE
- **Header Support:** Optional 0xFF 0x55 prefix
- **Device Persistence:** Remembers last connected device
- **Device List:** Manual device entry if name is unknown

**Usage:**
```bash
python gui_ble.py
```

**How to Use:**
1. **Scan:** Click "Scan Devices" to discover robots
2. **Connect:** Select a device from dropdown or enter manually
3. **Send:** Type message, choose line ending, click "Send"
4. **Receive:** Incoming messages display automatically
5. **Disconnect:** Click "Disconnect" to close connection

**GUI Layout:**
```
┌─ Device Management ─────────────────┐
│ [Scan] [Connect] [Disconnect]       │
│ Device: [Dropdown ▼]                │
│ Or enter: [Text field]              │
├─ Message Configuration ─────────────┤
│ Line Ending: [NL ▼]   [✓] Header   │
├─ Communication ─────────────────────┤
│ [Large text area for messages]      │
│ Send: [Input field] [Send]          │
│ [Status bar]                        │
└─────────────────────────────────────┘
```

**Keyboard Shortcuts:**
- **Ctrl+Enter:** Send message
- **Ctrl+D:** Disconnect

**Configuration Files:**
- `last_connected_device.json` - Remembers last device

---

## 2. gui_ble_wasd.py - Keyboard-Controlled Robot

**Purpose:** Advanced controller for real-time robot movement and action execution.

**Framework:** Tkinter

**Features:**
- **WASD Movement:** Real-time directional control
  - **W:** Forward
  - **A:** Left
  - **S:** Backward
  - **D:** Right
  - **E:** Special action
- **Frequency Control:** Adjust streaming frequency (1-50 Hz)
- **Custom Actions:** Configurable action buttons from `actions.json`
- **Dual Mode:** Toggle between keyboard control and manual text input
- **Status Display:** Real-time connection status and frequency info
- **Device Persistence:** Remembers last connected robot

**Usage:**
```bash
python gui_ble_wasd.py
```

**Keyboard Controls:**
```
W     - Forward
A S D - Left, Back, Right
E     - Special action (configurable)
Q R T - Custom action keys (from actions.json)
```

**GUI Elements:**
- Device selector dropdown
- Scan/Connect/Disconnect buttons
- Frequency slider (1-50 Hz, default 10)
- Toggle for keyboard control
- Custom action buttons
- Real-time message log
- Connection status indicator

**Configuration File (actions.json):**
```json
{
  "header": [255, 85],
  "directions": {
    "w": "F",
    "a": "L",
    "s": "B",
    "d": "R",
    "e": "E",
    "stop": "DIR_STOP"
  },
  "actions": [
    {
      "key": "q",
      "data": "LIGHT_TOGGLE",
      "label": "Toggle Light"
    },
    {
      "key": "r",
      "data": [255, 85, 2, 0],
      "label": "Special Command"
    },
    {
      "key": "t",
      "data": "BEEP",
      "label": "Beep"
    }
  ]
}
```

**How WASD Works:**
- Each key press starts streaming that direction at configured frequency
- Multiple keys can be held simultaneously
- Releasing all movement keys sends stop command
- Frequency can be adjusted in real-time without re-connecting

**Frequency Control:**
- **Default:** 10 Hz (10 commands per second)
- **Range:** 1-50 Hz
- **Adjust:** Use slider or +/- buttons in GUI
- **Use Case:** Lower for power saving, higher for responsive control

---

## 3. gui_ble_pygame.py - Real-Time Pygame Interface

**Purpose:** High-performance visual interface with real-time data streaming.

**Framework:** Pygame

**Features:**
- **Real-time Graphics:** Pygame-based rendering
- **WASD Streaming:** Continuous directional control
- **Frequency Adjustment:** +/- keys to adjust streaming rate
- **Header Toggle:** 'H' key to toggle 0xFF 0x55 prefix
- **Line Ending Cycle:** 'F' key to cycle through line ending options
- **Manual Text Mode:** 'T' key for manual message input
- **Device Scanning:** 'C' key to scan for robots
- **Connection Selection:** UP/DOWN arrows to select device
- **Status Display:** Real-time connection status and frequency
- **Message Log:** Incoming and outgoing message history

**Usage:**
```bash
python gui_ble_pygame.py
```

**Keyboard Controls:**
```
C           - Scan for devices
↑ ↓         - Select device
ENTER       - Connect to selected device
ESC         - Disconnect (if connected) or Exit
H           - Toggle header
F           - Cycle line ending
+ / -       - Increase/decrease frequency
W A S D E   - Movement commands
T           - Enter text input mode
```

**Display Layout:**
```
┌─ MonoGame BLE Robot Controller ────────┐
│ Status: CONNECTED to Device_Name       │
│ Header: ON  LineEnd: BOTH  Freq: 10Hz  │
│ Controls: C=Scan  ENTER=Connect ...    │
├─ Devices ─────────────────────────────┤
│ > Device_1 [AA:BB:CC:DD:EE:FF]        │
│   Device_2 [AA:BB:CC:DD:EE:00]        │
├─ Log ────────────────────────────────┤
│ Device: Device_1 discovered            │
│ Dir start: w                            │
│ Dir: a                                  │
│ Stop sent                               │
│ > Manual text input mode               │
└─────────────────────────────────────────┘
```

**Real-Time Features:**
- Streaming sends direction continuously at configured frequency
- Hold key to stream, release to send stop
- Frequency adjustable without reconnecting
- Multiple simultaneous keys supported

---

## 4. gui_ble_telemetry.py - Sensor Data Visualization

**Purpose:** Monitor and visualize real-time sensor data from the robot.

**Framework:** Pygame

**Features:**
- **Real-time Graphs:** Display sensor values over time
- **Multiple Sensors:** Monitor multiple sensors simultaneously
- **Data Logging:** Record sensor data to CSV/JSON
- **Customizable Layout:** Arrange graphs on screen
- **Frequency Control:** Adjust sensor sampling rate
- **WASD Control:** Drive robot while monitoring sensors
- **Export Data:** Save telemetry data for analysis
- **Visual Indicators:** Color-coded sensor status

**Usage:**
```bash
python gui_ble_telemetry.py
```

**Typical Setup:**
1. **Connect** to robot
2. **Select sensors** to monitor
3. **Start streaming** sensor data
4. **View real-time graphs** of sensor values
5. **Export data** for analysis

**Configuration:**
Sensor configuration in code (similar to `auriga_firmware.py` constants):
- Ultrasonic distance
- Temperature
- Light level
- Gyroscope/Accelerometer
- Motor encoders
- Battery voltage

**Data Export:**
- CSV format for Excel/spreadsheet analysis
- JSON format for programmatic access
- Timestamps included for all readings

**Keyboard Controls:**
```
C           - Scan devices
ENTER       - Connect
ESC         - Disconnect/Exit
W A S D     - Drive robot
+ / -       - Adjust sampling frequency
SPACE       - Start/stop logging
R           - Reset graph
E           - Export data
```

---

## Common Features (All Apps)

### Device Scanning
- Automatic BLE device discovery
- Filter for MakeBlock robots (optional)
- Display device name and MAC address
- Connection status indication

### Message Format
All apps support configurable message formatting:

**Structure:**
```
[HEADER] [DATA] [LINE_ENDING]
```

**Header (optional):**
- Default: 0xFF 0x55
- Toggle on/off per app

**Data:**
- String: "FORWARD"
- Bytes: [0xFF, 0x55, 0x01]
- Mixed: Can combine

**Line Ending:**
- **NL:** \n (0x0A)
- **CR:** \r (0x0D)
- **BOTH:** \r\n (default)
- **NONE:** No ending

### Configuration Files
- `last_connected_device.json` - Persists last device
- `actions.json` - Defines custom actions (WASD apps)
- Device-specific configs (for telemetry)

---

## Installation

### Requirements
- Python 3.7+
- Bleak (BLE library)
- Tkinter (usually included, for Tkinter apps)
- Pygame (for Pygame apps)

### Install Dependencies
```bash
pip install bleak
pip install pygame      # For pygame apps
pip install tkinter     # Usually pre-installed
```

### Verify Installation
```bash
python -c "import bleak; print('Bleak OK')"
python -c "import pygame; print('Pygame OK')"
python -c "import tkinter; print('Tkinter OK')"
```

---

## Troubleshooting

### Application Won't Start
- Verify Python 3.7+ installed
- Check all dependencies installed: `pip list | grep bleak`
- Try running from project directory

### Cannot Find Devices
- Run `cli_apps/scan_robots.py` to verify robot is visible
- Check robot is powered on and Bluetooth enabled
- Try restarting Bluetooth
- Move closer to robot

### Connection Drops
- Check BLE signal strength (move closer)
- Verify robot firmware is recent
- Try disconnecting/reconnecting
- Check if another app is connected to same device

### WASD Not Working
- Verify keyboard control is enabled
- Check if text input mode is active (disable it)
- Ensure robot is connected
- Verify `actions.json` has correct direction payloads

### Pygame Window Issues (gui_ble_pygame.py)
- Check display resolution is at least 800x600
- Verify graphics drivers are updated
- Try running with `SDL_VIDEODRIVER=windowed`

### Data Not Received (Telemetry)
- Use `cli_apps/ble_logger.py` to verify device characteristics
- Check CHARACTERISTIC_NOTIFY_UUID matches device
- Verify device firmware supports telemetry
- Try lower sampling frequency

---

## Performance Tips

### For WASD Control
- Start with 10 Hz frequency, adjust as needed
- Higher frequency = more responsive but more power usage
- Lower frequency = less lag on unreliable connections

### For Telemetry
- Sample only needed sensors
- Reduce graph update frequency for lower CPU usage
- Export data periodically instead of continuous logging

### General
- Close other BLE apps before running
- Keep device close for better signal
- Update robot firmware to latest version

---

## Integration with CLI Apps

GUI apps work well with CLI tools:
- Use `scan_robots.py` to find device addresses
- Use `identify_bots.py` to identify which robot
- Use `ble_logger.py` to discover characteristics
- Use `auriga_firmware.py` for custom protocol testing

---

## Related Documentation

- [Main README](../README.md)
- [CLI Applications](../cli_apps/README.md)
- [Arduino Sketches](../arduino/README.md)
- [Bleak Documentation](https://bleak.readthedocs.io/)
- [Pygame Documentation](https://www.pygame.org/docs/)
