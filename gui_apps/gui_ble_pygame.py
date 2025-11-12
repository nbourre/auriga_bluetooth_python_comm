import os
import sys
import json
import time
import threading
import asyncio
from typing import Any, Dict, List, Optional, Union, Tuple

import pygame
from bleak import BleakClient, BleakScanner

# -----------------------------
# BLE characteristic UUIDs (adjust if your device differs)
# -----------------------------
CHARACTERISTIC_NOTIFY_UUID = "0000ffe2-0000-1000-8000-00805f9b34fb"  # notifications
CHARACTERISTIC_WRITE_UUID  = "0000ffe3-0000-1000-8000-00805f9b34fb"  # write

# -----------------------------
# App constants
# -----------------------------
DEVICE_FILE = "last_connected_device.json"
ACTIONS_FILE = "actions.json"  # expected in current working directory

END_DATA_OPTIONS: Dict[str, bytes] = {
    'NL': b'\n',
    'CR': b'\r',
    'BOTH': b'\r\n',
    'NONE': b''
}

DEFAULT_FREQUENCY_HZ = 10.0
DEFAULT_HEADER = [0xFF, 0x55]

# -----------------------------
# Helpers
# -----------------------------
PayloadType = Union[str, int, List[int]]

def to_bytes(payload: PayloadType) -> bytes:
    if isinstance(payload, str):
        return payload.encode('utf-8')
    if isinstance(payload, int):
        return bytes([payload & 0xFF])
    if isinstance(payload, list):
        return bytes([int(x) & 0xFF for x in payload])
    raise TypeError(f"Unsupported payload type: {type(payload)}")

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
# BLE Controller (async BLE in thread)
# -----------------------------
class BleController:
    def __init__(self, log: TextLog):
        self.log = log
        self.client: Optional[BleakClient] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.loop_running = False
        self.loop_thread: Optional[threading.Thread] = None

        self.discovered: List[Tuple[str, str]] = []  # list of (name, address)
        self.selected_index: int = 0

        # config
        self.config_directions: Dict[str, PayloadType] = {}
        self.config_stop: Optional[PayloadType] = None
        self.config_actions: List[Dict[str, Any]] = []
        self.config_header: List[int] = DEFAULT_HEADER.copy()

        # runtime options
        self.use_header: bool = False
        self.line_ending_key: str = 'BOTH'

        # WASD streaming state
        self._pressed: set[str] = set()
        self._current_dir: Optional[str] = None
        self._dir_payload: Optional[bytes] = None
        self._dir_period_s: float = 1.0 / DEFAULT_FREQUENCY_HZ
        self._dir_thread_stop = threading.Event()
        self._dir_thread = threading.Thread(target=self._direction_sender_loop, daemon=True)

        # start event loop thread
        self._start_loop_thread()
        self._dir_thread.start()

    # --------------- asyncio loop ---------------
    def _start_loop_thread(self) -> None:
        def run():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop_running = True
            try:
                self.loop.run_forever()
            finally:
                self.loop_running = False
        self.loop_thread = threading.Thread(target=run, daemon=True)
        self.loop_thread.start()
        time.sleep(0.05)

    def run_coro(self, coro):
        if self.loop and self.loop_running:
            return asyncio.run_coroutine_threadsafe(coro, self.loop)
        return None

    # --------------- config ---------------
    def load_actions_config(self) -> None:
        path = os.path.join(os.getcwd(), ACTIONS_FILE)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except FileNotFoundError:
            cfg = {
                "header": [255, 85],
                "directions": {"w":"F","a":"L","s":"B","d":"R","e":"K","stop":"S"},
                "actions": [
                    {"key":"l", "data":"LIGHT_TOGGLE", "label":"Toggle Light"}
                ]
            }
            with open(path, 'w', encoding='utf-8') as wf:
                json.dump(cfg, wf, indent=2)

        # validate and copy
        dirs = cfg.get("directions", {})
        stop = dirs.get("stop")
        if not all(k in dirs for k in ("w","a","s","d","e")) or stop is None:
            raise ValueError("'directions' must define w,a,s,d,e and stop")
        self.config_directions = {k: dirs[k] for k in ("w","a","s","d","e")}
        self.config_stop = stop

        header_cfg = cfg.get("header", DEFAULT_HEADER)
        if isinstance(header_cfg, list) and all(isinstance(x, int) for x in header_cfg):
            self.config_header = header_cfg
        else:
            self.config_header = DEFAULT_HEADER.copy()

        self.config_actions = []
        for item in cfg.get("actions", []):
            key = str(item.get("key", "")).lower()
            if not key:
                continue
            self.config_actions.append({
                "key": key,
                "data": item.get("data"),
                "label": item.get("label", key.upper())
            })
        hdr_hex = ' '.join(f'0x{b:02X}' for b in self.config_header)
        self.log.add(f"Loaded actions.json. Header: [{hdr_hex}]\n")

    # --------------- device persistence ---------------
    def save_last_device(self, device_name: str) -> None:
        try:
            with open(DEVICE_FILE, 'w', encoding='utf-8') as f:
                json.dump({"device_name": device_name}, f)
        except Exception:
            pass

    def load_last_device(self) -> Optional[str]:
        try:
            if not os.path.exists(DEVICE_FILE):
                return None
            with open(DEVICE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get("device_name")
        except Exception:
            return None

    # --------------- BLE ops ---------------
    def start_scan(self, timeout: float = 8.0) -> None:
        self.run_coro(self._scan_devices(timeout))

    async def _scan_devices(self, timeout: float) -> None:
        try:
            self.log.add(f"Scanning for devices for {timeout:.0f}s...\n")
            devices = await BleakScanner.discover(timeout=timeout)
            discovered: List[Tuple[str, str]] = []
            for d in devices:
                if d.name:
                    discovered.append((d.name, d.address))
            discovered.sort(key=lambda t: t[0].lower())
            self.discovered = discovered
            self.selected_index = 0 if self.discovered else -1
            self.log.add(f"Found {len(self.discovered)} device(s).\n")
        except Exception as e:
            self.log.add(f"Scan error: {e}\n")

    def connect_selected(self) -> None:
        if 0 <= self.selected_index < len(self.discovered):
            name, addr = self.discovered[self.selected_index]
            self.run_coro(self._async_connect(name, addr))

    async def _async_connect(self, device_name: str, address: Optional[str]) -> None:
        try:
            if self.client and self.client.is_connected:
                await self.client.disconnect()
            self.client = BleakClient(address)
            await self.client.connect()
            if self.client.is_connected:
                self.log.add(f"Connected to {device_name} ({address}).\n")
                self.save_last_device(device_name)
                await self._start_notifications()
            else:
                self.log.add("Connection failed.\n")
        except Exception as e:
            self.log.add(f"Connect error: {e}\n")

    async def _start_notifications(self) -> None:
        async def handler(sender, data: bytes):
            try:
                decoded = data.decode('utf-8', errors='ignore')
            except Exception:
                decoded = str(data)
            self.log.add(f"Received: {decoded}\n")
        try:
            if self.client:
                await self.client.start_notify(CHARACTERISTIC_NOTIFY_UUID, handler)
                self.log.add("Started notifications.\n")
        except Exception as e:
            self.log.add(f"Notify error: {e}\n")

    def disconnect(self) -> None:
        self.run_coro(self._async_disconnect())

    async def _async_disconnect(self) -> None:
        try:
            if self.client and self.client.is_connected:
                await self.client.disconnect()
                self.log.add("Disconnected.\n")
        except Exception as e:
            self.log.add(f"Disconnect error: {e}\n")

    def send(self, payload: bytes, use_header: Optional[bool] = None) -> None:
        self.run_coro(self._async_write(payload, use_header))

    async def _async_write(self, payload: bytes, use_header: Optional[bool] = None) -> None:
        try:
            if not self.client:
                return
            add_header = self.use_header if use_header is None else use_header
            final_payload = payload
            if add_header and self.config_header:
                final_payload = bytes(self.config_header) + payload
            await self.client.write_gatt_char(CHARACTERISTIC_WRITE_UUID, final_payload)
        except Exception as e:
            self.log.add(f"Send error: {e}\n")

    # --------------- WASD streaming ---------------
    def set_frequency(self, hz: float) -> None:
        hz = max(1.0, float(hz))
        self._dir_period_s = 1.0 / hz

    def handle_keydown(self, key: str) -> None:
        key = key.lower()
        if key in self._pressed:
            return
        # Direction keys
        if key in ('w','a','s','d','e'):
            self._pressed.add(key)
            self._start_direction_stream(key)
            return
        # one-shot actions
        for act in self.config_actions:
            if act.get("key") == key:
                self._pressed.add(key)
                self._trigger_action(act)
                return

    def handle_keyup(self, key: str) -> None:
        key = key.lower()
        if key in self._pressed:
            self._pressed.discard(key)
            if key == self._current_dir:
                self._send_dir_stop()
                self._current_dir = None
                self._dir_payload = None

    def _start_direction_stream(self, key: str) -> None:
        if not (self.client and self.client.is_connected):
            return
        # payload
        raw = self.config_directions.get(key)
        if raw is None:
            self.log.add(f"No payload for '{key}'.\n")
            return
        try:
            payload = to_bytes(raw)
        except Exception as e:
            self.log.add(f"Invalid payload for '{key}': {e}\n")
            return
        end = END_DATA_OPTIONS.get(self.line_ending_key, b'')
        payload_with_end = payload + end
        self._current_dir = key
        self._dir_payload = payload_with_end
        # send first immediately
        self.send(payload_with_end)

    def _send_dir_stop(self) -> None:
        if not (self.client and self.client.is_connected):
            return
        if self.config_stop is None:
            return
        try:
            payload = to_bytes(self.config_stop)
            end = END_DATA_OPTIONS.get(self.line_ending_key, b'')
            payload_with_end = payload + end
            self.send(payload_with_end)
            self.log.add(f"Sent stop.\n")
        except Exception as e:
            self.log.add(f"Invalid stop payload: {e}\n")

    def _direction_sender_loop(self) -> None:
        last_sent = 0.0
        while not self._dir_thread_stop.is_set():
            now = time.time()
            if (self._current_dir and self._dir_payload and self.client and
                self.client.is_connected and self._dir_period_s > 0):
                if now - last_sent >= self._dir_period_s:
                    fut = self.run_coro(self._async_write(self._dir_payload))
                    if fut:
                        last_sent = now
            time.sleep(0.005)

    # --------------- cleanup ---------------
    def shutdown(self) -> None:
        try:
            self._dir_thread_stop.set()
            if self.client and self.client.is_connected:
                fut = self.run_coro(self.client.disconnect())
                if fut:
                    fut.result(timeout=2.0)
        except Exception:
            pass
        if self.loop and self.loop_running:
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.loop_thread and self.loop_thread.is_alive():
            self.loop_thread.join(timeout=1.0)

    # --------------- actions ---------------
    def _trigger_action(self, act: Dict[str, Any]) -> None:
        if not (self.client and self.client.is_connected):
            self.log.add("Not connected.\n")
            return
        data = act.get("data")
        try:
            payload = to_bytes(data)
            end = END_DATA_OPTIONS.get(self.line_ending_key, b'')
            payload_with_end = payload + end
        except Exception as e:
            self.log.add(f"Invalid action payload: {e}\n")
            return
        self.send(payload_with_end)
        shown = act.get("label") or act.get("key", "?").upper()
        self.log.add(f"Action sent: {shown}\n")

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

        self.log = TextLog(self.font)
        self.ble = BleController(self.log)
        self.ble.load_actions_config()

        self.frequency = DEFAULT_FREQUENCY_HZ
        self.ble.set_frequency(self.frequency)

        # UI state
        self.running = True
        self.mode = 'idle'  # 'idle' | 'scanning' | 'connected' | 'select'
        
        # Text input state
        self.text_input_mode = False
        self.text_input_buffer = ""

        # initial scan to speed things up
        self.mode = 'scanning'
        self.ble.start_scan(6.0)

    # ----------- rendering -----------
    def draw_header(self) -> None:
        y = 10
        def line(text: str, color=self.FG):
            img = self.font.render(text, True, color)
            self.screen.blit(img, (16, y))
            return y + img.get_height() + 6
        y = line("BLE Robot Controller (Pygame)", self.ACCENT)
        status = "CONNECTED" if (self.ble.client and self.ble.client.is_connected) else "DISCONNECTED"
        y = line(f"Status: {status}")
        hdr = 'ON' if self.ble.use_header else 'OFF'
        y = line(f"Header: {hdr}  |  Line Ending: {self.ble.line_ending_key}  |  Frequency: {self.frequency:.1f} Hz")
        y = line("Controls: ")
        y = line("  C=Scan  ENTER=Connect  UP/DOWN=Select  H=Toggle Header  F/F1=Line Ending  +/-=Freq  T=Type  ESC=Quit/Disconnect")
        y = line("W/A/S/D/E to drive; Action keys from actions.json also work here.")

        # device list
        y += 5
        action_y = y
        if self.ble.discovered:
            img = self.font.render("Devices:", True, self.FG)
            self.screen.blit(img, (16, y))
            y += img.get_height() + 6
            for i, (nm, addr) in enumerate(self.ble.discovered[:12]):
                sel = (i == self.ble.selected_index)
                color = self.ACCENT if sel else self.FG
                text = f"{'> ' if sel else '  '} {nm} ({addr})"
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
        if self.ble.config_actions:
            for act in self.ble.config_actions[:15]:
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
        if self.text_input_mode:
            input_y = self.HEIGHT - 60
            pygame.draw.rect(self.screen, (50,120,200), pygame.Rect(0, input_y, self.WIDTH, 60))
            prompt_text = f"Type message (ESC to cancel, ENTER to send): {self.text_input_buffer}_"
            img = self.font.render(prompt_text, True, (255,255,255))
            self.screen.blit(img, (16, input_y + 20))

    # ----------- event handling -----------
    def handle_event(self, ev: pygame.event.Event) -> None:
        if ev.type == pygame.QUIT:
            self.running = False
        elif ev.type == pygame.KEYDOWN:
            # Handle text input mode separately
            if self.text_input_mode:
                self._handle_text_input(ev)
                return
            
            if ev.key == pygame.K_ESCAPE:
                # disconnect or quit
                if self.ble.client and self.ble.client.is_connected:
                    self.ble.disconnect()
                else:
                    self.running = False
            elif ev.key == pygame.K_c:
                self.mode = 'scanning'
                self.ble.start_scan(6.0)
            elif ev.key == pygame.K_t:
                # Toggle text input mode
                self.text_input_mode = True
                self.text_input_buffer = ""
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.ble.connect_selected()
            elif ev.key == pygame.K_UP:
                if self.ble.discovered:
                    self.ble.selected_index = max(0, self.ble.selected_index - 1)
            elif ev.key == pygame.K_DOWN:
                if self.ble.discovered:
                    self.ble.selected_index = min(len(self.ble.discovered)-1, self.ble.selected_index + 1)
            elif ev.key == pygame.K_h:
                self.ble.use_header = not self.ble.use_header
            elif ev.key in (pygame.K_f, pygame.K_F1):
                # cycle line endings
                order = ['NL','CR','BOTH','NONE']
                i = order.index(self.ble.line_ending_key) if self.ble.line_ending_key in order else 2
                self.ble.line_ending_key = order[(i+1) % len(order)]
            elif ev.key in (pygame.K_PLUS, pygame.K_EQUALS):
                self.frequency = min(60.0, self.frequency + 1)
                self.ble.set_frequency(self.frequency)
            elif ev.key in (pygame.K_MINUS, pygame.K_UNDERSCORE):
                self.frequency = max(1.0, self.frequency - 1)
                self.ble.set_frequency(self.frequency)
            else:
                # map letter keys to chars if possible
                ch = self._pygame_key_to_char(ev.key)
                if ch:
                    self.ble.handle_keydown(ch)
        elif ev.type == pygame.KEYUP:
            ch = self._pygame_key_to_char(ev.key)
            if ch:
                self.ble.handle_keyup(ch)

    def _handle_text_input(self, ev: pygame.event.Event) -> None:
        """Handle keyboard input when in text input mode."""
        if ev.key == pygame.K_ESCAPE:
            # Cancel text input
            self.text_input_mode = False
            self.text_input_buffer = ""
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            # Send the message
            if self.text_input_buffer.strip():
                self._send_manual_text(self.text_input_buffer)
            self.text_input_mode = False
            self.text_input_buffer = ""
        elif ev.key == pygame.K_BACKSPACE:
            self.text_input_buffer = self.text_input_buffer[:-1]
        elif ev.key == pygame.K_SPACE:
            self.text_input_buffer += " "
        else:
            # Try to get the character from the key
            ch = self._pygame_key_to_printable(ev)
            if ch:
                self.text_input_buffer += ch

    def _send_manual_text(self, text: str) -> None:
        """Send manually typed text to the BLE device."""
        if not (self.ble.client and self.ble.client.is_connected):
            self.log.add("Not connected.\n")
            return
        try:
            payload = text.encode('utf-8')
            end = END_DATA_OPTIONS.get(self.ble.line_ending_key, b'')
            payload_with_end = payload + end
            self.ble.send(payload_with_end)
            hdr_info = " (with header)" if self.ble.use_header else ""
            self.log.add(f"Sent: {text}{hdr_info}\n")
        except Exception as e:
            self.log.add(f"Send error: {e}\n")

    @staticmethod
    def _pygame_key_to_char(key: int) -> Optional[str]:
        # Letters and digits mapping
        if pygame.K_a <= key <= pygame.K_z:
            return chr(key)
        if pygame.K_0 <= key <= pygame.K_9:
            return chr(key)
        return None

    @staticmethod
    def _pygame_key_to_printable(ev: pygame.event.Event) -> Optional[str]:
        """Convert pygame key event to printable character, handling shift."""
        # Use unicode if available (respects shift, caps lock, etc.)
        if ev.unicode and ev.unicode.isprintable():
            return ev.unicode
        # Fallback for special keys
        if ev.key == pygame.K_SPACE:
            return " "
        return None

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
            self.ble.shutdown()
            pygame.quit()


if __name__ == "__main__":
    App().run()
