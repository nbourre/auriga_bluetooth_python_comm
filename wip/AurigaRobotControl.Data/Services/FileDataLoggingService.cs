using AurigaRobotControl.Core.Interfaces;
using AurigaRobotControl.Core.Models;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;

namespace AurigaRobotControl.Data.Services
{
    public class FileDataLoggingService : IDataLoggingService
    {
        private readonly string _logDirectory;
        private readonly string _logFilePath;
        private readonly List<LogEntry> _memoryLogs;
        private readonly object _lockObject = new();

        public FileDataLoggingService()
        {
            _logDirectory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "AurigaRobotControl", "Logs");
            _logFilePath = Path.Combine(_logDirectory, $"robot_log_{DateTime.Now:yyyy-MM-dd}.json");
            _memoryLogs = new List<LogEntry>();
            
            Directory.CreateDirectory(_logDirectory);
        }

        public async Task LogCommandAsync(RobotCommand command, bool successful)
        {
            var logEntry = new LogEntry
            {
                Id = GetNextId(),
                Timestamp = DateTime.Now,
                Level = successful ? LogLevel.Info : LogLevel.Error,
                Category = "Command",
                Message = command.Description ?? "Robot command",
                Details = JsonSerializer.Serialize(new
                {
                    command.Id,
                    command.Action,
                    command.Device,
                    command.Port,
                    command.Slot,
                    Data = command.Data != null ? Convert.ToHexString(command.Data) : null,
                    Successful = successful
                })
            };

            await AddLogEntryAsync(logEntry);
        }

        public async Task LogDataReceivedAsync(string data)
        {
            var logEntry = new LogEntry
            {
                Id = GetNextId(),
                Timestamp = DateTime.Now,
                Level = LogLevel.Info,
                Category = "DataReceived",
                Message = "Data received from robot",
                Details = data
            };

            await AddLogEntryAsync(logEntry);
        }

        public async Task LogConnectionEventAsync(string deviceName, bool connected)
        {
            var logEntry = new LogEntry
            {
                Id = GetNextId(),
                Timestamp = DateTime.Now,
                Level = LogLevel.Info,
                Category = "Connection",
                Message = connected ? "Connected to robot" : "Disconnected from robot",
                DeviceName = deviceName,
                Details = JsonSerializer.Serialize(new { DeviceName = deviceName, Connected = connected })
            };

            await AddLogEntryAsync(logEntry);
        }

        public async Task LogErrorAsync(string error, Exception? exception = null)
        {
            var logEntry = new LogEntry
            {
                Id = GetNextId(),
                Timestamp = DateTime.Now,
                Level = LogLevel.Error,
                Category = "Error",
                Message = error,
                Details = exception != null ? JsonSerializer.Serialize(new
                {
                    exception.Message,
                    exception.StackTrace,
                    InnerException = exception.InnerException?.Message
                }) : null
            };

            await AddLogEntryAsync(logEntry);
        }

        public async Task<List<LogEntry>> GetLogsAsync(DateTime? fromDate = null, DateTime? toDate = null, LogLevel? level = null)
        {
            await LoadLogsFromFileAsync();

            lock (_lockObject)
            {
                var query = _memoryLogs.AsQueryable();

                if (fromDate.HasValue)
                    query = query.Where(l => l.Timestamp >= fromDate.Value);

                if (toDate.HasValue)
                    query = query.Where(l => l.Timestamp <= toDate.Value);

                if (level.HasValue)
                    query = query.Where(l => l.Level == level.Value);

                return query.OrderByDescending(l => l.Timestamp).ToList();
            }
        }

        public async Task ClearLogsAsync(DateTime? olderThan = null)
        {
            await LoadLogsFromFileAsync();

            lock (_lockObject)
            {
                if (olderThan.HasValue)
                {
                    _memoryLogs.RemoveAll(l => l.Timestamp < olderThan.Value);
                }
                else
                {
                    _memoryLogs.Clear();
                }
            }

            await SaveLogsToFileAsync();
        }

        private async Task AddLogEntryAsync(LogEntry logEntry)
        {
            lock (_lockObject)
            {
                _memoryLogs.Add(logEntry);
                
                // Keep only the last 1000 entries in memory
                if (_memoryLogs.Count > 1000)
                {
                    _memoryLogs.RemoveAt(0);
                }
            }

            // Save to file asynchronously
            _ = Task.Run(async () => await SaveLogsToFileAsync());
        }

        private async Task LoadLogsFromFileAsync()
        {
            if (!File.Exists(_logFilePath))
                return;

            try
            {
                var json = await File.ReadAllTextAsync(_logFilePath);
                if (!string.IsNullOrEmpty(json))
                {
                    var logs = JsonSerializer.Deserialize<List<LogEntry>>(json) ?? new List<LogEntry>();
                    
                    lock (_lockObject)
                    {
                        _memoryLogs.Clear();
                        _memoryLogs.AddRange(logs);
                    }
                }
            }
            catch (Exception ex)
            {
                // If we can't load logs, start with empty collection
                Console.WriteLine($"Failed to load logs: {ex.Message}");
            }
        }

        private async Task SaveLogsToFileAsync()
        {
            try
            {
                List<LogEntry> logsToSave;
                lock (_lockObject)
                {
                    logsToSave = new List<LogEntry>(_memoryLogs);
                }

                var json = JsonSerializer.Serialize(logsToSave, new JsonSerializerOptions
                {
                    WriteIndented = true
                });

                await File.WriteAllTextAsync(_logFilePath, json);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Failed to save logs: {ex.Message}");
            }
        }

        private int GetNextId()
        {
            lock (_lockObject)
            {
                return _memoryLogs.Count > 0 ? _memoryLogs.Max(l => l.Id) + 1 : 1;
            }
        }
    }
}