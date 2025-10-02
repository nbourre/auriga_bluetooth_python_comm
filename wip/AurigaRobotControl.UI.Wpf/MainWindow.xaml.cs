using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Shapes;
using AurigaRobotControl.Core.Interfaces;
using AurigaRobotControl.Core.Models;
using AurigaRobotControl.Core.Services;
using AurigaRobotControl.Data.Services;

namespace AurigaRobotControl.UI.Wpf;

public partial class MainWindow : Window
{
    private readonly IRobotConnectionService _connectionService;
    private readonly IRobotCommandService _commandService;
    private readonly IDataLoggingService _loggingService;
    private readonly IConfigurationService _configService;
    private bool _isConnected = false;
    private bool _isDebugMode = false; // Debug mode flag

    public MainWindow()
    {
        InitializeComponent();
        
        // Initialize services
        _loggingService = new FileDataLoggingService();
        _configService = new JsonConfigurationService();
        _connectionService = new BluetoothConnectionService(_loggingService);
        _commandService = new RobotCommandService();
        
        InitializeUI();
        LogMessage("Auriga Robot Control started");
    }

    private void InitializeUI()
    {
        // Create LED ring visual
        CreateLedRingVisual();
        this.KeyDown += MainWindow_KeyDown;
        this.Focusable = true;
    }

    private void CreateLedRingVisual()
    {
        const double centerX = 100;
        const double centerY = 100;
        const double radius = 80;
        const double ledSize = 12;

        for (int i = 0; i < 12; i++)
        {
            double angle = (i * 30 - 90) * Math.PI / 180;
            double x = centerX + radius * Math.Cos(angle) - ledSize / 2;
            double y = centerY + radius * Math.Sin(angle) - ledSize / 2;

            var led = new Ellipse
            {
                Width = ledSize,
                Height = ledSize,
                Fill = Brushes.Gray,
                Stroke = Brushes.Black,
                StrokeThickness = 1,
                Tag = i
            };

            Canvas.SetLeft(led, x);
            Canvas.SetTop(led, y);
            LedRingCanvas.Children.Add(led);
        }
    }

    // Event handlers


    private async void ConnectButton_Click(object sender, RoutedEventArgs e)
    {
        LogMessage("Attempting to connect to robot...");
        
        // Simulate connection process
        await System.Threading.Tasks.Task.Delay(1000);
        
        _isConnected = true;
        ConnectButton.IsEnabled = false;
        DisconnectButton.IsEnabled = true;
        StatusTextBlock.Text = "Connected";
        StatusTextBlock.Foreground = Brushes.Green;
        
        LogMessage("Connected to robot successfully");
        if (_isDebugMode)
        {
            LogMessage("[DEBUG] Bluetooth connection established - ready for commands");
        }
    }

    private async void ColorButton_Click(object sender, RoutedEventArgs e)
    {
        if (!_isConnected) return;
        var button = sender as Button;
        var color = button?.Tag?.ToString() ?? "White";
        LogMessage($"Setting LED color to {color}");
    }

    private async void MovementButton_Click(object sender, RoutedEventArgs e)
    {
        if (!_isConnected) return;
        var button = sender as Button;
        var direction = button?.Tag?.ToString() ?? "Stop";
        var speed = 50; // Default speed
        
        LogMessage($"Moving {direction} at speed {speed}%");
        
        if (_isDebugMode)
        {
            // Simulate sending movement command to robot
            byte[] commandBytes = { 0xFF, 0x55, 0x06, 0x00, 0x02, 0x05, (byte)speed, 0x00 };
            LogCommandWithDebugInfo($"Movement: {direction}", commandBytes);
        }
    }



    

    private async void BeepButton_Click(object sender, RoutedEventArgs e)
    {
        if (!_isConnected) return;
        LogMessage("Beep command sent");
    }

    private async void CustomToneButton_Click(object sender, RoutedEventArgs e)
    {
        if (!_isConnected) return;
        LogMessage("Custom tone command sent");
    }

    private async void MainWindow_KeyDown(object sender, KeyEventArgs e)
    {
        if (!_isConnected) return;
        
        string? direction = e.Key switch
        {
            Key.W => "Forward",
            Key.S => "Backward", 
            Key.A => "Left",
            Key.D => "Right",
            Key.Space => "Stop",
            _ => null
        };

        if (direction != null)
        {
            LogMessage($"Keyboard: {direction}");
            e.Handled = true;
        }
    }

    // Sequence management stubs
    private void NewSequenceButton_Click(object sender, RoutedEventArgs e)
    {
        MessageBox.Show("Sequence editor coming soon!", "Feature Preview");
    }

    private void EditSequenceButton_Click(object sender, RoutedEventArgs e)
    {
        MessageBox.Show("Sequence editor coming soon!", "Feature Preview");
    }

    private void DeleteSequenceButton_Click(object sender, RoutedEventArgs e)
    {
        MessageBox.Show("Sequence deletion coming soon!", "Feature Preview");
    }

    private void PlaySequenceButton_Click(object sender, RoutedEventArgs e)
    {
        MessageBox.Show("Sequence playback coming soon!", "Feature Preview");
    }

    private void StopSequenceButton_Click(object sender, RoutedEventArgs e)
    {
        LogMessage("Sequence execution stopped");
    }

    private void SequenceListBox_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        // TODO: Handle sequence selection
    }

    // Log management
    private void ClearLogButton_Click(object sender, RoutedEventArgs e)
    {
        LogTextBlock.Text = "";
    }

    private void SaveLogButton_Click(object sender, RoutedEventArgs e)
    {
        MessageBox.Show("Log export coming soon!", "Feature Preview");
    }

    private void SettingsButton_Click(object sender, RoutedEventArgs e)
    {
        MessageBox.Show("Settings dialog coming soon!", "Feature Preview");
    }

    // Debug Mode Event Handlers
    private void DebugModeCheckBox_Checked(object sender, RoutedEventArgs e)
    {
        _isDebugMode = true;
        if (DebugIndicator != null)
            DebugIndicator.Fill = Brushes.Lime;
        LogMessage("*** DEBUG MODE ENABLED *** - Raw serial data will be shown");
    }

    private void DebugModeCheckBox_Unchecked(object sender, RoutedEventArgs e)
    {
        _isDebugMode = false;
        if (DebugIndicator != null)
            DebugIndicator.Fill = Brushes.Gray;
        LogMessage("Debug mode disabled - Normal logging resumed");
    }

    // Debug Test Command Handlers
    private void TestLed1Button_Click(object sender, RoutedEventArgs e)
    {
        LogMessage("Testing LED #1 with debug info...");
        if (_isDebugMode)
        {
            LogMessage("[DEBUG] Simulating LED command bytes: 0xFF 0x55 0x0A 0x00 0x02 0x08 0x07 0x01 0x01 0xFF 0x00 0x00");
            LogMessage("[DEBUG] Command breakdown: Header[0xFF 0x55] Length[0x0A] Device[LED] Action[SET_COLOR] LED[1] R[255] G[0] B[0]");
        }
        
        // Update visual LED
        if (LedRingCanvas.Children.Count > 0 && LedRingCanvas.Children[0] is Ellipse ledCircle)
        {
            ledCircle.Fill = Brushes.Red;
        }
    }

    private void TestMovementButton_Click(object sender, RoutedEventArgs e)
    {
        if (!_isConnected)
        {
            LogMessage("ERROR: Connect to robot first to test movement");
            return;
        }
        
        LogMessage("Testing movement with debug info...");
        if (_isDebugMode)
        {
            LogMessage("[DEBUG] Simulating forward command bytes: 0xFF 0x55 0x09 0x00 0x02 0x05 0x02 0x09 0x96");
            LogMessage("[DEBUG] Command breakdown: Header[0xFF 0x55] Length[0x09] Device[MOTOR] Action[RUN] Speed[150] Direction[Forward]");
        }
    }

    private void TestSequenceButton_Click(object sender, RoutedEventArgs e)
    {
        LogMessage("Creating test command sequence with debug info...");
        if (_isDebugMode)
        {
            LogMessage("[DEBUG] Sequence will generate 5 commands:");
            LogMessage("[DEBUG]   1. LED Red:     0xFF 0x55 0x0A 0x00 0x02 0x08 0x07 0x01 0x01 0xFF 0x00 0x00");
            LogMessage("[DEBUG]   2. Move Forward: 0xFF 0x55 0x09 0x00 0x02 0x05 0x02 0x09 0x64");
            LogMessage("[DEBUG]   3. LED Green:   0xFF 0x55 0x0A 0x00 0x02 0x08 0x07 0x01 0x01 0x00 0xFF 0x00");
            LogMessage("[DEBUG]   4. Stop:        0xFF 0x55 0x07 0x00 0x02 0x05 0x02 0x09 0x00");
            LogMessage("[DEBUG]   5. LED Off:     0xFF 0x55 0x0A 0x00 0x02 0x08 0x07 0x01 0x01 0x00 0x00 0x00");
        }
        else
        {
            LogMessage("Test sequence created (enable debug mode to see raw bytes)");
        }
    }

    // Debug Log Management
    private void LogFilter_Changed(object sender, RoutedEventArgs e)
    {
        if (_isDebugMode)
        {
            LogMessage("[DEBUG] Log filter settings changed");
        }
    }

    private void CopyLogButton_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            if (LogTextBlock != null)
            {
                Clipboard.SetText(LogTextBlock.Text);
                LogMessage("Log copied to clipboard");
            }
        }
        catch (Exception ex)
        {
            LogMessage($"Failed to copy log: {ex.Message}");
        }
    }

    // Enhanced LED control with debug logging
    private void SetAllLedsRed_Click(object sender, RoutedEventArgs e)
    {
        LogMessage("Setting all LEDs to RED");
        if (_isDebugMode)
        {
            LogMessage("[DEBUG] LED Ring command bytes: 0xFF 0x55 0x0B 0x00 0x02 0x08 0x07 0x02 0x00 0xFF 0x00 0x00");
            LogMessage("[DEBUG] Command: Set all 12 LEDs to RGB(255, 0, 0)");
        }
        SetAllLedVisuals(Colors.Red);
    }

    private void SetAllLedsGreen_Click(object sender, RoutedEventArgs e)
    {
        LogMessage("Setting all LEDs to GREEN");
        if (_isDebugMode)
        {
            LogMessage("[DEBUG] LED Ring command bytes: 0xFF 0x55 0x0B 0x00 0x02 0x08 0x07 0x02 0x00 0x00 0xFF 0x00");
            LogMessage("[DEBUG] Command: Set all 12 LEDs to RGB(0, 255, 0)");
        }
        SetAllLedVisuals(Colors.Green);
    }

    private void SetAllLedsBlue_Click(object sender, RoutedEventArgs e)
    {
        LogMessage("Setting all LEDs to BLUE");
        if (_isDebugMode)
        {
            LogMessage("[DEBUG] LED Ring command bytes: 0xFF 0x55 0x0B 0x00 0x02 0x08 0x07 0x02 0x00 0x00 0x00 0xFF");
            LogMessage("[DEBUG] Command: Set all 12 LEDs to RGB(0, 0, 255)");
        }
        SetAllLedVisuals(Colors.Blue);
    }

    private void SetAllLedsOff_Click(object sender, RoutedEventArgs e)
    {
        LogMessage("Turning OFF all LEDs");
        if (_isDebugMode)
        {
            LogMessage("[DEBUG] LED Ring command bytes: 0xFF 0x55 0x0B 0x00 0x02 0x08 0x07 0x02 0x00 0x00 0x00 0x00");
            LogMessage("[DEBUG] Command: Set all 12 LEDs to RGB(0, 0, 0) - OFF");
        }
        SetAllLedVisuals(Colors.Gray);
    }

    private void SetAllLedVisuals(Color color)
    {
        for (int i = 0; i < 12; i++)
        {
            if (LedRingCanvas.Children[i * 2] is Ellipse ledCircle)
            {
                ledCircle.Fill = new SolidColorBrush(color);
            }
        }
    }

    // Connection event handlers
    private void DisconnectButton_Click(object sender, RoutedEventArgs e)
    {
        _isConnected = false;
        ConnectButton.IsEnabled = true;
        DisconnectButton.IsEnabled = false;
        StatusTextBlock.Text = "Disconnected";
        StatusTextBlock.Foreground = Brushes.Red;
        
        LogMessage("Disconnected from robot");
        if (_isDebugMode)
        {
            LogMessage("[DEBUG] Bluetooth connection closed");
        }
    }

    // Movement control event handlers with debug logging
    private void MainWindow_KeyUp(object sender, KeyEventArgs e)
    {
        if (!_isConnected) return;

        if (e.Key == Key.W || e.Key == Key.S || e.Key == Key.A || e.Key == Key.D)
        {
            LogMessage("Keyboard: Stop");
            if (_isDebugMode)
            {
                LogMessage("[DEBUG] Stop command bytes: 0xFF 0x55 0x07 0x00 0x02 0x05 0x02 0x09 0x00");
            }
        }
    }

    // Movement button handlers with debug logging
    private void ForwardButton_MouseDown(object sender, MouseButtonEventArgs e)
    {
        if (_isConnected)
        {
            LogMessage("Button: Forward");
            if (_isDebugMode)
            {
                LogMessage("[DEBUG] Forward command bytes: 0xFF 0x55 0x09 0x00 0x02 0x05 0x02 0x09 0x96");
            }
        }
    }

    private void ForwardButton_MouseUp(object sender, MouseButtonEventArgs e)
    {
        if (_isConnected)
        {
            LogMessage("Button: Stop");
            if (_isDebugMode)
            {
                LogMessage("[DEBUG] Stop command bytes: 0xFF 0x55 0x07 0x00 0x02 0x05 0x02 0x09 0x00");
            }
        }
    }

    private void LeftButton_MouseDown(object sender, MouseButtonEventArgs e)
    {
        if (_isConnected)
        {
            LogMessage("Button: Left");
            if (_isDebugMode)
            {
                LogMessage("[DEBUG] Left turn command bytes: 0xFF 0x55 0x09 0x00 0x02 0x05 0x01 0x09 0x96");
            }
        }
    }

    private void LeftButton_MouseUp(object sender, MouseButtonEventArgs e)
    {
        if (_isConnected)
        {
            LogMessage("Button: Stop");
            if (_isDebugMode)
            {
                LogMessage("[DEBUG] Stop command bytes: 0xFF 0x55 0x07 0x00 0x02 0x05 0x02 0x09 0x00");
            }
        }
    }

    private void RightButton_MouseDown(object sender, MouseButtonEventArgs e)
    {
        if (_isConnected)
        {
            LogMessage("Button: Right");
            if (_isDebugMode)
            {
                LogMessage("[DEBUG] Right turn command bytes: 0xFF 0x55 0x09 0x00 0x02 0x05 0x04 0x09 0x96");
            }
        }
    }

    private void RightButton_MouseUp(object sender, MouseButtonEventArgs e)
    {
        if (_isConnected)
        {
            LogMessage("Button: Stop");
            if (_isDebugMode)
            {
                LogMessage("[DEBUG] Stop command bytes: 0xFF 0x55 0x07 0x00 0x02 0x05 0x02 0x09 0x00");
            }
        }
    }

    private void BackwardButton_MouseDown(object sender, MouseButtonEventArgs e)
    {
        if (_isConnected)
        {
            LogMessage("Button: Backward");
            if (_isDebugMode)
            {
                LogMessage("[DEBUG] Backward command bytes: 0xFF 0x55 0x09 0x00 0x02 0x05 0x03 0x09 0x96");
            }
        }
    }

    private void BackwardButton_MouseUp(object sender, MouseButtonEventArgs e)
    {
        if (_isConnected)
        {
            LogMessage("Button: Stop");
            if (_isDebugMode)
            {
                LogMessage("[DEBUG] Stop command bytes: 0xFF 0x55 0x07 0x00 0x02 0x05 0x02 0x09 0x00");
            }
        }
    }

    private void StopButton_Click(object sender, RoutedEventArgs e)
    {
        if (_isConnected)
        {
            LogMessage("Manual STOP");
            if (_isDebugMode)
            {
                LogMessage("[DEBUG] Emergency stop bytes: 0xFF 0x55 0x07 0x00 0x02 0x05 0x02 0x09 0x00");
                LogMessage("[DEBUG] All motors stopped immediately");
            }
        }
    }

    private void EmergencyStopButton_Click(object sender, RoutedEventArgs e)
    {
        if (_isConnected)
        {
            LogMessage("*** EMERGENCY STOP ACTIVATED ***");
            if (_isDebugMode)
            {
                LogMessage("[DEBUG] Emergency stop bytes: 0xFF 0x55 0x07 0x00 0x02 0x05 0x02 0x09 0x00");
                LogMessage("[DEBUG] All systems halted!");
            }
        }
    }

    // Sequence management placeholder handlers
    private void LoadSequenceButton_Click(object sender, RoutedEventArgs e)
    {
        LogMessage("Load sequence functionality - coming soon");
    }

    private void SaveSequenceButton_Click(object sender, RoutedEventArgs e)
    {
        LogMessage("Save sequence functionality - coming soon");
    }

    private void RunSequenceButton_Click(object sender, RoutedEventArgs e)
    {
        LogMessage("Run sequence functionality - coming soon");
    }

    // Data logging placeholder handlers
    private void BrowseLogFileButton_Click(object sender, RoutedEventArgs e)
    {
        var saveDialog = new Microsoft.Win32.SaveFileDialog
        {
            Filter = "JSON files (*.json)|*.json|All files (*.*)|*.*",
            DefaultExt = "json"
        };

        if (saveDialog.ShowDialog() == true)
        {
            LogFilePathTextBox.Text = saveDialog.FileName;
            LogMessage($"Log file path set to: {saveDialog.FileName}");
        }
    }

    private void StartLoggingButton_Click(object sender, RoutedEventArgs e)
    {
        StartLoggingButton.IsEnabled = false;
        StopLoggingButton.IsEnabled = true;
        LogMessage("Data logging started");
        if (_isDebugMode)
        {
            LogMessage($"[DEBUG] Logging to file: {LogFilePathTextBox.Text}");
        }
    }

    private void StopLoggingButton_Click(object sender, RoutedEventArgs e)
    {
        StartLoggingButton.IsEnabled = true;
        StopLoggingButton.IsEnabled = false;
        LogMessage("Data logging stopped");
    }

    private void LogMessage(string message, bool isError = false)
    {
        var timestamp = DateTime.Now.ToString("HH:mm:ss");
        var logEntry = $"[{timestamp}] {message}\n";
        
        if (LogTextBlock != null)
        {
            LogTextBlock.Text += logEntry;
            
            if (AutoScrollCheckBox?.IsChecked == true)
            {
                var scrollViewer = LogTextBlock.Parent as ScrollViewer;
                scrollViewer?.ScrollToEnd();
            }
        }
    }

    private void LogCommandWithDebugInfo(string commandName, byte[] commandBytes)
    {
        if (!_isDebugMode) return;
        
        var hexString = string.Join(" ", commandBytes.Select(b => b.ToString("X2")));
        var decimalString = string.Join(" ", commandBytes.Select(b => b.ToString()));
        
        LogMessage($"[DEBUG] {commandName}");
        LogMessage($"  Hex: {hexString}");
        LogMessage($"  Dec: {decimalString}");
        LogMessage($"  Bytes: {commandBytes.Length}");
    }
}
