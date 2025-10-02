# AurigaRobotControl

A .NET 8 WPF application for controlling MakeBlock Auriga robots via Bluetooth. Features:
- RGB LED ring control (12 individually addressable LEDs)
- WASD motor movement controls
- Emergency stop
- Configurable command format
- Command sequence editor and runner
- Connection status indicators
- Data logging for sensor readings and sent commands

## Architecture
- `AurigaRobotControl.Core`: Core logic and robot command abstractions
- `AurigaRobotControl.Data`: Data access, logging, and configuration
- `AurigaRobotControl.UI.Wpf`: WPF user interface

Designed for extensibility: future CLI, web, or mobile frontends can be added easily.

## Getting Started
1. Open the solution in Visual Studio or VS Code
2. Build the solution
3. Launch `AurigaRobotControl.UI.Wpf` to start controlling your robot

## Requirements
- .NET 8 SDK
- Windows 10/11 (WPF UI)
- Bluetooth 4.0+ adapter

## License
MIT