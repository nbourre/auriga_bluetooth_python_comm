using System;

namespace monogame_ble_controller.Models
{
    public class ActionConfig
    {
        public string Key { get; set; }
        public string Data { get; set; }
        public string Label { get; set; }

        public ActionConfig(string key, string data, string label)
        {
            Key = key;
            Data = data;
            Label = label;
        }
    }
}