using System;
using System.Collections.Generic;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;

namespace monogame_ble_controller.UI
{
    public class TextLog
    {
        private readonly SpriteFont font;
        private readonly List<string> lines;
        private readonly int maxLines;

        public TextLog(SpriteFont font, int maxLines = 22)
        {
            this.font = font;
            this.maxLines = maxLines;
            this.lines = new List<string>();
        }

        public void Add(string message)
        {
            foreach (var line in message.Split(new[] { '\n' }, StringSplitOptions.None))
            {
                lines.Add(line);
            }
            if (lines.Count > maxLines)
            {
                lines.RemoveRange(0, lines.Count - maxLines);
            }
            Console.WriteLine(message); // also log to console
        }

        public void Draw(SpriteBatch spriteBatch, Vector2 position, Color color)
        {
            Vector2 currentPosition = position;
            foreach (var line in lines)
            {
                spriteBatch.DrawString(font, line, currentPosition, color);
                currentPosition.Y += font.LineSpacing + 2;
            }
        }
    }
}