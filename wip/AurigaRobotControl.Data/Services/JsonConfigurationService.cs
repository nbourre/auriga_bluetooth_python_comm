using AurigaRobotControl.Core.Interfaces;
using Microsoft.Extensions.Configuration;
using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using System.Threading.Tasks;

namespace AurigaRobotControl.Data.Services
{
    public class JsonConfigurationService : IConfigurationService
    {
        private readonly string _configDirectory;
        private readonly string _configFilePath;
        private readonly Dictionary<string, object> _settings;
        private readonly object _lockObject = new();

        public JsonConfigurationService()
        {
            _configDirectory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "AurigaRobotControl");
            _configFilePath = Path.Combine(_configDirectory, "appsettings.json");
            _settings = new Dictionary<string, object>();
            
            Directory.CreateDirectory(_configDirectory);
            _ = LoadSettingsAsync();
        }

        public async Task<T> GetSettingAsync<T>(string key, T defaultValue = default!)
        {
            await LoadSettingsAsync();
            
            lock (_lockObject)
            {
                if (_settings.TryGetValue(key, out var value))
                {
                    try
                    {
                        if (value is JsonElement jsonElement)
                        {
                            return JsonSerializer.Deserialize<T>(jsonElement.GetRawText()) ?? defaultValue;
                        }
                        
                        if (value is T directValue)
                        {
                            return directValue;
                        }
                        
                        // Try to convert
                        return (T)Convert.ChangeType(value, typeof(T));
                    }
                    catch
                    {
                        return defaultValue;
                    }
                }
                
                return defaultValue;
            }
        }

        public async Task SetSettingAsync<T>(string key, T value)
        {
            lock (_lockObject)
            {
                _settings[key] = value!;
            }
            
            await SaveSettingsAsync();
        }

        public async Task<Dictionary<string, object>> GetAllSettingsAsync()
        {
            await LoadSettingsAsync();
            
            lock (_lockObject)
            {
                return new Dictionary<string, object>(_settings);
            }
        }

        public async Task SaveSettingsAsync()
        {
            try
            {
                Dictionary<string, object> settingsToSave;
                lock (_lockObject)
                {
                    settingsToSave = new Dictionary<string, object>(_settings);
                }

                var json = JsonSerializer.Serialize(settingsToSave, new JsonSerializerOptions
                {
                    WriteIndented = true
                });

                await File.WriteAllTextAsync(_configFilePath, json);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Failed to save settings: {ex.Message}");
            }
        }

        public async Task<string?> GetLastConnectedDeviceAsync()
        {
            return await GetSettingAsync<string?>("LastConnectedDevice");
        }

        public async Task SetLastConnectedDeviceAsync(string deviceName)
        {
            await SetSettingAsync("LastConnectedDevice", deviceName);
        }

        public async Task<CommandFormat> GetCommandFormatAsync()
        {
            var format = await GetSettingAsync<CommandFormat?>("CommandFormat");
            return format ?? new CommandFormat(); // Return default if not found
        }

        public async Task SetCommandFormatAsync(CommandFormat format)
        {
            await SetSettingAsync("CommandFormat", format);
        }

        private async Task LoadSettingsAsync()
        {
            if (!File.Exists(_configFilePath))
            {
                // Create default settings file
                await CreateDefaultSettingsAsync();
                return;
            }

            try
            {
                var json = await File.ReadAllTextAsync(_configFilePath);
                if (!string.IsNullOrEmpty(json))
                {
                    var loadedSettings = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(json);
                    if (loadedSettings != null)
                    {
                        lock (_lockObject)
                        {
                            _settings.Clear();
                            foreach (var kvp in loadedSettings)
                            {
                                _settings[kvp.Key] = kvp.Value;
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Failed to load settings: {ex.Message}");
                await CreateDefaultSettingsAsync();
            }
        }

        private async Task CreateDefaultSettingsAsync()
        {
            var defaultSettings = new Dictionary<string, object>
            {
                ["LastConnectedDevice"] = "",
                ["CommandFormat"] = new CommandFormat(),
                ["AutoConnect"] = false,
                ["LogLevel"] = "Info",
                ["MaxLogEntries"] = 1000,
                ["ConnectionTimeout"] = 30,
                ["EmergencyStopEnabled"] = true,
                ["DefaultMovementSpeed"] = 100,
                ["DefaultBeepFrequency"] = 1000,
                ["DefaultBeepDuration"] = 500
            };

            lock (_lockObject)
            {
                _settings.Clear();
                foreach (var kvp in defaultSettings)
                {
                    _settings[kvp.Key] = kvp.Value;
                }
            }

            await SaveSettingsAsync();
        }
    }
}