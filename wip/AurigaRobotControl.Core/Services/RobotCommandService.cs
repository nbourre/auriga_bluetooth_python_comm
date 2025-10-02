using AurigaRobotControl.Core.Interfaces;
using AurigaRobotControl.Core.Models;
using System;
using System.Threading.Tasks;

namespace AurigaRobotControl.Core.Services
{
    public class RobotCommandService : IRobotCommandService
    {
        private byte _commandId = 1;

        public async Task<RobotCommand> CreateMoveCommandAsync(MotorCommand.Direction direction, byte speed = 100, int duration = 0)
        {
            byte[] motorData = direction switch
            {
                MotorCommand.Direction.Forward => new byte[] { speed, speed }, // Both motors forward
                MotorCommand.Direction.Backward => new byte[] { (byte)(256 - speed), (byte)(256 - speed) }, // Both motors backward
                MotorCommand.Direction.Left => new byte[] { (byte)(256 - speed), speed }, // Left motor backward, right forward
                MotorCommand.Direction.Right => new byte[] { speed, (byte)(256 - speed) }, // Left motor forward, right backward
                MotorCommand.Direction.Stop => new byte[] { 0, 0 }, // Stop both motors
                _ => new byte[] { 0, 0 }
            };

            var command = new RobotCommand
            {
                Id = GetNextCommandId(),
                Action = RobotAction.Run,
                Device = Models.RobotDevice.EncoderBoard,
                Port = RobotPort.Port1,
                Slot = 2,
                Data = motorData,
                Description = $"Move {direction} at speed {speed}"
            };

            return await Task.FromResult(command);
        }

        public async Task<RobotCommand> CreateStopCommandAsync()
        {
            return await CreateMoveCommandAsync(MotorCommand.Direction.Stop);
        }

        public async Task<RobotCommand> CreateLedCommandAsync(byte ledIndex, RgbColor color)
        {
            // MakeBlock LED ring command format: ledIndex, red, green, blue
            var data = new byte[] { ledIndex, color.Red, color.Green, color.Blue };

            var command = new RobotCommand
            {
                Id = GetNextCommandId(),
                Action = RobotAction.Run,
                Device = Models.RobotDevice.RgbLed,
                Port = RobotPort.Port1,
                Slot = 1,
                Data = data,
                Description = $"Set LED {ledIndex} to RGB({color.Red},{color.Green},{color.Blue})"
            };

            return await Task.FromResult(command);
        }

        public async Task<RobotCommand> CreateLedRingCommandAsync(RgbColor color)
        {
            // Set all LEDs (index 255 or 0 for all)
            return await CreateLedCommandAsync(0, color);
        }

        public async Task<RobotCommand> CreateBeepCommandAsync(int frequency = 1000, int duration = 500)
        {
            // Convert frequency and duration to bytes
            var freqBytes = BitConverter.GetBytes((short)frequency);
            var durationBytes = BitConverter.GetBytes((short)duration);
            
            var data = new byte[4];
            Array.Copy(freqBytes, 0, data, 0, 2);
            Array.Copy(durationBytes, 0, data, 2, 2);

            var command = new RobotCommand
            {
                Id = GetNextCommandId(),
                Action = RobotAction.Run,
                Device = Models.RobotDevice.Tone,
                Port = RobotPort.Port1,
                Data = data,
                Description = $"Beep at {frequency}Hz for {duration}ms"
            };

            return await Task.FromResult(command);
        }

        public async Task<RobotCommand> CreateSensorReadCommandAsync(Models.RobotDevice sensor, RobotPort port)
        {
            var command = new RobotCommand
            {
                Id = GetNextCommandId(),
                Action = RobotAction.Get,
                Device = sensor,
                Port = port,
                Description = $"Read {sensor} on {port}"
            };

            return await Task.FromResult(command);
        }

        public async Task<RobotCommand> CreateCustomCommandAsync(byte id, RobotAction action, Models.RobotDevice device, 
            RobotPort? port = null, byte? slot = null, byte[]? data = null)
        {
            var command = new RobotCommand
            {
                Id = id,
                Action = action,
                Device = device,
                Port = port,
                Slot = slot,
                Data = data,
                Description = $"Custom command: {action} {device}"
            };

            return await Task.FromResult(command);
        }

        private byte GetNextCommandId()
        {
            _commandId++;
            if (_commandId > 255) _commandId = 1;
            return _commandId;
        }
    }
}