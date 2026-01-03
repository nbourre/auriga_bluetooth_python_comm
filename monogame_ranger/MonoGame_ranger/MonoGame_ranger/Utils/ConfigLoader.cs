using System;
using System.IO;
using Newtonsoft.Json;

namespace monogame_ble_controller.Utils
{
    public class ConfigLoader
    {
        public static T LoadConfig<T>(string filePath)
        {
            if (!File.Exists(filePath))
            {
                throw new FileNotFoundException($"Configuration file not found: {filePath}");
            }

            var json = File.ReadAllText(filePath);
            return JsonConvert.DeserializeObject<T>(json);
        }
    }
}