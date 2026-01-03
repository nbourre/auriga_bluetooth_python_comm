using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Microsoft.Xna.Framework.Input;
using Newtonsoft.Json.Linq;
using monogame_ble_controller.Controllers;
using monogame_ble_controller.UI;
using monogame_ble_controller.Utils;

namespace monogame_ble_controller
{
    /// <summary>
    /// Main MonoGame loop implementing BLE robot controller functionality inspired by gui_ble_pygame.py.
    /// </summary>
    public class Game1 : Game
    {
        private readonly GraphicsDeviceManager _graphics;
        private SpriteBatch _spriteBatch;
        private SpriteFont _font;
        private TextLog _log;

        // BLE
        private readonly BleController _ble = new();
        private int _selectedIdx = 0;

        // Config & actions
        private byte[] _header = new byte[] { 0xFF, 0x55 };
        private bool _useHeader = false;
        private string _lineEndingKey = "BOTH";
        private readonly Dictionary<string, JToken> _directions = new();
        private JToken _stopToken; // direction stop payload
        private class ActionItem { public string Key; public JToken Data; public string Label; public byte[] Cached; }
        private readonly List<ActionItem> _actions = new();
        private readonly Dictionary<Keys, ActionItem> _actionKeyMap = new();

        // Direction streaming
        private string _currentDir;
        private byte[] _currentDirPayload;
        private double _frequencyHz = 10.0;
        private double _periodSeconds = 0.1;
        private DateTime _lastSent = DateTime.MinValue;
        private readonly Thread _dirThread;
        private volatile bool _dirThreadRun = true;
        private readonly HashSet<string> _pressed = new();

        // Manual text input
        private bool _textInputMode = false;
        private readonly StringBuilder _textBuffer = new();

        // Input tracking
        private KeyboardState _prevKeyboard;

        // Line endings mapping
        private static readonly Dictionary<string, byte[]> LineEndings = new()
        {
            {"NL", new byte[]{ (byte)'\n'}},
            {"CR", new byte[]{ (byte)'\r'}},
            {"BOTH", new byte[]{ (byte)'\r', (byte)'\n'}},
            {"NONE", Array.Empty<byte>()}
        };
        private static readonly string[] LineEndingCycle = {"BOTH","NL","CR","NONE"};

        public Game1()
        {
            _graphics = new GraphicsDeviceManager(this);
            Content.RootDirectory = "Content";
            IsMouseVisible = true;
            _dirThread = new Thread(DirectionLoop) { IsBackground = true };
            _dirThread.Start();

            // BLE events
            _ble.DeviceDiscovered += d => _log?.Add($"Device: {d.Name} [{d.Id}]");
            _ble.DeviceConnected += d => _log?.Add($"Connected: {d.Name}");
            _ble.DeviceDisconnected += d => _log?.Add($"Disconnected: {d.Name}");
            _ble.DataReceived += bytes => _log?.Add($"RX: {BitConverter.ToString(bytes)}");
            _ble.Error += ex => _log?.Add($"BLE Error: {ex.Message}");
        }

        protected override void Initialize()
        {
            LoadActionsConfig();
            base.Initialize();
        }

        protected override void LoadContent()
        {
            _spriteBatch = new SpriteBatch(GraphicsDevice);
            _font = Content.Load<SpriteFont>("DefaultFont"); // ensure Content/DefaultFont.spritefont exists
            _log = new TextLog(_font);
            _log.Add("Press C to scan devices.");
        }

        protected override void Update(GameTime gameTime)
        {
            var kb = Keyboard.GetState();
            HandleInput(kb, _prevKeyboard);
            _prevKeyboard = kb;
            base.Update(gameTime);
        }

        protected override void Draw(GameTime gameTime)
        {
            GraphicsDevice.Clear(new Color(30,30,34));
            _spriteBatch.Begin();
            var fg = new Color(230,230,230);
            float y = 10;
            DrawLine("MonoGame BLE Robot Controller", fg, ref y);
            var status = _ble.IsConnected ? $"CONNECTED: {_ble.ConnectedDeviceName}" : "DISCONNECTED";
            DrawLine($"Status: {status}", fg, ref y);
            DrawLine($"Header: {(_useHeader?"ON":"OFF")}  LineEnd: {_lineEndingKey}  Freq: {_frequencyHz:F1}Hz", fg, ref y);
            DrawLine("Controls: C=Scan  ENTER=Connect  UP/DOWN=Select  H=Header  F=LineEnd  +/-=Freq  T=Type  ESC=Quit/Disc", fg, ref y);
            y += 8;
            DrawLine("Devices:", fg, ref y);
            var devices = _ble.DiscoveredDevices;
            for(int i=0;i<devices.Count;i++)
            {
                var pref = (i==_selectedIdx)?">":" ";
                DrawLine($"{pref} {devices[i].Name} [{devices[i].Id}]", i==_selectedIdx?Color.LightSkyBlue:fg, ref y);
            }
            y += 8;
            DrawLine("Log:", fg, ref y);
            _log.Draw(_spriteBatch, new Vector2(10, y), fg);
            if (_textInputMode)
            {
                _spriteBatch.DrawString(_font, "> "+_textBuffer.ToString(), new Vector2(10, GraphicsDevice.Viewport.Height - 40), Color.Yellow);
            }
            _spriteBatch.End();
            base.Draw(gameTime);
        }

        private void DrawLine(string text, Color color, ref float y)
        {
            _spriteBatch.DrawString(_font, text, new Vector2(10,y), color);
            y += _font.LineSpacing + 2;
        }

        private void HandleInput(KeyboardState kb, KeyboardState prev)
        {
            bool Just(Keys k) => kb.IsKeyDown(k) && !prev.IsKeyDown(k);
            if (_textInputMode)
            {
                HandleTextInput(kb, prev);
                return;
            }

            if (Just(Keys.C)) _ = ScanAsync();
            if (Just(Keys.Enter)) _ = ConnectSelectedAsync();
            if (Just(Keys.Up)) _selectedIdx = Math.Max(0,_selectedIdx-1);
            if (Just(Keys.Down)) _selectedIdx = Math.Min(_ble.DiscoveredDevices.Count-1,_selectedIdx+1);
            if (Just(Keys.H)) { _useHeader = !_useHeader; _log.Add($"Header: {(_useHeader?"ON":"OFF")}"); }
            if (Just(Keys.F)) CycleLineEnding();
            if (Just(Keys.OemPlus) || Just(Keys.Add)) SetFrequency(_frequencyHz+1);
            if (Just(Keys.OemMinus) || Just(Keys.Subtract)) SetFrequency(_frequencyHz-1);
            if (Just(Keys.T)) { _textInputMode = true; _textBuffer.Clear(); _log.Add("Text input mode ON"); }
            if (Just(Keys.Escape)) { if (_ble.IsConnected) _ = _ble.DisconnectAsync(); else Exit(); }

            // Direction keys W A S D E
            foreach (var entry in new[]{Keys.W,Keys.A,Keys.S,Keys.D,Keys.E})
            {
                var keyStr = entry.ToString().ToLowerInvariant();
                if (kb.IsKeyDown(entry) && !prev.IsKeyDown(entry))
                {
                    _pressed.Add(keyStr);
                    StartDirection(keyStr);
                }
                if (!kb.IsKeyDown(entry) && prev.IsKeyDown(entry) && _pressed.Contains(keyStr))
                {
                    _pressed.Remove(keyStr);
                    if (_currentDir == keyStr) SendStop();
                }
            }

            // Action keys
            foreach (var kv in _actionKeyMap)
                if (Just(kv.Key)) TriggerAction(kv.Value);
        }

        private void HandleTextInput(KeyboardState kb, KeyboardState prev)
        {
            bool Just(Keys k) => kb.IsKeyDown(k) && !prev.IsKeyDown(k);
            foreach (Keys k in Enum.GetValues(typeof(Keys)))
            {
                if (!Just(k)) continue;
                if (k == Keys.Enter)
                {
                    var txt = _textBuffer.ToString();
                    _textInputMode = false;
                    SendText(txt);
                    _log.Add($"Sent text: {txt}");
                    return;
                }
                if (k == Keys.Escape)
                {
                    _textInputMode = false; _log.Add("Text input cancelled"); return;
                }
                if (k == Keys.Back && _textBuffer.Length>0) { _textBuffer.Length--; continue; }
                var ch = KeyToChar(k, kb);
                if (ch!=null) _textBuffer.Append(ch);
            }
        }

        private static string KeyToChar(Keys key, KeyboardState kb)
        {
            bool shift = kb.IsKeyDown(Keys.LeftShift) || kb.IsKeyDown(Keys.RightShift);
            if (key >= Keys.A && key <= Keys.Z)
            {
                char c = (char)('a' + (key - Keys.A));
                return shift? char.ToUpper(c).ToString(): c.ToString();
            }
            if (key >= Keys.D0 && key <= Keys.D9)
                return ((char)('0' + (key - Keys.D0))).ToString();
            return key switch
            {
                Keys.Space => " ",
                Keys.OemPeriod => ".",
                Keys.OemComma => ",",
                Keys.OemMinus => "-",
                Keys.OemPlus => "+",
                _ => null
            };
        }

        private async Task ScanAsync()
        {
            try
            {
                _log.Add("Scanning...");
                await _ble.ScanAsync(TimeSpan.FromSeconds(6));
                _log.Add($"Found {_ble.DiscoveredDevices.Count} devices");
                _selectedIdx = Math.Min(_selectedIdx, _ble.DiscoveredDevices.Count-1);
            }
            catch (Exception ex) { _log.Add("Scan error: "+ex.Message); }
        }

        private async Task ConnectSelectedAsync()
        {
            if (_ble.DiscoveredDevices.Count == 0) { _log.Add("No devices to connect"); return; }
            if (_selectedIdx<0 || _selectedIdx>=_ble.DiscoveredDevices.Count) { _log.Add("Selection out of range"); return; }
            var dev = _ble.DiscoveredDevices[_selectedIdx];
            try { await _ble.ConnectAsync(dev); } catch (Exception ex) { _log.Add("Connect error: "+ex.Message); }
        }

        private void LoadActionsConfig()
        {
            try
            {
                var path = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "..", "actions.json");
                if (!File.Exists(path)) { return; }
                var root = JToken.Parse(File.ReadAllText(path));
                var headerTok = root["header"];
                if (headerTok is JArray hdrArr)
                    _header = hdrArr.Select(h => (byte)h.Value<int>()).ToArray();
                var dirTok = root["directions"] as JObject;
                if (dirTok!=null)
                {
                    foreach (var kv in dirTok.Properties())
                    {
                        _directions[kv.Name] = kv.Value;
                        if (kv.Name == "stop") _stopToken = kv.Value;
                    }
                }
                _actions.Clear(); _actionKeyMap.Clear();
                if (root["actions"] is JArray actArr)
                {
                    foreach (var act in actArr.OfType<JObject>())
                    {
                        var key = act.Value<string>("key");
                        var label = act.Value<string>("label") ?? key;
                        var data = act["data"] ?? JValue.CreateNull();
                        if (Enum.TryParse<Keys>(key, true, out var monoKey))
                        {
                            var item = new ActionItem { Key = key, Label = label, Data = data };
                            _actions.Add(item);
                            _actionKeyMap[monoKey] = item;
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine("Config load error: "+ex.Message);
            }
        }

        private void StartDirection(string key)
        {
            if (!_ble.IsConnected) { _log.Add("Not connected"); return; }
            if (!_directions.TryGetValue(key, out var token)) { _log.Add($"No direction for {key}"); return; }
            try
            {
                var payloadCore = PayloadHelper.ToBytes(token);
                var ending = LineEndings[_lineEndingKey];
                var full = BuildPayload(payloadCore, ending);
                _currentDir = key;
                _currentDirPayload = full;
                _ = _ble.SendAsync(full);
                _lastSent = DateTime.UtcNow;
                _log.Add("Dir: "+key);
            }
            catch (Exception ex) { _log.Add("Dir error: "+ex.Message); }
        }

        private void SendStop()
        {
            if (!_ble.IsConnected || _stopToken == null) return;
            try
            {
                var payloadCore = PayloadHelper.ToBytes(_stopToken);
                var ending = LineEndings[_lineEndingKey];
                var full = BuildPayload(payloadCore, ending);
                _ = _ble.SendAsync(full);
                _log.Add("Stop sent");
            } catch (Exception ex) { _log.Add("Stop error: "+ex.Message); }
            _currentDir = null; _currentDirPayload = null;
        }

        private void DirectionLoop()
        {
            while (_dirThreadRun)
            {
                if (_ble.IsConnected && _currentDirPayload != null)
                {
                    var elapsed = (DateTime.UtcNow - _lastSent).TotalSeconds;
                    if (elapsed >= _periodSeconds)
                    {
                        _ = _ble.SendAsync(_currentDirPayload);
                        _lastSent = DateTime.UtcNow;
                    }
                }
                Thread.Sleep(10);
            }
        }

        private void TriggerAction(ActionItem act)
        {
            if (!_ble.IsConnected) { _log.Add("Not connected"); return; }
            try
            {
                if (act.Cached == null)
                {
                    var core = PayloadHelper.ToBytes(act.Data);
                    var ending = LineEndings[_lineEndingKey];
                    act.Cached = BuildPayload(core, ending);
                }
                _ = _ble.SendAsync(act.Cached);
                _log.Add("Action: "+act.Label);
            }
            catch (Exception ex) { _log.Add("Action error: "+ex.Message); }
        }

        private void SendText(string text)
        {
            if (!_ble.IsConnected) { _log.Add("Not connected"); return; }
            var core = Encoding.UTF8.GetBytes(text);
            var ending = LineEndings[_lineEndingKey];
            var payload = BuildPayload(core, ending);
            _ = _ble.SendAsync(payload);
        }

        private byte[] BuildPayload(byte[] core, byte[] ending)
        {
            if (_useHeader && _header.Length>0)
            {
                var buffer = new byte[_header.Length + core.Length + ending.Length];
                Buffer.BlockCopy(_header,0,buffer,0,_header.Length);
                Buffer.BlockCopy(core,0,buffer,_header.Length,core.Length);
                Buffer.BlockCopy(ending,0,buffer,_header.Length+core.Length,ending.Length);
                return buffer;
            }
            if (ending.Length==0) return core;
            var res = new byte[core.Length+ending.Length];
            Buffer.BlockCopy(core,0,res,0,core.Length);
            Buffer.BlockCopy(ending,0,res,core.Length,ending.Length);
            return res;
        }

        private void SetFrequency(double hz)
        {
            hz = Math.Max(1.0, Math.Min(50.0, hz));
            _frequencyHz = hz; _periodSeconds = 1.0 / _frequencyHz;
            _log.Add($"Frequency: {_frequencyHz:F1} Hz");
        }

        private void CycleLineEnding()
        {
            var idx = Array.IndexOf(LineEndingCycle, _lineEndingKey);
            idx = (idx + 1) % LineEndingCycle.Length;
            _lineEndingKey = LineEndingCycle[idx];
            _log.Add("Line ending: "+_lineEndingKey);
        }

        protected override void Dispose(bool disposing)
        {
            _dirThreadRun = false;
            try { if (_dirThread != null && _dirThread.IsAlive) _dirThread.Join(200); } catch { }
            base.Dispose(disposing);
        }
    }
}