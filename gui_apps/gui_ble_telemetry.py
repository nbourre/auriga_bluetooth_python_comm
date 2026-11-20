import json
import math
from typing import Any, Dict, List, Optional

import pygame

from actions_config import ActionsConfig
from ble_connection import END_DATA_OPTIONS, BleConnection, LineAssembler
from drive_controller import DEFAULT_FREQUENCY_HZ, DriveController
from message_history import MessageHistory
from pygame_parts import DeviceSelector, TextInputBox, key_to_char

LINE_ENDING_ORDER = ['NL', 'CR', 'BOTH', 'NONE']

TOTAL_CHECKPOINTS = 6

# UI Layout constants
UI_MARGIN_LEFT = 16
UI_MARGIN_TOP = 10
UI_SPACING_SMALL = 2
UI_SPACING_MEDIUM = 6
UI_SPACING_LARGE = 15
UI_SPACING_HBOX = 20
UI_TITLE_FONT_SIZE = 32
UI_FONT_SIZE = 22
UI_FONT_SMALL_SIZE = 18
UI_SECTION_SPACING = 15
UI_DEVICE_MAX = 10
UI_ACTION_MAX = 10
UI_LOG_HEIGHT = 150
UI_LOG_BOTTOM_OFFSET = 70
UI_LOG_INPUT_HEIGHT = 60
UI_COL_1_MIN_WIDTH = 500  # Whole telemetry column minimum width
UI_COLUMN_2_OFFSET = 350  # For telemetry right column
UI_DEVICES_PANEL_OFFSET = 600  # For devices panel offset from left
UI_ACTIONS_PANEL_OFFSET = 600  # For actions panel offset from left

UI_DEVICE_MIN_HEIGHT = UI_DEVICE_MAX * (UI_FONT_SMALL_SIZE)

# Checkpoint tracking
class TelemetryState:
    """Store telemetry data received from robot as JSON."""
    def __init__(self):
        self.ts: int = 0
        self.chrono: int = 0
        self.gz: float = 0.0
        self.etat: int = 0
        self.pwm_l: int = 0
        self.pwm_r: int = 0
        self.capt: List[int] = [0, 0, 0, 0, 0]
        self.completed_checkpoints: set[int] = set()  # checkpoint numbers 1-6
        self.last_checkpoint: int = 0  # Most recently completed checkpoint

    def update_from_json(self, data: Dict[str, Any]) -> None:
        """Update telemetry from JSON dict."""
        self.ts = data.get("ts", self.ts)
        self.chrono = data.get("chrono", self.chrono)
        self.gz = data.get("gz", self.gz)
        self.etat = data.get("etat", self.etat)
        pwm = data.get("pwm", {})
        self.pwm_l = pwm.get("l", self.pwm_l)
        self.pwm_r = pwm.get("r", self.pwm_r)
        self.capt = data.get("capt", self.capt)
        cp = data.get("cp")
        if cp is not None and 1 <= cp <= TOTAL_CHECKPOINTS:
            self.completed_checkpoints.add(cp)
            self.last_checkpoint = cp

# -----------------------------
# Pygame UI helpers
# -----------------------------
class MessageBox:
    """A control that displays text with a background rectangle."""
    def __init__(self, x: int, y: int, width: int, height: int, 
                 bg_color=(40, 44, 52), text_color=(230, 230, 230), 
                 font: Optional[pygame.font.Font] = None):
        self.rect = pygame.Rect(x, y, width, height)
        self.bg_color = bg_color
        self.text_color = text_color
        self.font = font or pygame.font.SysFont(None, 20)
        self.lines: List[str] = []
        self.max_lines = 20
        self.padding = 8
    
    def add(self, msg: str) -> None:
        """Add message to the log."""
        for line in msg.splitlines():
            self.lines.append(line)
        if len(self.lines) > self.max_lines:
            self.lines = self.lines[-self.max_lines:]
        print(msg, end="")  # also log to console
    
    def set_position(self, x: int, y: int) -> None:
        """Update position of the message box."""
        self.rect.x = x
        self.rect.y = y
    
    def set_size(self, width: int, height: int) -> None:
        """Update size of the message box."""
        self.rect.width = width
        self.rect.height = height
    
    def draw(self, surface: pygame.Surface) -> None:
        """Draw the background rectangle and text."""
        # Draw background
        pygame.draw.rect(surface, self.bg_color, self.rect)
        
        # Draw text
        x = self.rect.x + self.padding
        y = self.rect.y + self.padding
        for line in self.lines:
            img = self.font.render(line, True, self.text_color)
            surface.blit(img, (x, y))
            y += img.get_height() + 2
            # Stop if we exceed the box height
            if y > self.rect.y + self.rect.height - self.padding:
                break

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

# -------- Layout Containers (Base Container, HBox, VBox) --------
class Container:
    """Base class for layout containers."""
    def __init__(self, x: int = 0, y: int = 0, spacing: int = 10, 
                 min_width: Optional[int] = None, max_width: Optional[int] = None,
                 min_height: Optional[int] = None, max_height: Optional[int] = None):
        self.x = x
        self.y = y
        self.spacing = spacing
        self.children: List[Tuple[Any, int, int]] = []  # (element, width, height)
        self._cached_width = 0
        self._cached_height = 0
        self.min_width = min_width
        self.max_width = max_width
        self.min_height = min_height
        self.max_height = max_height
    
    def add(self, element: Any, width: Optional[int] = None, height: Optional[int] = None) -> None:
        """Add an element to the container."""
        w = width or 0
        h = height or 0
        self.children.append((element, w, h))
        self._recalculate()
    
    def _recalculate(self) -> None:
        """Calculate dimensions. Override in subclasses."""
        pass
    
    def _apply_constraints(self) -> None:
        """Apply min/max width and height constraints."""
        if self.min_width is not None:
            self._cached_width = max(self._cached_width, self.min_width)
        if self.max_width is not None:
            self._cached_width = min(self._cached_width, self.max_width)
        if self.min_height is not None:
            self._cached_height = max(self._cached_height, self.min_height)
        if self.max_height is not None:
            self._cached_height = min(self._cached_height, self.max_height)
    
    def get_width(self) -> int:
        return self._cached_width
    
    def get_height(self) -> int:
        return self._cached_height
    
    def draw(self, surface: pygame.Surface, font: Optional[pygame.font.Font] = None, color=(230, 230, 230)) -> None:
        """Draw the container. Override in subclasses."""
        pass

class HBox(Container):
    """Horizontal layout container for Pygame elements."""
    def __init__(self, x: int = 0, y: int = 0, spacing: int = 10,
                 min_width: Optional[int] = None, max_width: Optional[int] = None,
                 min_height: Optional[int] = None, max_height: Optional[int] = None):
        super().__init__(x, y, spacing, min_width=min_width, max_width=max_width,
                        min_height=min_height, max_height=max_height)
    
    def _recalculate(self) -> None:
        """Calculate total width and height of all children."""
        total_w = 0
        max_h = 0
        for elem, w, h in self.children:
            if w == 0 or h == 0:
                # Ensure child containers recalculate themselves first
                if hasattr(elem, '_recalculate'):
                    elem._recalculate()
                # Try to get size from element (if it has get_width/get_height)
                if hasattr(elem, 'get_width') and hasattr(elem, 'get_height'):
                    w = elem.get_width()
                    h = elem.get_height()
                elif isinstance(elem, str):
                    w, h = 50, 20  # rough estimate for strings
            total_w += w + self.spacing
            max_h = max(max_h, h)
        self._cached_width = max(0, total_w - self.spacing)
        self._cached_height = max_h
        self._apply_constraints()
    
    def draw(self, surface: pygame.Surface, font: Optional[pygame.font.Font] = None, color=(230, 230, 230)) -> None:
        """Draw all children horizontally, distributing space equally if needed."""
        # Calculate available width for children with unspecified widths
        unspecified_indices = [i for i, (elem, w, h) in enumerate(self.children) if w == 0]
        specified_width = sum(w for elem, w, h in self.children if w > 0)
        spacing_total = self.spacing * (len(self.children) - 1) if len(self.children) > 0 else 0
        
        if unspecified_indices:
            # Calculate equal width for unspecified children
            # Estimate available width (use container width if set via constraints)
            available_width = self.get_width() if self.get_width() > 0 else 500  # fallback
            remaining_width = available_width - specified_width - spacing_total
            equal_width = max(50, remaining_width // len(unspecified_indices)) if unspecified_indices else 0
        else:
            equal_width = 0
        
        curr_x = self.x
        for i, (elem, w, h) in enumerate(self.children):
            # Use equal_width if w == 0
            use_w = equal_width if w == 0 else w
            
            if isinstance(elem, str):
                # Render string
                if font:
                    img = font.render(elem, True, color)
                    surface.blit(img, (curr_x, self.y))
                    curr_x += img.get_width() + self.spacing
            elif isinstance(elem, (HBox, VBox)):
                # Nested layout container - update position and draw
                elem.x = curr_x
                elem.y = self.y
                # Apply width if unspecified
                if w == 0 and use_w > 0:
                    elem.min_width = use_w
                    elem.max_width = use_w
                    elem._recalculate()
                elem.draw(surface, font=font, color=color)
                curr_x += elem.get_width() + self.spacing
            elif hasattr(elem, 'draw'):
                # Element has a draw method
                # Set position if available
                if hasattr(elem, 'set_position'):
                    elem.set_position(curr_x, self.y)
                else:
                    if hasattr(elem, 'x'):
                        elem.x = curr_x
                    if hasattr(elem, 'y'):
                        elem.y = self.y
                elem.draw(surface)
                curr_x += use_w + self.spacing
            elif isinstance(elem, pygame.Surface):
                # Direct surface
                surface.blit(elem, (curr_x, self.y))
                curr_x += use_w + self.spacing

class VBox(Container):
    """Vertical layout container for Pygame elements."""
    def __init__(self, x: int = 0, y: int = 0, spacing: int = 6,
                 min_width: Optional[int] = None, max_width: Optional[int] = None,
                 min_height: Optional[int] = None, max_height: Optional[int] = None):
        super().__init__(x, y, spacing, min_width=min_width, max_width=max_width,
                        min_height=min_height, max_height=max_height)
    
    def _recalculate(self) -> None:
        """Calculate total width and height of all children."""
        max_w = 0
        total_h = 0
        for elem, w, h in self.children:
            if w == 0 or h == 0:
                # Ensure child containers recalculate themselves first
                if hasattr(elem, '_recalculate'):
                    elem._recalculate()
                # Try to get size from element
                if hasattr(elem, 'get_width') and hasattr(elem, 'get_height'):
                    w = elem.get_width()
                    h = elem.get_height()
                elif isinstance(elem, str):
                    w, h = 100, 20  # rough estimate
            max_w = max(max_w, w)
            total_h += h + self.spacing
        self._cached_width = max_w
        self._cached_height = max(0, total_h - self.spacing)
        self._apply_constraints()
    
    def draw(self, surface: pygame.Surface, font: Optional[pygame.font.Font] = None, color=(230, 230, 230)) -> None:
        """Draw all children vertically, distributing space equally if needed."""
        # Calculate available height for children with unspecified heights
        unspecified_indices = [i for i, (elem, w, h) in enumerate(self.children) if h == 0]
        specified_height = sum(h for elem, w, h in self.children if h > 0)
        spacing_total = self.spacing * (len(self.children) - 1) if len(self.children) > 0 else 0
        
        if unspecified_indices:
            # Calculate equal height for unspecified children
            # Estimate available height (use container height if set via constraints)
            available_height = self.get_height() if self.get_height() > 0 else 400  # fallback
            remaining_height = available_height - specified_height - spacing_total
            equal_height = max(50, remaining_height // len(unspecified_indices)) if unspecified_indices else 0
        else:
            equal_height = 0
        
        curr_y = self.y
        for i, (elem, w, h) in enumerate(self.children):
            # Use equal_height if h == 0
            use_h = equal_height if h == 0 else h
            
            if isinstance(elem, str):
                # Render string
                if font:
                    img = font.render(elem, True, color)
                    surface.blit(img, (self.x, curr_y))
                    curr_y += img.get_height() + self.spacing
            elif isinstance(elem, (HBox, VBox)):
                # Nested layout container - update position and draw
                elem.x = self.x
                elem.y = curr_y
                # Apply height if unspecified
                if h == 0 and use_h > 0:
                    elem.min_height = use_h
                    elem.max_height = use_h
                    elem._recalculate()
                elem.draw(surface, font=font, color=color)
                curr_y += elem.get_height() + self.spacing
            elif hasattr(elem, 'draw'):
                # Element has a draw method
                # Set position if available
                if hasattr(elem, 'set_position'):
                    elem.set_position(self.x, curr_y)
                else:
                    if hasattr(elem, 'x'):
                        elem.x = self.x
                    if hasattr(elem, 'y'):
                        elem.y = curr_y
                elem.draw(surface)
                curr_y += use_h + self.spacing
            elif isinstance(elem, pygame.Surface):
                surface.blit(elem, (self.x, curr_y))
                curr_y += use_h + self.spacing

class VBoxWithTitle(VBox):
    """VBox with a title header."""
    def __init__(self, title: str, x: int = 0, y: int = 0, spacing: int = 6, 
                 title_font: Optional[pygame.font.Font] = None, title_color=(235, 235, 235),
                 min_width: Optional[int] = None, max_width: Optional[int] = None,
                 min_height: Optional[int] = None, max_height: Optional[int] = None):
        super().__init__(x, y, spacing, min_width=min_width, max_width=max_width, 
                        min_height=min_height, max_height=max_height)
        self.title = title
        self.title_font = title_font
        self.title_color = title_color
        self._title_height = 0
    
    def _recalculate(self) -> None:
        """Calculate width and height including title."""
        # Call parent recalculate
        super()._recalculate()
        
        # Add title height to total height
        if self.title_font and self.title:
            title_img = self.title_font.render(self.title, True, self.title_color)
            self._title_height = title_img.get_height()
            self._cached_height += self._title_height + 6  # 6 pixels spacing after title
    
    def draw(self, surface: pygame.Surface, font: Optional[pygame.font.Font] = None, color=(230, 230, 230)) -> None:
        """Draw title and all children vertically."""
        curr_y = self.y
        
        # Draw title
        if self.title_font and self.title:
            title_img = self.title_font.render(self.title, True, self.title_color)
            surface.blit(title_img, (self.x, curr_y))
            self._title_height = title_img.get_height()
            curr_y += self._title_height + 6
        
        # Draw all children
        for elem, w, h in self.children:
            if isinstance(elem, str):
                # Render string
                if font:
                    img = font.render(elem, True, color)
                    surface.blit(img, (self.x, curr_y))
                    curr_y += img.get_height() + self.spacing
            elif isinstance(elem, (HBox, VBox)):
                # Nested layout container - update position and draw
                elem.x = self.x
                elem.y = curr_y
                elem.draw(surface, font=font, color=color)
                curr_y += elem.get_height() + self.spacing
            elif hasattr(elem, 'draw'):
                # Element has a draw method
                # Use set_position if available (for MessageBox, etc.)
                if hasattr(elem, 'set_position'):
                    elem.set_position(self.x, curr_y)
                else:
                    if hasattr(elem, 'x'):
                        elem.x = self.x
                    if hasattr(elem, 'y'):
                        elem.y = curr_y
                elem.draw(surface)
                curr_y += h + self.spacing
            elif isinstance(elem, pygame.Surface):
                surface.blit(elem, (self.x, curr_y))
                curr_y += h + self.spacing

class CheckpointTimeline:
    """Control for displaying checkpoint timeline with circles."""
    def __init__(self, telemetry: 'TelemetryState', x: int = 0, y: int = 0, font_small: Optional[pygame.font.Font] = None, fg_color=(235, 235, 235)):
        self.telemetry = telemetry
        self.x = x
        self.y = y
        self.font_small = font_small
        self.fg_color = fg_color
        self._height = 60
    
    def get_width(self) -> int:
        return 500
    
    def get_height(self) -> int:
        return self._height
    
    def draw(self, surface: pygame.Surface) -> None:
        """Draw checkpoint timeline with circles."""
        # Timeline settings
        timeline_width = 500
        cp_spacing = timeline_width // (TOTAL_CHECKPOINTS + 1)
        cp_radius = 18
        line_y = self.y + 20

        # Draw horizontal line
        # pygame.draw.line(surface, (100, 100, 100), 
        #                 (self.x + cp_spacing, line_y), 
        #                 (self.x + cp_spacing * TOTAL_CHECKPOINTS, line_y), 2)

        # Draw checkpoint circles
        for cp_num in range(1, TOTAL_CHECKPOINTS + 1):
            cp_x = self.x + cp_spacing * cp_num
#            is_completed = cp_num in self.telemetry.completed_checkpoints
            is_completed = cp_num <= self.telemetry.last_checkpoint

            if is_completed:
                # Filled circle for completed
                pygame.draw.circle(surface, (0, 200, 100), (cp_x, line_y), cp_radius)
            else:
                # Empty circle for not completed
                pygame.draw.circle(surface, (100, 100, 100), (cp_x, line_y), cp_radius, 2)
            
            # Draw the lines between the circles
            if cp_num > 1:
                pygame.draw.line(surface, (100, 100, 100),
                                (self.x + cp_spacing * (cp_num - 1) + cp_radius, line_y),
                                (self.x + cp_spacing * cp_num - cp_radius, line_y), 2)
            
            # Draw checkpoint number
            if self.font_small:
                label = self.font_small.render(str(cp_num), True, self.fg_color)
                label_x = cp_x - label.get_width() // 2
                label_y = line_y + cp_radius + 6
                surface.blit(label, (label_x, label_y))

class Dial:
    """Control for displaying heading angle as a dial with needle."""
    def __init__(self, telemetry: 'TelemetryState', x: int = 0, y: int = 0, 
                 radius: int = 60, font_small: Optional[pygame.font.Font] = None, 
                 fg_color=(235, 235, 235)):
        self.telemetry = telemetry
        self.x = x
        self.y = y
        self.radius = radius
        self.font_small = font_small
        self.fg_color = fg_color
    
    def get_width(self) -> int:
        return self.radius * 2 + 40
    
    def get_height(self) -> int:
        return self.radius * 2 + 60
    
    def draw(self, surface: pygame.Surface) -> None:
        """Draw heading dial with needle."""
        center_x = self.x + self.radius + 20
        center_y = self.y + self.radius + 20
        
        # Draw dial circle (background)
        pygame.draw.circle(surface, (60, 60, 60), (center_x, center_y), self.radius, 3)
        
        # Draw angle labels at 45° increments (-180 to 180)
        # Note: 0° is up/north, angles increase clockwise (like compass heading)
        angles = [-180, -135, -90, -45, 0, 45, 90, 135, 180]
        
        for angle in angles:
            # Convert angle to radians (0° is up/north)
            rad = math.radians(angle)
            # Position text outside the circle
            text_dist = self.radius + 15
            text_x = center_x + math.sin(rad) * text_dist
            text_y = center_y - math.cos(rad) * text_dist
            
            if self.font_small:
                label_text = f"{angle}°" if (angle != 180 and angle != -180) else "±180°"
                label_img = self.font_small.render(label_text, True, (150, 150, 150))
                # Center the text on the position
                text_x -= label_img.get_width() // 2
                text_y -= label_img.get_height() // 2
                surface.blit(label_img, (text_x, text_y))
        
        # Draw heading needle
        heading = self.telemetry.gz  # Angle between -180 and 180
        # Convert heading to radians (0° is up/north)
        needle_rad = math.radians(heading)
        needle_length = self.radius - 10
        needle_end_x = center_x + math.sin(needle_rad) * needle_length
        needle_end_y = center_y - math.cos(needle_rad) * needle_length
        
        # Draw needle line
        pygame.draw.line(surface, (255, 100, 100), (center_x, center_y), 
                        (needle_end_x, needle_end_y), 3)
        
        # Draw needle head (small circle)
        pygame.draw.circle(surface, (255, 100, 100), (int(needle_end_x), int(needle_end_y)), 5)
        
        # Draw center point
        pygame.draw.circle(surface, (200, 200, 200), (center_x, center_y), 4)
        
        # Draw heading value below dial
        if self.font_small:
            heading_text = f"Heading: {heading:.1f}°"
            heading_img = self.font_small.render(heading_text, True, self.fg_color)
            heading_x = center_x - heading_img.get_width() // 2
            heading_y = center_y + self.radius + 20
            surface.blit(heading_img, (heading_x, heading_y))


# -----------------------------
# Main App
# -----------------------------
class App:
    BG = (25, 28, 34)
    FG = (235, 235, 235)
    ACCENT = (80, 180, 255)

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("BLE Robot Telemetry Monitor")
        self.screen = pygame.display.set_mode((1200, 800), pygame.RESIZABLE)
        self.WIDTH = self.screen.get_width()
        self.HEIGHT = self.screen.get_height()
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, UI_FONT_SIZE)
        self.font_small = pygame.font.SysFont(None, UI_FONT_SMALL_SIZE)
        self.font_title = pygame.font.SysFont(None, UI_TITLE_FONT_SIZE)

        # Create MessageBox for log display (position will be set in draw)
        log_y = self.HEIGHT - UI_LOG_HEIGHT - UI_LOG_BOTTOM_OFFSET
        self.message_box = MessageBox(UI_MARGIN_LEFT, log_y, self.WIDTH - 32, UI_LOG_HEIGHT, font=self.font_small)
        
        # Runtime options
        self.use_header = False
        self.line_ending_key = 'BOTH'
        self.frequency = float(DEFAULT_FREQUENCY_HZ)

        # Components
        self.telemetry = TelemetryState()
        self.conn = BleConnection()
        self.conn.log.connect(self.message_box.add)
        self.conn.rx.connect(self._on_rx)
        self.conn.payload_wrapper = self._add_header
        self._rx_lines = LineAssembler()

        self.actions_config = ActionsConfig()
        self.actions_config.load()
        self.message_box.add(f"Loaded actions.json. Header: [{self.actions_config.header_hex}]\n")

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
        """Feed JSON telemetry lines to the telemetry state, log the others (called from the BLE thread)."""
        for line in self._rx_lines.feed(chunk):
            line = line.strip()
            if not line:
                continue
            try:
                try:
                    self.telemetry.update_from_json(json.loads(line))
                except json.JSONDecodeError:
                    # Not JSON, display raw message
                    self.message_box.add(f"Received: {line}\n")
            except Exception as e:
                self.message_box.add(f"Handler error: {e}\n")

    def _send_manual_text(self, text: str) -> bool:
        """Send manually typed text. Returns True if it was sent."""
        if not self.conn.send_text(text, self._end_data()):
            return False
        hdr_info = " (with header)" if self.use_header else ""
        self.message_box.add(f"Sent: {text}{hdr_info}\n")
        return True

    # ----------- rendering -----------
    def draw_header(self) -> None:
        y = UI_MARGIN_TOP
        
        # Title
        img = self.font_title.render("Robot Telemetry Monitor", True, self.ACCENT)
        self.screen.blit(img, (UI_MARGIN_LEFT, y))
        y += img.get_height() + UI_SECTION_SPACING
        
        # Connection status
        connected = self.conn.is_connected
        status = "CONNECTED" if connected else "DISCONNECTED"
        status_color = (0, 200, 100) if connected else (255, 80, 80)
        img = self.font.render(f"Status: {status}", True, status_color)
        self.screen.blit(img, (UI_MARGIN_LEFT, y))
        y += img.get_height() + UI_SECTION_SPACING
        
        # Controls info (more compact)
        img = self.font_small.render("Controls: C=Scan | ENTER=Connect | UP/DOWN=Select | H=Header | F=Line End | +/-=Freq | T=Type | ESC=Quit", True, (150, 150, 150))
        self.screen.blit(img, (UI_MARGIN_LEFT, y))
        y += img.get_height() + UI_SECTION_SPACING
        
        # Master VBox layout
        master_vbox = VBox(x=UI_MARGIN_LEFT, y=y, spacing=UI_SPACING_LARGE)
        
        # First HBox: Checkpoints and Available Devices
        first_hbox = HBox(spacing=UI_SPACING_HBOX)
        
        # Checkpoints section
        timeline_control = CheckpointTimeline(self.telemetry, x=0, y=0, font_small=self.font_small, fg_color=self.FG)
        checkpoint_box = VBoxWithTitle("Checkpoints:", title_font=self.font, title_color=self.FG, spacing=UI_SPACING_MEDIUM, min_width=UI_COL_1_MIN_WIDTH)
        checkpoint_box.add(timeline_control, width=timeline_control.get_width(), height=timeline_control.get_height())
        
        # Available Devices section
        devices_box = VBoxWithTitle("Available Devices:", title_font=self.font, title_color=self.FG, spacing=UI_SPACING_SMALL, min_width=UI_COL_1_MIN_WIDTH, min_height=UI_DEVICE_MIN_HEIGHT)
        if self.devices.devices:
            for i, dev in enumerate(self.devices.devices[:UI_DEVICE_MAX]):
                sel = (i == self.devices.selected_index)
                color = self.ACCENT if sel else (200, 200, 200)
                text = f"{'► ' if sel else '  '} {dev.name}"
                devices_box.add(text)
        else:
            # Add empty message as a child element so min_height constraint applies
            devices_box.add("No devices (press C to scan)")

       
        first_hbox.add(checkpoint_box)
        first_hbox.add(devices_box)
     
     
        master_vbox.add(first_hbox)
        
        # Second HBox: Telemetry and Actions
        second_hbox = HBox(spacing=UI_SPACING_HBOX)
        
        # Telemetry section
        col1_vbox = VBox(spacing=UI_SPACING_MEDIUM, min_width=200)
        col1_items = [
            f"State: {self.telemetry.etat}",
            f"Timestamp: {self.telemetry.ts} ms",
            f"Chrono: {self.telemetry.chrono} ms",
            f"Angle Z: {self.telemetry.gz:.2f}°"
        ]
        for item in col1_items:
            col1_vbox.add(item)
        
        col2_vbox = VBox(spacing=UI_SPACING_MEDIUM, min_width=200)
        col2_items = [
            f"PWM L: {self.telemetry.pwm_l}  R: {self.telemetry.pwm_r}",
            f"Sensors: {self.telemetry.capt}",
            f"Checkpoint: {self.telemetry.last_checkpoint}/{TOTAL_CHECKPOINTS}",
        ]
        for item in col2_items:
            col2_vbox.add(item)
        
        columns_hbox = HBox(spacing=UI_SPACING_HBOX)
        columns_hbox.add(col1_vbox)
        columns_hbox.add(col2_vbox)
        
        telemetry_box = VBoxWithTitle("Telemetry:", title_font=self.font, title_color=self.FG, spacing=UI_SPACING_MEDIUM, min_width=UI_COL_1_MIN_WIDTH)
        # Add columns_hbox with width to make it expand and fill available space
        telemetry_box.add(columns_hbox, width=UI_COL_1_MIN_WIDTH)

        # Create Dial control for heading visualization
        dial_control = Dial(self.telemetry, radius=60, font_small=self.font_small, fg_color=self.FG)

        
        # Actions section
        actions_box = VBoxWithTitle("Actions:", title_font=self.font, title_color=self.FG, spacing=UI_SPACING_SMALL, min_width=UI_COL_1_MIN_WIDTH)
        if self.actions_config.actions:
            for act in self.actions_config.actions[:UI_ACTION_MAX]:
                label = f"{act.get('label') or act.get('key','?').upper()} ({act.get('key','?').upper()})"
                actions_box.add(label)
        
        second_hbox.add(telemetry_box) 
        second_hbox.add(dial_control)
        second_hbox.add(actions_box)
        master_vbox.add(second_hbox)
        
        
        # Message box section - add to master VBox
        self.message_box.set_size(self.WIDTH - 32, UI_LOG_HEIGHT)
        master_vbox.add(self.message_box, width=self.WIDTH - 32, height=UI_LOG_HEIGHT)
        
        # Draw the master VBox
        master_vbox.draw(self.screen, font=self.font_small, color=self.FG)
        
        # text input overlay
        self.text_input.draw(self.screen, self.font,
                             pygame.Rect(0, self.HEIGHT - UI_LOG_INPUT_HEIGHT, self.WIDTH, UI_LOG_INPUT_HEIGHT),
                             margin=UI_MARGIN_LEFT)

    def _draw_telemetry_data(self, x: int, y: int) -> int:
        """Draw telemetry data section using VBoxWithTitle containing HBox. Returns new y position."""
        # Left column (VBox of items)
        col1_vbox = VBox(x=x + 10, y=y + 25, spacing=4)
        col1_items = [
            f"State: {self.telemetry.etat}",
            f"Timestamp: {self.telemetry.ts} ms",
            f"Chrono: {self.telemetry.chrono} ms",
            f"Gyro Z: {self.telemetry.gz:.2f}°/s",
        ]
        for item in col1_items:
            col1_vbox.add(item)
        
        # Right column (VBox of PWM/Sensor items)
        col2_vbox = VBox(x=x + 300, y=y + 25, spacing=4)
        pwm_text = f"PWM L: {self.telemetry.pwm_l}  R: {self.telemetry.pwm_r}"
        sensor_text = f"Sensors: {self.telemetry.capt}"
        col2_vbox.add(pwm_text)
        col2_vbox.add(sensor_text)
        
        # HBox containing both columns
        columns_hbox = HBox(x=x, y=y + 25, spacing=20)
        columns_hbox.add(col1_vbox)
        columns_hbox.add(col2_vbox)
        
        # VBoxWithTitle containing the HBox
        telemetry_box = VBoxWithTitle("Telemetry:", x=x, y=y, title_font=self.font, title_color=self.FG, spacing=6)
        telemetry_box.add(columns_hbox)
        telemetry_box.draw(self.screen, font=self.font_small, color=self.FG)
        
        # Calculate total height
        col1_height = col1_vbox.get_height()
        col2_height = col2_vbox.get_height()
        total_height = max(col1_height, col2_height) + 25  # 25 for title
        
        return y + total_height + 10

    def _draw_checkpoint_timeline(self, x: int, y: int) -> int:
        """Draw checkpoint timeline using VBoxWithTitle. Returns new y position."""
        # Create CheckpointTimeline control
        timeline_control = CheckpointTimeline(self.telemetry, x=x, y=y + 25, font_small=self.font_small, fg_color=self.FG)
        
        # Create VBoxWithTitle and add the timeline control
        checkpoint_box = VBoxWithTitle("Checkpoints:", x=x, y=y, title_font=self.font, title_color=self.FG, spacing=6)
        checkpoint_box.add(timeline_control, width=timeline_control.get_width(), height=timeline_control.get_height())
        checkpoint_box.draw(self.screen)
        
        return y + 25 + timeline_control.get_height() + 10

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
