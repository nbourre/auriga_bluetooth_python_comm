"""Pygame building blocks shared by the pygame applications.

  - DeviceSelector: list of scanned devices with a selection cursor
  - TextInputBox:   one-line text input with Up / Down message history
  - key_to_char / key_to_printable: pygame key helpers
"""
from typing import Callable, List, Optional

import pygame

from ble_connection import BleConnection, DiscoveredDevice
from message_history import MessageHistory


class DeviceSelector:
    """Devices found by the last scan and the currently selected one."""

    def __init__(self, conn: BleConnection) -> None:
        self.conn = conn
        self.devices: List[DiscoveredDevice] = []
        self.selected_index = -1
        conn.devices_found.connect(self._on_devices_found)

    def _on_devices_found(self, devices: List[DiscoveredDevice]) -> None:
        self.devices = list(devices)
        self.selected_index = 0 if self.devices else -1

    def move(self, step: int) -> None:
        if self.devices:
            self.selected_index = max(0, min(len(self.devices) - 1, self.selected_index + step))

    def connect_selected(self) -> None:
        if 0 <= self.selected_index < len(self.devices):
            device = self.devices[self.selected_index]
            self.conn.connect(device.name, device.address)


class TextInputBox:
    """One-line text input driven by pygame KEYDOWN events.

    ENTER submits, ESC cancels, UP / DOWN browse the history of sent messages.
    `on_submit(text)` must return True if the message was really sent: only then
    is it added to the history.
    """

    PROMPT = "Type message (ESC to cancel, ENTER to send, UP/DOWN for history): "

    def __init__(self, on_submit: Callable[[str], bool], history: Optional[MessageHistory] = None) -> None:
        self.on_submit = on_submit
        self.history = history or MessageHistory()
        self.active = False
        self.buffer = ""

    def open(self) -> None:
        self.active = True
        self.buffer = ""
        self.history.reset()

    def close(self) -> None:
        self.active = False
        self.buffer = ""

    def handle_key(self, ev: pygame.event.Event) -> None:
        if ev.key == pygame.K_ESCAPE:
            self.close()
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            text = self.buffer
            self.close()
            if text.strip() and self.on_submit(text):
                self.history.add(text)
        elif ev.key in (pygame.K_UP, pygame.K_DOWN):
            text = self.history.browse(-1 if ev.key == pygame.K_UP else +1, self.buffer)
            if text is not None:
                self.buffer = text
        elif ev.key == pygame.K_BACKSPACE:
            self.buffer = self.buffer[:-1]
        else:
            ch = key_to_printable(ev)
            if ch:
                self.buffer += ch

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, rect: pygame.Rect, margin: int = 16) -> None:
        """Draw the input bar inside `rect` (only when active)."""
        if not self.active:
            return
        pygame.draw.rect(surface, (50, 120, 200), rect)
        img = font.render(f"{self.PROMPT}{self.buffer}_", True, (255, 255, 255))
        surface.blit(img, (rect.x + margin, rect.y + 20))


def key_to_char(key: int) -> Optional[str]:
    """Letter / digit for a pygame key code, else None."""
    if pygame.K_a <= key <= pygame.K_z or pygame.K_0 <= key <= pygame.K_9:
        return chr(key)
    return None


def key_to_printable(ev: pygame.event.Event) -> Optional[str]:
    """Printable character of a key event (respects shift, caps lock, ...)."""
    if ev.unicode and ev.unicode.isprintable():
        return ev.unicode
    if ev.key == pygame.K_SPACE:
        return " "
    return None
