using AurigaRobotControl.Core.Interfaces;
using AurigaRobotControl.Core.Models;
using InTheHand.Bluetooth;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace AurigaRobotControl.Data.Services
{
    public class BluetoothConnectionService : IRobotConnectionService
    {
        private BluetoothDevice? _connectedDevice;
        private GattCharacteristic? _writeCharacteristic;
        private GattCharacteristic? _notifyCharacteristic;
        private readonly IDataLoggingService _logger;
        
        // MakeBlock Auriga BLE UUIDs
        private const string ServiceUuid = "0000ffe1-0000-1000-8000-00805f9b34fb";
        private const string WriteCharacteristicUuid = "0000ffe3-0000-1000-8000-00805f9b34fb";
        private const string NotifyCharacteristicUuid = "0000ffe2-0000-1000-8000-00805f9b34fb";
        
        public event EventHandler<bool>? ConnectionStatusChanged;
        public event EventHandler<string>? DataReceived;
        public event EventHandler<string>? ErrorOccurred;

        public bool IsConnected => _connectedDevice?.Gatt?.IsConnected == true;
        public string? ConnectedDeviceName => _connectedDevice?.Name;

        public BluetoothConnectionService(IDataLoggingService logger)
        {
            _logger = logger;
        }

        public async Task<List<Core.Interfaces.RobotDevice>> ScanForDevicesAsync()
        {
            try
            {
                var devices = new List<Core.Interfaces.RobotDevice>();
                
                // Request device scan for MakeBlock devices
                var requestOptions = new RequestDeviceOptions();
                requestOptions.Filters.Add(new BluetoothLEScanFilter
                {
                    NamePrefix = "Makeblock"
                });

                var foundDevices = await Bluetooth.ScanForDevicesAsync(requestOptions);
                
                foreach (var device in foundDevices)
                {
                    if (!string.IsNullOrEmpty(device.Name) && device.Name.StartsWith("Makeblock"))
                    {
                        devices.Add(new Core.Interfaces.RobotDevice
                        {
                            Name = device.Name,
                            Address = device.Id,
                            SignalStrength = -50, // Placeholder
                            IsConnectable = true
                        });
                    }
                }

                await _logger.LogCommandAsync(new RobotCommand { Description = $"Device scan completed. Found {devices.Count} devices." }, true);
                return devices;
            }
            catch (Exception ex)
            {
                await _logger.LogErrorAsync("Device scan failed", ex);
                ErrorOccurred?.Invoke(this, $"Scan failed: {ex.Message}");
                return new List<Core.Interfaces.RobotDevice>();
            }
        }

        public async Task<bool> ConnectAsync(string deviceName)
        {
            try
            {
                if (IsConnected)
                {
                    await DisconnectAsync();
                }

                // Find the device
                var requestOptions = new RequestDeviceOptions();
                requestOptions.Filters.Add(new BluetoothLEScanFilter
                {
                    Name = deviceName
                });

                var devices = await Bluetooth.ScanForDevicesAsync(requestOptions);
                _connectedDevice = devices.FirstOrDefault(d => d.Name == deviceName);

                if (_connectedDevice == null)
                {
                    ErrorOccurred?.Invoke(this, $"Device '{deviceName}' not found");
                    return false;
                }

                // Connect to GATT server
                await _connectedDevice.Gatt.ConnectAsync();

                if (!_connectedDevice.Gatt.IsConnected)
                {
                    ErrorOccurred?.Invoke(this, "Failed to connect to GATT server");
                    return false;
                }

                // Get the service
                var service = await _connectedDevice.Gatt.GetPrimaryServiceAsync(BluetoothUuid.FromGuid(Guid.Parse(ServiceUuid)));
                if (service == null)
                {
                    ErrorOccurred?.Invoke(this, "MakeBlock service not found");
                    return false;
                }

                // Get characteristics
                _writeCharacteristic = await service.GetCharacteristicAsync(BluetoothUuid.FromGuid(Guid.Parse(WriteCharacteristicUuid)));
                _notifyCharacteristic = await service.GetCharacteristicAsync(BluetoothUuid.FromGuid(Guid.Parse(NotifyCharacteristicUuid)));

                if (_writeCharacteristic == null || _notifyCharacteristic == null)
                {
                    ErrorOccurred?.Invoke(this, "Required characteristics not found");
                    return false;
                }

                // Start notifications
                _notifyCharacteristic.CharacteristicValueChanged += OnCharacteristicValueChanged;
                await _notifyCharacteristic.StartNotificationsAsync();

                ConnectionStatusChanged?.Invoke(this, true);
                await _logger.LogConnectionEventAsync(deviceName, true);
                
                return true;
            }
            catch (Exception ex)
            {
                await _logger.LogErrorAsync($"Connection to {deviceName} failed", ex);
                ErrorOccurred?.Invoke(this, $"Connection failed: {ex.Message}");
                return false;
            }
        }

        public async Task DisconnectAsync()
        {
            try
            {
                if (_notifyCharacteristic != null)
                {
                    _notifyCharacteristic.CharacteristicValueChanged -= OnCharacteristicValueChanged;
                    await _notifyCharacteristic.StopNotificationsAsync();
                }

                if (_connectedDevice?.Gatt?.IsConnected == true)
                {
                    _connectedDevice.Gatt.Disconnect();
                }

                var deviceName = ConnectedDeviceName;
                _connectedDevice = null;
                _writeCharacteristic = null;
                _notifyCharacteristic = null;

                ConnectionStatusChanged?.Invoke(this, false);
                
                if (!string.IsNullOrEmpty(deviceName))
                {
                    await _logger.LogConnectionEventAsync(deviceName, false);
                }
            }
            catch (Exception ex)
            {
                await _logger.LogErrorAsync("Disconnection failed", ex);
            }
        }

        public async Task<bool> SendCommandAsync(RobotCommand command)
        {
            if (!IsConnected || _writeCharacteristic == null)
            {
                ErrorOccurred?.Invoke(this, "Not connected to any device");
                return false;
            }

            try
            {
                var data = command.ToByteArray();
                await _writeCharacteristic.WriteValueWithoutResponseAsync(data);
                await _logger.LogCommandAsync(command, true);
                return true;
            }
            catch (Exception ex)
            {
                await _logger.LogCommandAsync(command, false);
                await _logger.LogErrorAsync($"Failed to send command: {command.Description}", ex);
                ErrorOccurred?.Invoke(this, $"Send failed: {ex.Message}");
                return false;
            }
        }

        public async Task<bool> SendRawDataAsync(byte[] data)
        {
            if (!IsConnected || _writeCharacteristic == null)
            {
                ErrorOccurred?.Invoke(this, "Not connected to any device");
                return false;
            }

            try
            {
                await _writeCharacteristic.WriteValueWithoutResponseAsync(data);
                await _logger.LogCommandAsync(new RobotCommand { Description = $"Raw data sent: {Convert.ToHexString(data)}" }, true);
                return true;
            }
            catch (Exception ex)
            {
                await _logger.LogErrorAsync("Failed to send raw data", ex);
                ErrorOccurred?.Invoke(this, $"Send failed: {ex.Message}");
                return false;
            }
        }

        private async void OnCharacteristicValueChanged(object? sender, GattCharacteristicValueChangedEventArgs e)
        {
            try
            {
                var data = e.Value;
                if (data?.Length > 0)
                {
                    // Try to decode as text first
                    string message;
                    try
                    {
                        message = Encoding.UTF8.GetString(data).Trim();
                        if (string.IsNullOrEmpty(message))
                        {
                            message = Convert.ToHexString(data);
                        }
                    }
                    catch
                    {
                        message = Convert.ToHexString(data);
                    }

                    DataReceived?.Invoke(this, message);
                    await _logger.LogDataReceivedAsync(message);
                }
            }
            catch (Exception ex)
            {
                await _logger.LogErrorAsync("Error processing received data", ex);
            }
        }
    }
}