from typing import List

import pygame

from actions_config import ActionsConfig
from ble_connection import END_DATA_OPTIONS, BleConnection, LineAssembler
from drive_controller import DEFAULT_FREQUENCY_HZ, DriveController
from message_history import MessageHistory
from pygame_parts import DeviceSelector, TextInputBox, key_to_char

LINE_ENDING_ORDER = ['NL', 'CR', 'BOTH', 'NONE']

# -----------------------------
# Pygame UI helpers
# -----------------------------
class TextLog:
    def __init__(self, font: pygame.font.Font, max_lines: int = 22):
        self.font = font
        self.max_lines = max_lines
        self.lines: List[str] = []
    
    def add(self, msg: str) -> None:
        for line in msg.splitlines():
            self.lines.append(line)
        if len(self.lines) > self.max_lines:
            self.lines = self.lines[-self.max_lines:]
        print(msg, end="")  # also log to console

    def draw(self, surface: pygame.Surface, x: int, y: int, color=(230,230,230)) -> None:
        yy = y
        for line in self.lines:
            img = self.font.render(line, True, color)
            surface.blit(img, (x, yy))
            yy += img.get_height() + 2


# -----------------------------
# Main App
# -----------------------------
class App:
    WIDTH = 960
    HEIGHT = 640
    BG = (25, 28, 34)
    FG = (235, 235, 235)
    ACCENT = (80, 180, 255)

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("BLE Robot Controller (Pygame)")
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 22)
        self.font_small = pygame.font.SysFont(None, 18)

        # Runtime options
        self.use_header = False
        self.line_ending_key = 'BOTH'
        self.frequency = float(DEFAULT_FREQUENCY_HZ)

        # Components
        self.log = TextLog(self.font)
        self.conn = BleConnection()
        self.conn.log.connect(self.log.add)
        self.conn.rx.connect(self._on_rx)
        self.conn.payload_wrapper = self._add_header
        self._rx_lines = LineAssembler()

        self.actions_config = ActionsConfig()
        self.actions_config.load()
        self.log.add(f"Loaded actions.json. Header: [{self.actions_config.header_hex}]\n")

        self.devices = DeviceSelector(self.conn)
        self.drive = DriveController(self.conn, self.actions_config, self._end_data, self.frequency)
        self.text_input = TextInputBox(self._send_manual_text, MessageHistory.per_user())

        # UI state
        self.running = True
        self.mode = 'scanning'  # 'idle' | 'scanning' | 'connected' | 'select'

        # initial scan to speed things up
        self.conn.scan(6.0)

    # ----------- helpers -----------
    def _end_data(self) -> bytes:
        return END_DATA_OPTIONS.get(self.line_ending_key, b'')

    def _add_header(self, payload: bytes) -> bytes:
        return self.actions_config.with_header(payload) if self.use_header else payload

    def _on_rx(self, chunk: str) -> None:
        """Log every complete non-empty line received (called from the BLE thread)."""
        for line in self._rx_lines.feed(chunk):
            line = line.strip()
            if line:
                self.log.add(f"Received: {line}\n")

    def _send_manual_text(self, text: str) -> bool:
        """Send manually typed text. Returns True if it was sent."""
        if not self.conn.send_text(text, self._end_data()):
            return False
        hdr_info = " (with header)" if self.use_header else ""
        self.log.add(f"Sent: {text}{hdr_info}\n")
        return True

    # ----------- rendering -----------
    def draw_header(self) -> None:
        y = 10
        def line(text: str, color=self.FG):
            img = self.font.render(text, True, color)
            self.screen.blit(img, (16, y))
            return y + img.get_height() + 6
        y = line("BLE Robot Controller (Pygame)", self.ACCENT)
        status = "CONNECTED" if self.conn.is_connected else "DISCONNECTED"
        y = line(f"Status: {status}")
        hdr = 'ON' if self.use_header else 'OFF'
        y = line(f"Header: {hdr}  |  Line Ending: {self.line_ending_key}  |  Frequency: {self.frequency:.1f} Hz")
        y = line("Controls: ")
        y = line("  C=Scan  ENTER=Connect  UP/DOWN=Select  H=Toggle Header  F/F1=Line Ending  +/-=Freq  T=Type  ESC=Quit/Disconnect")
        y = line("W/A/S/D/E to drive; Action keys from actions.json also work here.")

        # device list
        y += 5
        action_y = y
        if self.devices.devices:
            img = self.font.render("Devices:", True, self.FG)
            self.screen.blit(img, (16, y))
            y += img.get_height() + 6
            for i, dev in enumerate(self.devices.devices[:12]):
                sel = (i == self.devices.selected_index)
                color = self.ACCENT if sel else self.FG
                text = f"{'> ' if sel else '  '} {dev.name} ({dev.address})"
                img = self.font_small.render(text, True, color)
                self.screen.blit(img, (24, y))
                y += img.get_height() + 2
        else:
            img = self.font_small.render("No devices (press C to scan).", True, (180,180,180))
            self.screen.blit(img, (16, y))

        # actions
        ax = 520
        ay = action_y
        img = self.font.render("Actions:", True, self.FG)
        self.screen.blit(img, (ax, ay))
        ay += img.get_height() + 6
        if self.actions_config.actions:
            for act in self.actions_config.actions[:15]:
                label = (act.get("label") or act.get("key","?").upper()) + f" ({act.get('key','?').upper()})"
                img = self.font_small.render(label, True, (200,200,200))
                self.screen.blit(img, (ax+8, ay))
                ay += img.get_height() + 2
        else:
            img = self.font_small.render("No actions configured.", True, (180,180,180))
            self.screen.blit(img, (ax+8, ay))

        # log area
        pygame.draw.rect(self.screen, (40,44,52), pygame.Rect(16, ay, self.WIDTH-32, self.HEIGHT-316))
        
        self.log.draw(self.screen, 24, ay + 8)
        
        # text input overlay
        self.text_input.draw(self.screen, self.font, pygame.Rect(0, self.HEIGHT - 60, self.WIDTH, 60))

    # ----------- event handling -----------
    def handle_event(self, ev: pygame.event.Event) -> None:
        if ev.type == pygame.QUIT:
            self.running = False
        elif ev.type == pygame.KEYDOWN:
            # Text input mode captures all keys
            if self.text_input.active:
                self.text_input.handle_key(ev)
                return

            if ev.key == pygame.K_ESCAPE:
                # disconnect or quit
                if self.conn.is_connected:
                    self.conn.disconnect()
                else:
                    self.running = False
            elif ev.key == pygame.K_c:
                self.mode = 'scanning'
                self.conn.scan(6.0)
            elif ev.key == pygame.K_t:
                self.text_input.open()
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.devices.connect_selected()
            elif ev.key == pygame.K_UP:
                self.devices.move(-1)
            elif ev.key == pygame.K_DOWN:
                self.devices.move(+1)
            elif ev.key == pygame.K_h:
                self.use_header = not self.use_header
            elif ev.key in (pygame.K_f, pygame.K_F1):
                # cycle line endings
                i = LINE_ENDING_ORDER.index(self.line_ending_key) if self.line_ending_key in LINE_ENDING_ORDER else 2
                self.line_ending_key = LINE_ENDING_ORDER[(i + 1) % len(LINE_ENDING_ORDER)]
            elif ev.key in (pygame.K_PLUS, pygame.K_EQUALS):
                self.frequency = min(60.0, self.frequency + 1)
                self.drive.set_frequency(self.frequency)
            elif ev.key in (pygame.K_MINUS, pygame.K_UNDERSCORE):
                self.frequency = max(1.0, self.frequency - 1)
                self.drive.set_frequency(self.frequency)
            else:
                ch = key_to_char(ev.key)
                if ch:
                    self.drive.key_down(ch)
        elif ev.type == pygame.KEYUP:
            ch = key_to_char(ev.key)
            if ch:
                self.drive.key_up(ch)

    # ----------- main loop -----------
    def run(self) -> None:
        try:
            while self.running:
                for ev in pygame.event.get():
                    self.handle_event(ev)

                self.screen.fill(self.BG)
                self.draw_header()
                pygame.display.flip()
                self.clock.tick(60)
        finally:
            self.drive.shutdown()
            self.conn.shutdown()
            pygame.quit()


if __name__ == "__main__":
    App().run()
