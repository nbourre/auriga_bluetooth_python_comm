"""History of sent messages, browsable with Up / Down and saved between sessions.

Toolkit-independent: used by the Tk `MessageSender` and the pygame `TextInputBox`.
"""
import json
import os
import sys
from typing import List, Optional

APP_DIR_NAME = "auriga_ble"
HISTORY_FILE_NAME = "message_history.json"


def user_data_dir(app_name: str = APP_DIR_NAME) -> str:
    """Per-user directory for application data, following each platform's convention.

    Windows: %LOCALAPPDATA%\\<app>   macOS: ~/Library/Application Support/<app>
    Linux/other: $XDG_STATE_HOME/<app> (default ~/.local/state/<app>)
    """
    home = os.path.expanduser("~")
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or home
    elif sys.platform == "darwin":
        base = os.path.join(home, "Library", "Application Support")
    else:
        base = os.environ.get("XDG_STATE_HOME") or os.path.join(home, ".local", "state")
    return os.path.join(base, app_name)


def default_history_path() -> str:
    return os.path.join(user_data_dir(), HISTORY_FILE_NAME)


class MessageHistory:
    """Sent messages (most recent last) with an Up / Down browsing cursor.

    `path` is the JSON file used to persist the history; pass None to keep it in memory only.
    """

    def __init__(self, path: Optional[str] = None, max_items: int = 100) -> None:
        self.path = path
        self.max_items = max_items
        self._items: List[str] = self._load()[-max_items:] if path else []
        self._index = len(self._items)  # == len(items) when not browsing
        self._draft = ""                # text being typed before browsing started

    @classmethod
    def per_user(cls, max_items: int = 100) -> "MessageHistory":
        """History persisted in the per-user data directory."""
        return cls(default_history_path(), max_items)

    @property
    def items(self) -> List[str]:
        return list(self._items)

    def add(self, message: str) -> None:
        if not self._items or self._items[-1] != message:  # skip consecutive duplicates
            self._items.append(message)
            del self._items[:-self.max_items]
            self._save()
        self.reset()

    def reset(self) -> None:
        """Stop browsing (call when a new input session starts or after sending)."""
        self._index = len(self._items)
        self._draft = ""

    def browse(self, step: int, current_text: str) -> Optional[str]:
        """Move through the history (-1 = older, +1 = newer).

        Returns the text to show in the input, or None if nothing should change.
        Going past the newest entry gives back what was being typed before browsing.
        """
        if not self._items:
            return None
        if self._index == len(self._items):
            self._draft = current_text
        new_index = self._index + step
        if new_index < 0 or new_index > len(self._items):
            return None
        self._index = new_index
        return self._draft if new_index == len(self._items) else self._items[new_index]

    # -----------------------------
    # Persistence
    # -----------------------------
    def _load(self) -> List[str]:
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [m for m in data if isinstance(m, str)] if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _save(self) -> None:
        if not self.path:
            return
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self._items, f, ensure_ascii=False)
        except OSError:
            pass  # history is a convenience: never break the app because of it
