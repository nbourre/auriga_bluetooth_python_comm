"""Robot configuration read from actions.json (toolkit-independent)."""
import json
import os
from typing import Any, Dict, List

ACTIONS_FILE = "actions.json"  # in the current working directory
DEFAULT_HEADER = [0xFF, 0x55]  # default header
DIRECTION_KEYS = ('w', 'a', 's', 'd', 'e')


class ActionsConfig:
    """Contents of actions.json: header, direction payloads and one-shot actions."""

    def __init__(self, filename: str = ACTIONS_FILE) -> None:
        self.filename = filename
        self.directions: Dict[str, Any] = {}
        self.stop: Any = None
        self.actions: List[Dict[str, Any]] = []
        self.header: List[int] = DEFAULT_HEADER.copy()

    def load(self) -> None:
        """Load the file (creating it with default values if it does not exist).

        Raises ValueError if the content is invalid.
        """
        path = os.path.join(os.getcwd(), self.filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except FileNotFoundError:
            cfg = {
                "header": [255, 85],
                "directions": {"w": "F", "a": "L", "s": "B", "d": "R", "e": "K", "stop": "S"},
                "actions": [
                    {"key": "l", "data": "LIGHT_TOGGLE", "label": "Toggle Light"},
                    {"key": "z", "data": [255, 85], "label": "Special Command"}
                ]
            }
            with open(path, 'w', encoding='utf-8') as wf:
                json.dump(cfg, wf, indent=2)

        dirs = cfg.get("directions", {})
        stop = dirs.get("stop")
        if not all(k in dirs for k in DIRECTION_KEYS) or stop is None:
            raise ValueError("'directions' must define w,a,s,d,e (klaxon) and stop")
        self.directions = {k: dirs[k] for k in DIRECTION_KEYS}
        self.stop = stop

        header = cfg.get("header", DEFAULT_HEADER)
        if isinstance(header, list) and all(isinstance(x, int) for x in header):
            self.header = header
        else:
            self.header = DEFAULT_HEADER.copy()

        self.actions = []
        for item in cfg.get("actions", []):
            key = str(item.get("key", "")).lower()
            if key:
                self.actions.append({"key": key, "data": item.get("data"),
                                     "label": item.get("label", key.upper())})

    @property
    def header_hex(self) -> str:
        return ' '.join(f'0x{b:02X}' for b in self.header)

    def with_header(self, payload: bytes) -> bytes:
        """Prepend the configured header to a payload."""
        return bytes(self.header) + payload if self.header else payload
