using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Plugin.BLE;
using Plugin.BLE.Abstractions.Contracts;
using Plugin.BLE.Abstractions.EventArgs;
using Plugin.BLE.Abstractions.Exceptions;
using Plugin.BLE.Abstractions;

namespace monogame_ble_controller.Controllers
{
    /// <summary>
    /// Centralized BLE controller: scanning, connecting, writing, notifications.
    /// Wraps Plugin.BLE and exposes higher level events & helpers.
    /// </summary>
    public class BleController
    {
        private readonly IBluetoothLE _bluetoothLE;
        private readonly IAdapter _adapter;
        private IDevice _connectedDevice;
        private ICharacteristic _writeCharacteristic;
        private ICharacteristic _notifyCharacteristic;
        private readonly List<IDevice> _discovered = new();
        private readonly object _lock = new();

        public IReadOnlyList<IDevice> DiscoveredDevices
        {
            get { lock (_lock) return _discovered.ToList(); }
        }

        /// <summary>Optional target service UUID to narrow service search.</summary>
        public Guid? TargetServiceUuid { get; set; }
        /// <summary>Optional write characteristic UUID.</summary>
        public Guid? TargetWriteCharacteristicUuid { get; set; }
        /// <summary>Optional notify characteristic UUID.</summary>
        public Guid? TargetNotifyCharacteristicUuid { get; set; }

        public bool IsConnected => _connectedDevice != null;
        public string ConnectedDeviceName => _connectedDevice?.Name;

        public event Action<IDevice> DeviceDiscovered;
        public event Action<IDevice> DeviceConnected;
        public event Action<IDevice> DeviceDisconnected;
        public event Action<byte[]> DataReceived;
        public event Action<Exception> Error;

        public BleController()
        {
            _bluetoothLE = CrossBluetoothLE.Current;
            _adapter = CrossBluetoothLE.Current.Adapter;
            _adapter.DeviceDiscovered += Adapter_DeviceDiscovered;
            _adapter.DeviceDisconnected += Adapter_DeviceDisconnected;
        }

        private void Adapter_DeviceDiscovered(object sender, DeviceEventArgs e)
        {
            lock (_lock)
            {
                if (_discovered.All(d => d.Id != e.Device.Id))
                    _discovered.Add(e.Device);
            }
            DeviceDiscovered?.Invoke(e.Device);
        }

        private void Adapter_DeviceDisconnected(object sender, DeviceEventArgs e)
        {
            if (_connectedDevice != null && e.Device.Id == _connectedDevice.Id)
            {
                _connectedDevice = null;
                _writeCharacteristic = null;
                _notifyCharacteristic = null;
                DeviceDisconnected?.Invoke(e.Device);
            }
        }

        /// <summary>
        /// Scan for devices for a limited duration.
        /// </summary>
        public async Task<IReadOnlyList<IDevice>> ScanAsync(TimeSpan duration, CancellationToken ct = default)
        {
            if (!_bluetoothLE.IsOn)
            {
                var ex = new InvalidOperationException("Bluetooth is not enabled.");
                Error?.Invoke(ex);
                throw ex;
            }
            lock (_lock) _discovered.Clear();
            try
            {
                await _adapter.StartScanningForDevicesAsync();
                await Task.Delay(duration, ct);
            }
            catch (Exception ex)
            {
                if (ex is TaskCanceledException) { }
                else Error?.Invoke(ex);
            }
            finally
            {
                if (_adapter.IsScanning)
                {
                    try { await _adapter.StopScanningForDevicesAsync(); } catch { }
                }
            }
            return DiscoveredDevices;
        }

        public async Task ConnectAsync(IDevice device)
        {
            if (device == null) throw new ArgumentNullException(nameof(device));
            try
            {
                await _adapter.ConnectToDeviceAsync(device);
                _connectedDevice = device;
                DeviceConnected?.Invoke(device);
                await ResolveCharacteristicsAsync();
            }
            catch (Exception ex)
            {
                Error?.Invoke(ex);
                throw;
            }
        }

        public async Task DisconnectAsync()
        {
            if (_connectedDevice == null) return;
            var dev = _connectedDevice;
            try
            {
                await _adapter.DisconnectDeviceAsync(dev);
            }
            catch (Exception ex)
            {
                Error?.Invoke(ex);
            }
            finally
            {
                _connectedDevice = null;
                _writeCharacteristic = null;
                _notifyCharacteristic = null;
                DeviceDisconnected?.Invoke(dev);
            }
        }

        /// <summary>
        /// Attempts to locate write & notify characteristics based on optional target GUIDs or by capability.
        /// </summary>
        private async Task ResolveCharacteristicsAsync()
        {
            if (_connectedDevice == null) return;
            try
            {
                var services = await _connectedDevice.GetServicesAsync();
                foreach (var svc in services)
                {
                    if (TargetServiceUuid.HasValue && svc.Id != TargetServiceUuid.Value) continue;
                    var characteristics = await svc.GetCharacteristicsAsync();
                    foreach (var ch in characteristics)
                    {
                        if (_writeCharacteristic == null)
                        {
                            if (TargetWriteCharacteristicUuid.HasValue && ch.Id == TargetWriteCharacteristicUuid.Value)
                                _writeCharacteristic = ch;
                            else if (ch.CanWrite() || ch.CanWriteWithoutResponse())
                                _writeCharacteristic = ch;
                        }
                        if (_notifyCharacteristic == null)
                        {
                            if (TargetNotifyCharacteristicUuid.HasValue && ch.Id == TargetNotifyCharacteristicUuid.Value)
                                _notifyCharacteristic = ch;
                            else if (ch.CanUpdate())
                                _notifyCharacteristic = ch;
                        }
                        if (_writeCharacteristic != null && _notifyCharacteristic != null) break;
                    }
                    if (_writeCharacteristic != null && _notifyCharacteristic != null) break;
                }

                if (_notifyCharacteristic != null)
                {
                    _notifyCharacteristic.ValueUpdated += NotifyCharacteristic_ValueUpdated;
                    try { await _notifyCharacteristic.StartUpdatesAsync(); } catch (Exception ex) { Error?.Invoke(ex); }
                }
            }
            catch (Exception ex)
            {
                Error?.Invoke(ex);
            }
        }

        private void NotifyCharacteristic_ValueUpdated(object sender, CharacteristicUpdatedEventArgs e)
        {
            var val = e.Characteristic.Value;
            if (val != null && val.Length > 0)
                DataReceived?.Invoke(val);
        }

        public async Task<bool> SendAsync(byte[] data)
        {
            if (!IsConnected || _writeCharacteristic == null) return false;
            try
            {
                await _writeCharacteristic.WriteAsync(data);
                return true;
            }
            catch (Exception ex)
            {
                Error?.Invoke(ex);
                return false;
            }
        }
    }

    internal static class CharacteristicExtensions
    {
        public static bool CanWrite(this ICharacteristic ch) => ch != null && ch.Properties.HasFlag(CharacteristicPropertyType.Write);
        public static bool CanWriteWithoutResponse(this ICharacteristic ch) => ch != null && ch.Properties.HasFlag(CharacteristicPropertyType.WriteWithoutResponse);
        public static bool CanUpdate(this ICharacteristic ch) => ch != null && (ch.Properties.HasFlag(CharacteristicPropertyType.Notify) || ch.Properties.HasFlag(CharacteristicPropertyType.Indicate));
    }
}