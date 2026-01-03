using System;
using System.Collections.Generic;
using System.Globalization;
using Newtonsoft.Json.Linq;

namespace monogame_ble_controller.Utils
{
    public static class PayloadHelper
    {
        /// <summary>
        /// Convert flexible payload types (string, int, IEnumerable<int>, JSON arrays / tokens) to byte[].
        /// Supports hex string tokens like "0xFF" or "FF" inside arrays.
        /// </summary>
        public static byte[] ToBytes(object payload)
        {
            switch (payload)
            {
                case null:
                    return Array.Empty<byte>();
                case byte[] direct:
                    return direct;
                case string str:
                    return System.Text.Encoding.UTF8.GetBytes(str);
                case int integer:
                    return new[] { (byte)(integer & 0xFF) };
                case JToken token:
                    return FromJToken(token);
                case IEnumerable<int> intEnum:
                    return EnumerateIntEnumerable(intEnum);
                case IEnumerable<object> objEnum:
                    return EnumerateObjectEnumerable(objEnum);
                default:
                    throw new ArgumentException($"Unsupported payload type: {payload.GetType()}");
            }
        }

        private static byte[] FromJToken(JToken token)
        {
            if (token.Type == JTokenType.Array)
            {
                var list = new List<byte>();
                foreach (var child in token.Children())
                {
                    switch (child.Type)
                    {
                        case JTokenType.Integer:
                            list.Add((byte)((int)child & 0xFF));
                            break;
                        case JTokenType.String:
                            var s = child.Value<string>();
                            if (TryParseByte(s, out var b)) list.Add(b);
                            else list.AddRange(System.Text.Encoding.UTF8.GetBytes(s));
                            break;
                        default:
                            // Fallback: stringify token
                            list.AddRange(System.Text.Encoding.UTF8.GetBytes(child.ToString()));
                            break;
                    }
                }
                return list.ToArray();
            }
            if (token.Type == JTokenType.Integer)
                return new[] { (byte)((int)token & 0xFF) };
            if (token.Type == JTokenType.String)
            {
                var s = token.Value<string>();
                if (TryParseByte(s, out var b)) return new[] { b };
                return System.Text.Encoding.UTF8.GetBytes(s);
            }
            // Fallback: raw string of token
            return System.Text.Encoding.UTF8.GetBytes(token.ToString());
        }

        private static bool TryParseByte(string s, out byte value)
        {
            value = 0;
            if (string.IsNullOrWhiteSpace(s)) return false;
            s = s.Trim();
            if (s.StartsWith("0x", StringComparison.OrdinalIgnoreCase)) s = s.Substring(2);
            if (byte.TryParse(s, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out value)) return true;
            if (byte.TryParse(s, NumberStyles.Integer, CultureInfo.InvariantCulture, out value)) return true;
            return false;
        }

        private static byte[] EnumerateIntEnumerable(IEnumerable<int> ints)
        {
            var list = new List<byte>();
            foreach (var i in ints) list.Add((byte)(i & 0xFF));
            return list.ToArray();
        }

        private static byte[] EnumerateObjectEnumerable(IEnumerable<object> objs)
        {
            var list = new List<byte>();
            foreach (var o in objs)
            {
                switch (o)
                {
                    case int i:
                        list.Add((byte)(i & 0xFF));
                        break;
                    case string s:
                        if (TryParseByte(s, out var b)) list.Add(b); else list.AddRange(System.Text.Encoding.UTF8.GetBytes(s));
                        break;
                    case JToken jt:
                        list.AddRange(FromJToken(jt));
                        break;
                }
            }
            return list.ToArray();
        }
    }
}