using System;

namespace AurigaRobotControl.Core.Models
{
    public enum RobotAction
    {
        Get = 1,
        Run = 2,
        Reset = 4
    }

    public enum RobotDevice
    {
        Version = 0,
        UltrasonicSensor = 1,
        TemperatureSensor = 2,
        LightSensor = 3,
        Potentiometer = 4,
        Joystick = 5,
        Gyro = 6,
        SoundSensor = 7,
        RgbLed = 8,
        SevenSegment = 9,
        Motor = 10,
        Servo = 11,
        Encoder = 12,
        IR = 13,
        IRRemote = 14,
        PIRMotion = 15,
        Infrared = 16,
        LineFollower = 17,
        IRRemoteCode = 18,
        Shutter = 20,
        LimitSwitch = 21,
        Button = 22,
        Humiture = 23,
        FlameSensor = 24,
        GasSensor = 25,
        Compass = 26,
        TemperatureSensor1 = 27,
        Digital = 30,
        Analog = 31,
        PWM = 32,
        ServoPin = 33,
        Tone = 34,
        ButtonInner = 35,
        UltrasonicArduino = 36,
        PulseIn = 37,
        Stepper = 40,
        LEDMatrix = 41,
        Timer = 50,
        TouchSensor = 51,
        JoystickMove = 52,
        CommonCommand = 60,
        EncoderBoard = 61,
        EncoderPIDMotion = 62,
        PM25Sensor = 63,
        SmartServo = 64
    }

    public enum RobotPort
    {
        Port1 = 1,
        Port2 = 2,
        Port3 = 3,
        Port4 = 4,
        Port10 = 10
    }

    public class RobotCommand
    {
        public byte Id { get; set; }
        public RobotAction Action { get; set; }
        public RobotDevice Device { get; set; }
        public RobotPort? Port { get; set; }
        public byte? Slot { get; set; }
        public byte[]? Data { get; set; }
        public DateTime Timestamp { get; set; } = DateTime.Now;
        public string? Description { get; set; }

        public byte[] ToByteArray()
        {
            var command = new List<byte> { 0xFF, 0x55 };
            
            // Calculate length dynamically
            var length = 3; // id, action, device
            if (Port.HasValue) length++;
            if (Slot.HasValue) length++;
            if (Data != null) length += Data.Length;
            
            command.Add((byte)length);
            command.Add(Id);
            command.Add((byte)Action);
            command.Add((byte)Device);
            
            if (Port.HasValue) command.Add((byte)Port.Value);
            if (Slot.HasValue) command.Add(Slot.Value);
            if (Data != null) command.AddRange(Data);
            
            return command.ToArray();
        }
    }

    public class RgbColor
    {
        public byte Red { get; set; }
        public byte Green { get; set; }
        public byte Blue { get; set; }

        public RgbColor(byte red, byte green, byte blue)
        {
            Red = red;
            Green = green;
            Blue = blue;
        }

        public static RgbColor Black => new(0, 0, 0);
        public static RgbColor White => new(255, 255, 255);
        public static RgbColor RedColor => new(255, 0, 0);
        public static RgbColor GreenColor => new(0, 255, 0);
        public static RgbColor BlueColor => new(0, 0, 255);
        public static RgbColor Yellow => new(255, 255, 0);
        public static RgbColor Cyan => new(0, 255, 255);
        public static RgbColor Magenta => new(255, 0, 255);
    }

    public class MotorCommand
    {
        public enum Direction
        {
            Forward,
            Backward,
            Left,
            Right,
            Stop
        }

        public Direction Move { get; set; }
        public byte Speed { get; set; } = 100; // 0-255
        public int Duration { get; set; } = 0; // 0 for continuous, >0 for duration in ms
    }

    public class LedRingCommand
    {
        public byte LedIndex { get; set; } // 0-11 for individual LEDs, 255 for all
        public RgbColor Color { get; set; }

        public LedRingCommand(byte ledIndex, RgbColor color)
        {
            LedIndex = ledIndex;
            Color = color;
        }
    }
}