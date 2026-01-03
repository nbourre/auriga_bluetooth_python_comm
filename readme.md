# MakeBlock bluetooth communication

With this script, we can now communicate with the MakeBlock Bluetooth module without relying on the MakeBlock software! And more importantly, we can now use Arduino IDE to program the MakeBlock robot!

# How to use
To test the code, you will need to have the following installed:
- firmware_for_auriga.ino uploaded
- Change the DEVICE_ADDRESS variable to the MAC address of your Bluetooth module
  - Use your phone to find the MAC address of the Bluetooth module
  - Or use the scan_robots.py script to find the MAC address of the Bluetooth module
- Test the by changing the commented commands.

# GUI Applications
**AI generated content**

This project includes two GUI applications for interacting with BLE devices:

## gui_ble.py - Basic BLE Communication GUI

### Location
`gui_apps/gui_ble.py`

### Features
- **Device Scanner**: Scan for nearby BLE devices and select from a dropdown
- **Manual Connection**: Enter device name manually if not found in scan
- **Real-time Communication**: Send and receive messages with the connected device
- **Message Configuration**: Choose line endings (NL, CR, BOTH, NONE)
- **Header Support**: Optional header prefix (configurable via actions.json)
- **Status Monitoring**: Real-time connection status display
- **Device Persistence**: Remembers last connected device

### How to Use
1. **Launch the application**:
   ```bash
   python gui_apps/gui_ble.py
   ```

2. **Connect to a device**:
   - Click "Scan Devices" to discover nearby BLE devices
   - Select a device from the dropdown, OR
   - Enter the device name manually in the text field
   - Click "Connect"

3. **Send messages**:
   - Type your message in the text field
   - Choose line ending format from dropdown
   - Check "Header" if you want to include the configured header
   - Click "Send"

4. **Receive messages**:
   - Incoming messages appear automatically in the main text area


## gui_ble_wasd.py - Advanced Robot Controller

### Location
`gui_apps/gui_ble_wasd.py`

### Features
- **All basic BLE features** from gui_ble.py
- **WASD Keyboard Control**: Real-time directional control using W/A/S/D keys
- **Customizable Actions**: Configurable action buttons with keyboard shortcuts
- **Frequency Control**: Adjustable transmission frequency for WASD commands
- **Header Support**: Optional data header prefix (0xFF55 by default)
- **Smart Input Management**: Automatically disables text input when keyboard control is active

### How to Use
1. **Launch the application**:
   ```bash
   python gui_apps/gui_ble_wasd.py
   ```

2. **Connect to a device** (same as gui_ble.py)

3. **Configure actions** (if needed):
   - Edit `gui_apps/actions.json` to customize commands
   - Click "Reload Actions" to apply changes

4. **Use keyboard control**:
   - Check "Enable Keyboard Control" checkbox
   - Use **W/A/S/D** keys for directional movement
   - Use configured action keys (Q, E, R, etc.) for special commands
   - Adjust frequency slider for command transmission rate

5. **Manual message sending**:
   - Uncheck "Enable Keyboard Control" to use manual text input
   - Type messages and send as in gui_ble.py

### Configuration File (actions.json)
```json
{
  "header": [255, 85],
  "directions": {
    "w": "F",
    "a": "L", 
    "s": "B",
    "d": "R",
    "stop": "DIR_STOP"
  },
  "actions": [
    {
      "key": "q",
      "data": "LIGHT_TOGGLE",
      "label": "Toggle Light"
    },
    {
      "key": "e", 
      "data": [255, 85, 2, 0],
      "label": "Special Command"
    },
    {
      "key": "r",
      "data": "BEEP",
      "label": "Beep Sound"
    }
  ]
}
```

#### Configuration Options:
- **header**: Array of bytes to prefix to all messages when header option is enabled
- **directions**: Payloads for W/A/S/D movement and stop command
- **actions**: List of action buttons with:
  - `key`: Keyboard shortcut
  - `data`: Command payload (string, number, or byte array)
  - `label`: Display name for the button

### Keyboard Shortcuts (when keyboard control is enabled)
- **W**: Forward
- **A**: Left  
- **S**: Backward
- **D**: Right
- **Q**: Toggle Light (default)
- **E**: Special Command (default)
- **R**: Beep Sound (default)

### Data Formats
Actions support multiple data formats:
- **String**: `"LIGHT_TOGGLE"` → UTF-8 encoded
- **Integer**: `255` → Single byte
- **Byte Array**: `[255, 85, 2, 0]` → Sequence of bytes

## Requirements
- Python 3.7+
- `bleak` library for BLE communication
- `tkinter` (usually included with Python)

Install dependencies:
```bash
pip install bleak
```

## Warning!
For now the code is only in the super-alpha stage, so it may not work as expected. I will try to improve it as soon as possible.

## MonoGame BLE Controller (DesktopGL)

Location: `monogame_ranger/MonoGame_ranger/MonoGame_ranger`

This C# MonoGame application mirrors the functionality of the Python `gui_ble_wasd.py` and `gui_ble_pygame.py` scripts, providing a real-time keyboard-driven BLE robot controller.

### Features
* Device scanning (press `C`) using `Plugin.BLE`.
* Connect to selected device (`ENTER`).
* WASD + `E` directional streaming at adjustable frequency.
* Custom actions loaded from `actions.json` (string, int, byte arrays, mixed JSON tokens).
* Optional header prefix toggle (`H`).
* Cycle line endings (`F`): BOTH → NL → CR → NONE.
* Manual text send mode (`T` then type + ENTER).
* Live incoming data log (notifications) and sent payload log.
* Graceful disconnect (`ESC`).

### Controls Summary
| Key | Action |
|-----|--------|
| C | Scan for BLE devices (6s) |
| ↑ / ↓ | Select device from list |
| ENTER | Connect to selected device |
| H | Toggle header on/off |
| F | Cycle line ending |
| + / - | Increase / decrease streaming frequency (1–50 Hz) |
| T | Enter manual text input mode |
| ESC | Disconnect (if connected) or Exit |
| W A S D E | Directional streaming commands |
| (Action Keys) | Defined in `actions.json` (e.g. Q, R, etc.) |

### actions.json Format (same as Python)
```
{
  "header": [255, 85],
  "directions": { "w": "F", "a": "L", "s": "B", "d": "R", "e": "E", "stop": "DIR_STOP" },
  "actions": [ { "key": "q", "data": "LIGHT_TOGGLE", "label": "Light" } ]
}
```
Supported `data` payload types: string, number, array of ints/hex strings, mixed arrays (e.g. `["0xFF", 2, "RUN"]`).

### Build & Run
Requirements:
* .NET 8 SDK
* MonoGame DesktopGL packages (already referenced)
* `Plugin.BLE` (already referenced)

Build:
```pwsh
dotnet build monogame_ranger/MonoGame_ranger/MonoGame_ranger/MonoGame_ranger.csproj
```
Run:
```pwsh
dotnet run --project monogame_ranger/MonoGame_ranger/MonoGame_ranger/MonoGame_ranger.csproj
```

### Customizing BLE Characteristics
In `BleController.cs` you can set:
```csharp
ble.TargetServiceUuid = Guid.Parse("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx");
ble.TargetWriteCharacteristicUuid = Guid.Parse("yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy");
ble.TargetNotifyCharacteristicUuid = Guid.Parse("zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz");
```
If left null the first writable / notifiable characteristics found are used.

### Notes
* Direction streaming thread resends the last direction at configured frequency until key released (then sends stop payload).
* Header bytes are prepended only when toggled ON.
* Line endings appended after header+core; choose NONE for raw binary.
* Incoming notification bytes are hex-dumped in the log.

### Future Improvements
* In-game UI overlays for frequency & connection state.
* Persist last connected device and user settings.
* Optional gamepad support for directions.


