"""Toolkit-independent robot driving: W/A/S/D/E streaming and one-shot action keys.

The UI (Tk, pygame, ...) only has to call `key_down` / `key_up` with a lowercase
key name. Direction keys use a LIFO stack: the most recently pressed key wins, and
releasing it falls back to the previous one (or STOP when the stack is empty).
"""
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from actions_config import DIRECTION_KEYS, ActionsConfig
from ble_connection import BleConnection, to_bytes

DEFAULT_FREQUENCY_HZ = 10


class DriveController:
    def __init__(self, conn: BleConnection, config: ActionsConfig,
                 end_data: Callable[[], bytes], frequency_hz: float = DEFAULT_FREQUENCY_HZ) -> None:
        self.conn = conn
        self.config = config
        self.end_data = end_data  # called at each send so the UI can change the line ending live

        self._pressed_actions: set = set()   # one-shot actions currently held (avoid key repeat)
        self._key_stack: List[str] = []      # LIFO stack of held direction keys
        self._dir_payload: Optional[bytes] = None
        self._dir_period_s = 1.0 / max(1.0, float(frequency_hz))

        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._direction_sender_loop, daemon=True)
        self._thread.start()

    def set_frequency(self, hz: float) -> None:
        self._dir_period_s = 1.0 / max(1.0, float(hz))

    def shutdown(self) -> None:
        self._stop_event.set()

    # -----------------------------
    # Key events
    # -----------------------------
    def key_down(self, key: str) -> bool:
        """Handle a key press. Returns True if the key is used by the controller."""
        key = key.lower()
        if key in DIRECTION_KEYS:
            if key not in self._key_stack:
                self._key_stack.append(key)
                self._update_stream()
            return True
        for act in self.config.actions:
            if act.get("key") == key:
                if key not in self._pressed_actions:
                    self._pressed_actions.add(key)
                    self.trigger_action(act)
                return True
        return False

    def key_up(self, key: str) -> bool:
        """Handle a key release. Returns True if the key is used by the controller."""
        key = key.lower()
        was_action = key in self._pressed_actions
        self._pressed_actions.discard(key)
        if key in DIRECTION_KEYS:
            if key in self._key_stack:
                self._key_stack = [k for k in self._key_stack if k != key]
                self._update_stream()
            return True
        return was_action

    # -----------------------------
    # Sending
    # -----------------------------
    def trigger_action(self, act: Dict[str, Any]) -> None:
        if not self.conn.is_connected:
            self.conn.log.emit("Not connected to any device.\n")
            return
        try:
            payload = to_bytes(act.get("data")) + self.end_data()
        except Exception as e:
            self.conn.log.emit(f"Invalid action payload: {e}\n")
            return
        self.conn.write(payload)
        shown = act.get("label") or act.get("key", "?").upper()
        self.conn.log.emit(f"Action sent: {shown}\n")

    def _update_stream(self) -> None:
        # empty stack -> STOP, otherwise stream the command of the key on top of the stack
        if not self._key_stack:
            self._dir_payload = None
            self._send_stop()
            return
        raw = self.config.directions.get(self._key_stack[-1])
        if raw is None:
            return
        try:
            self._dir_payload = to_bytes(raw) + self.end_data()
            if self.conn.is_connected:
                self.conn.write(self._dir_payload)
        except Exception as e:
            self.conn.log.emit(f"Payload error: {e}\n")

    def _send_stop(self) -> None:
        if not self.conn.is_connected or self.config.stop is None:
            return
        try:
            payload = to_bytes(self.config.stop) + self.end_data()
        except Exception as e:
            self.conn.log.emit(f"Invalid stop payload: {e}\n")
            return
        self.conn.write(payload)
        self.conn.log.emit(f"Sent: {self.config.stop}\n")

    def _direction_sender_loop(self) -> None:
        """Repeat the current direction payload at the configured frequency."""
        last_sent = 0.0
        while not self._stop_event.is_set():
            now = time.time()
            payload = self._dir_payload
            if payload and self.conn.is_connected and now - last_sent >= self._dir_period_s:
                if self.conn.write(payload):
                    last_sent = now
            time.sleep(0.005)
