using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Microsoft.Xna.Framework.Input;

namespace monogame_ble_controller.UI
{
    public class UIManager
    {
        private SpriteBatch spriteBatch;
        private GraphicsDeviceManager graphics;

        public UIManager(GraphicsDeviceManager graphics, SpriteBatch spriteBatch)
        {
            this.graphics = graphics;
            this.spriteBatch = spriteBatch;
        }

        public void Draw(GameTime gameTime)
        {
            spriteBatch.Begin();

            // Draw UI elements here

            spriteBatch.End();
        }

        public void HandleInput(KeyboardState keyboardState)
        {
            // Handle user input here
        }
    }
}