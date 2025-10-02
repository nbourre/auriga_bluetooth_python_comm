using AurigaRobotControl.Core.Models;
using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace AurigaRobotControl.Core.Interfaces
{
    public interface IRobotConnectionService
    {
        event EventHandler<bool> ConnectionStatusChanged;
        event EventHandler<string> DataReceived;
        event EventHandler<string> ErrorOccurred;
        
        bool IsConnected { get; }
        string? ConnectedDeviceName { get; }
        
        Task<List<RobotDevice>> ScanForDevicesAsync();
        Task<bool> ConnectAsync(string deviceName);
        Task DisconnectAsync();
        Task<bool> SendCommandAsync(RobotCommand command);
        Task<bool> SendRawDataAsync(byte[] data);
    }

    public interface IRobotCommandService
    {
        Task<RobotCommand> CreateMoveCommandAsync(MotorCommand.Direction direction, byte speed = 100, int duration = 0);
        Task<RobotCommand> CreateStopCommandAsync();
        Task<RobotCommand> CreateLedCommandAsync(byte ledIndex, RgbColor color);
        Task<RobotCommand> CreateLedRingCommandAsync(RgbColor color);
        Task<RobotCommand> CreateBeepCommandAsync(int frequency = 1000, int duration = 500);
        Task<RobotCommand> CreateSensorReadCommandAsync(Models.RobotDevice sensor, RobotPort port);
        Task<RobotCommand> CreateCustomCommandAsync(byte id, RobotAction action, Models.RobotDevice device, RobotPort? port = null, byte? slot = null, byte[]? data = null);
    }

    public interface ICommandSequenceService
    {
        Task<List<CommandSequence>> GetAllSequencesAsync();
        Task<CommandSequence?> GetSequenceByIdAsync(int id);
        Task<int> SaveSequenceAsync(CommandSequence sequence);
        Task<bool> DeleteSequenceAsync(int id);
        Task<bool> ExecuteSequenceAsync(int sequenceId, IRobotConnectionService robotService);
        Task<bool> StopSequenceExecutionAsync();
        
        bool IsExecuting { get; }
        event EventHandler<CommandSequenceExecutionEventArgs> SequenceExecutionStarted;
        event EventHandler<CommandSequenceExecutionEventArgs> SequenceExecutionCompleted;
        event EventHandler<CommandSequenceExecutionEventArgs> SequenceExecutionError;
        event EventHandler<CommandSequenceStepEventArgs> SequenceStepExecuted;
    }

    public interface IDataLoggingService
    {
        Task LogCommandAsync(RobotCommand command, bool successful);
        Task LogDataReceivedAsync(string data);
        Task LogConnectionEventAsync(string deviceName, bool connected);
        Task LogErrorAsync(string error, Exception? exception = null);
        Task<List<LogEntry>> GetLogsAsync(DateTime? fromDate = null, DateTime? toDate = null, LogLevel? level = null);
        Task ClearLogsAsync(DateTime? olderThan = null);
    }

    public interface IConfigurationService
    {
        Task<T> GetSettingAsync<T>(string key, T defaultValue = default!);
        Task SetSettingAsync<T>(string key, T value);
        Task<Dictionary<string, object>> GetAllSettingsAsync();
        Task SaveSettingsAsync();
        
        // Specific robot settings
        Task<string?> GetLastConnectedDeviceAsync();
        Task SetLastConnectedDeviceAsync(string deviceName);
        Task<CommandFormat> GetCommandFormatAsync();
        Task SetCommandFormatAsync(CommandFormat format);
    }

    public class RobotDevice
    {
        public string Name { get; set; } = string.Empty;
        public string Address { get; set; } = string.Empty;
        public int SignalStrength { get; set; }
        public bool IsConnectable { get; set; } = true;
    }

    public class CommandSequence
    {
        public int Id { get; set; }
        public string Name { get; set; } = string.Empty;
        public string Description { get; set; } = string.Empty;
        public List<CommandSequenceStep> Steps { get; set; } = new();
        public DateTime CreatedAt { get; set; } = DateTime.Now;
        public DateTime ModifiedAt { get; set; } = DateTime.Now;
    }

    public class CommandSequenceStep
    {
        public int Order { get; set; }
        public RobotCommand Command { get; set; } = new();
        public int DelayAfterMs { get; set; } = 0;
        public string Description { get; set; } = string.Empty;
    }

    public class CommandSequenceExecutionEventArgs : EventArgs
    {
        public CommandSequence Sequence { get; set; } = new();
        public bool IsSuccessful { get; set; }
        public string? ErrorMessage { get; set; }
    }

    public class CommandSequenceStepEventArgs : EventArgs
    {
        public CommandSequenceStep Step { get; set; } = new();
        public int StepIndex { get; set; }
        public int TotalSteps { get; set; }
        public bool IsSuccessful { get; set; }
        public string? ErrorMessage { get; set; }
    }

    public class LogEntry
    {
        public int Id { get; set; }
        public DateTime Timestamp { get; set; } = DateTime.Now;
        public LogLevel Level { get; set; }
        public string Category { get; set; } = string.Empty;
        public string Message { get; set; } = string.Empty;
        public string? Details { get; set; }
        public string? DeviceName { get; set; }
    }

    public enum LogLevel
    {
        Debug,
        Info,
        Warning,
        Error
    }

    public class CommandFormat
    {
        public string Name { get; set; } = "MakeBlock Default";
        public byte[] Header { get; set; } = { 0xFF, 0x55 };
        public bool IncludeLength { get; set; } = true;
        public bool IncludeCrc { get; set; } = false;
        public string EndDataOption { get; set; } = "NONE"; // NL, CR, BOTH, NONE
        public bool IsCustom { get; set; } = false;
    }
}