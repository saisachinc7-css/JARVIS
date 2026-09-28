"""
JARVIS JARVIS UI - Sci-Fi Holographic Interface
A stunning floating popup that displays JARVIS conversations with animated effects.
"""

import sys
import time
import threading
from typing import Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QScrollArea, QFrame, QGraphicsDropShadowEffect
    )
    from PySide6.QtCore import (
        Qt, QTimer, QPropertyAnimation, QEasingCurve, 
        Signal as pyqtSignal, QObject, QThread, Property as pyqtProperty, QPoint, QSize
    )
    from PySide6.QtGui import (
        QFont, QColor, QPainter, QLinearGradient, QRadialGradient,
        QPen, QBrush, QPainterPath, QFontDatabase
    )
    PYQT_AVAILABLE = True
except ImportError:
    try:
        from PyQt6.QtWidgets import (
            QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
            QLabel, QScrollArea, QFrame, QGraphicsDropShadowEffect
        )
        from PyQt6.QtCore import (
            Qt, QTimer, QPropertyAnimation, QEasingCurve, 
            pyqtSignal, QObject, QThread, pyqtProperty, QPoint, QSize
        )
        from PyQt6.QtGui import (
            QFont, QColor, QPainter, QLinearGradient, QRadialGradient,
            QPen, QBrush, QPainterPath, QFontDatabase
        )
        PYQT_AVAILABLE = True
    except ImportError:
        PYQT_AVAILABLE = False
        print("[JARVIS UI] PySide6/PyQt6 not installed. Run: pip install PySide6")


class JarvisState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


@dataclass
class ChatMessage:
    role: str  # "user", "jarvis", "system", "tool"
    content: str
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


# ============================================================================
# COLOR SCHEME - Premium Sci-Fi Palette
# ============================================================================
class Colors:
    # Primary backgrounds
    BG_DARK = "#0a0e17"
    BG_PANEL = "#0d1321"
    BG_CARD = "#141b2d"
    
    # Accent colors - Neon spectrum
    CYAN = "#00d4ff"
    CYAN_GLOW = "#00d4ff40"
    PURPLE = "#a855f7"
    PURPLE_GLOW = "#a855f740"
    PINK = "#ec4899"
    ORANGE = "#f97316"
    GREEN = "#22c55e"
    
    # Text
    TEXT_PRIMARY = "#e2e8f0"
    TEXT_SECONDARY = "#94a3b8"
    TEXT_MUTED = "#64748b"
    
    # Gradients (start, end)
    GRADIENT_PRIMARY = ("#00d4ff", "#a855f7")
    GRADIENT_ACTIVE = ("#22c55e", "#00d4ff")
    GRADIENT_WARM = ("#f97316", "#ec4899")


# ============================================================================
# ANIMATED ORB - Pulsating Core
# ============================================================================
class JarvisOrb(QWidget):
    """Animated holographic orb that indicates JARVIS's state."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(80, 80)
        self._state = JarvisState.IDLE
        self._pulse_value = 0.0
        self._rotation = 0.0
        
        # Animation timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(30)  # ~33 FPS
        
    def set_state(self, state: JarvisState):
        self._state = state
        self.update()
        
    def _animate(self):
        self._pulse_value = (self._pulse_value + 0.05) % (2 * 3.14159)
        self._rotation = (self._rotation + 2) % 360
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        center_x = self.width() // 2
        center_y = self.height() // 2
        
        # Calculate pulse effect
        import math
        pulse = 0.5 + 0.5 * math.sin(self._pulse_value)
        
        # Colors based on state
        if self._state == JarvisState.LISTENING:
            color1 = QColor(Colors.GREEN)
            color2 = QColor(Colors.CYAN)
            outer_glow = QColor(Colors.GREEN)
        elif self._state == JarvisState.PROCESSING:
            color1 = QColor(Colors.ORANGE)
            color2 = QColor(Colors.PINK)
            outer_glow = QColor(Colors.ORANGE)
        elif self._state == JarvisState.SPEAKING:
            color1 = QColor(Colors.PURPLE)
            color2 = QColor(Colors.PINK)
            outer_glow = QColor(Colors.PURPLE)
        else:  # IDLE
            color1 = QColor(Colors.CYAN)
            color2 = QColor(Colors.PURPLE)
            outer_glow = QColor(Colors.CYAN)
        
        # Outer glow rings (animated)
        if self._state != JarvisState.IDLE:
            for i in range(3):
                ring_alpha = int(80 * (1 - i * 0.3) * pulse)
                ring_size = 35 + i * 8 + pulse * 5
                outer_glow.setAlpha(ring_alpha)
                painter.setPen(QPen(outer_glow, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(
                    QPoint(center_x, center_y), 
                    int(ring_size), int(ring_size)
                )
        
        # Inner gradient orb
        gradient = QRadialGradient(center_x, center_y, 30)
        gradient.setColorAt(0, color1)
        gradient.setColorAt(0.7, color2)
        gradient.setColorAt(1, QColor(color2.red(), color2.green(), color2.blue(), 50))
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(QPoint(center_x, center_y), 25, 25)
        
        # Center bright core
        core_gradient = QRadialGradient(center_x - 5, center_y - 5, 15)
        core_gradient.setColorAt(0, QColor(255, 255, 255, 200))
        core_gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(core_gradient))
        painter.drawEllipse(QPoint(center_x, center_y), 15, 15)


# ============================================================================
# CHAT MESSAGE WIDGET
# ============================================================================
class MessageWidget(QFrame):
    """Individual chat message with styling."""
    
    def __init__(self, message: ChatMessage, parent=None):
        super().__init__(parent)
        self.message = message
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        
        # Role label
        role_label = QLabel(self._get_role_display())
        role_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        role_label.setStyleSheet(f"color: {self._get_role_color()}; background: transparent;")
        
        # Content label
        content_label = QLabel(self.message.content)
        content_label.setFont(QFont("Segoe UI", 10))
        content_label.setWordWrap(True)
        content_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | 
            Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        content_label.setOpenExternalLinks(True)
        content_label.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY}; 
            background: transparent;
            line-height: 1.4;
        """)
        
        layout.addWidget(role_label)
        layout.addWidget(content_label)
        
        # Card styling
        self.setStyleSheet(f"""
            MessageWidget {{
                background: {self._get_bg_color()};
                border-radius: 12px;
                border-left: 3px solid {self._get_role_color()};
            }}
        """)
        
        # Glow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(self._get_role_color()))
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)
        
    def _get_role_display(self) -> str:
        mapping = {
            "user": "👤 YOU",
            "jarvis": "🤖 JARVIS",
            "system": "⚙️ SYSTEM",
            "tool": "🔧 TOOL RESULT"
        }
        return mapping.get(self.message.role, self.message.role.upper())
    
    def _get_role_color(self) -> str:
        mapping = {
            "user": Colors.CYAN,
            "jarvis": Colors.PURPLE,
            "system": Colors.TEXT_MUTED,
            "tool": Colors.GREEN
        }
        return mapping.get(self.message.role, Colors.TEXT_PRIMARY)
    
    def _get_bg_color(self) -> str:
        mapping = {
            "user": "#0d2137",
            "jarvis": "#1a0d2e",
            "system": "#1a1a1a",
            "tool": "#0d2d1a"
        }
        return mapping.get(self.message.role, Colors.BG_CARD)


# ============================================================================
# MAIN JARVIS WINDOW
# ============================================================================
class JarvisWindow(QMainWindow):
    """Main JARVIS-style floating window."""
    
    message_received = pyqtSignal(str, str)  # role, content
    state_changed = pyqtSignal(str)  # state name
    
    def __init__(self):
        super().__init__()
        self._messages: List[ChatMessage] = []
        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        
    def _setup_window(self):
        self.setWindowTitle("JARVIS")
        self.setFixedSize(420, 600)
        
        # Frameless, always on top, transparent background
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Position in bottom-right corner
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 440, screen.height() - 650)
        
    def _setup_ui(self):
        # Central widget with custom painting
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # Background frame
        self.bg_frame = QFrame()
        self.bg_frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {Colors.BG_DARK}, 
                    stop:0.5 {Colors.BG_PANEL},
                    stop:1 {Colors.BG_DARK}
                );
                border-radius: 20px;
                border: 1px solid {Colors.CYAN}40;
            }}
        """)
        
        frame_layout = QVBoxLayout(self.bg_frame)
        frame_layout.setContentsMargins(15, 15, 15, 15)
        frame_layout.setSpacing(15)
        
        # ===== HEADER =====
        header = QHBoxLayout()
        
        # Orb
        self.orb = JarvisOrb()
        header.addWidget(self.orb)
        
        # Title area
        title_layout = QVBoxLayout()
        
        title = QLabel("JARVIS")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"""
            color: {Colors.CYAN};
            background: transparent;
        """)
        
        self.status_label = QLabel("● IDLE")
        self.status_label.setFont(QFont("Segoe UI", 10))
        self.status_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; background: transparent;")
        
        title_layout.addWidget(title)
        title_layout.addWidget(self.status_label)
        header.addLayout(title_layout, 1)
        
        # Close button
        close_btn = QLabel("✕")
        close_btn.setFont(QFont("Segoe UI", 14))
        close_btn.setStyleSheet(f"""
            color: {Colors.TEXT_MUTED}; 
            background: transparent;
            padding: 5px;
        """)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.mousePressEvent = lambda e: self.hide()
        header.addWidget(close_btn)
        
        frame_layout.addLayout(header)
        
        # ===== SEPARATOR =====
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 transparent, stop:0.5 {Colors.CYAN}, stop:1 transparent);")
        frame_layout.addWidget(sep)
        
        # ===== CHAT AREA =====
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: {Colors.BG_DARK};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {Colors.CYAN}60;
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {Colors.CYAN};
            }}
        """)
        
        self.chat_widget = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_widget)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_layout.setSpacing(10)
        self.chat_layout.addStretch()
        
        self.scroll_area.setWidget(self.chat_widget)
        frame_layout.addWidget(self.scroll_area, 1)
        
        # ===== FOOTER =====
        footer = QLabel("Say 'Jarvis' to wake me up")
        footer.setFont(QFont("Segoe UI", 9))
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(f"color: {Colors.TEXT_MUTED}; background: transparent;")
        frame_layout.addWidget(footer)
        
        main_layout.addWidget(self.bg_frame)
        
        # Drop shadow for entire window
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 212, 255, 80))
        shadow.setOffset(0, 0)
        self.bg_frame.setGraphicsEffect(shadow)
        
    def _connect_signals(self):
        self.message_received.connect(self._add_message)
        self.state_changed.connect(self._update_state)
        
    def _add_message(self, role: str, content: str):
        msg = ChatMessage(role=role, content=content)
        self._messages.append(msg)
        
        # Create widget
        widget = MessageWidget(msg)
        
        # Insert before stretch
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, widget)
        
        # Scroll to bottom
        QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))
        
    def _update_state(self, state_name: str):
        state_map = {
            "idle": JarvisState.IDLE,
            "listening": JarvisState.LISTENING,
            "processing": JarvisState.PROCESSING,
            "speaking": JarvisState.SPEAKING
        }
        state = state_map.get(state_name.lower(), JarvisState.IDLE)
        self.orb.set_state(state)
        
        # Update status label
        status_colors = {
            JarvisState.IDLE: Colors.TEXT_MUTED,
            JarvisState.LISTENING: Colors.GREEN,
            JarvisState.PROCESSING: Colors.ORANGE,
            JarvisState.SPEAKING: Colors.PURPLE
        }
        status_text = {
            JarvisState.IDLE: "● IDLE",
            JarvisState.LISTENING: "● LISTENING",
            JarvisState.PROCESSING: "● PROCESSING",
            JarvisState.SPEAKING: "● SPEAKING"
        }
        self.status_label.setText(status_text[state])
        self.status_label.setStyleSheet(f"color: {status_colors[state]}; background: transparent;")
        
    def add_message(self, role: str, content: str):
        """Thread-safe message addition."""
        self.message_received.emit(role, content)
        
    def set_state(self, state: str):
        """Thread-safe state change."""
        self.state_changed.emit(state)
        
    # Enable window dragging
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            
    def mouseMoveEvent(self, event):
        if hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)


# ============================================================================
# GLOBAL INSTANCE & THREAD MANAGEMENT
# ============================================================================
_jarvis_window: Optional[JarvisWindow] = None
_app: Optional[QApplication] = None
_ui_thread: Optional[threading.Thread] = None


def _run_ui():
    """Run the UI in its own thread."""
    global _jarvis_window, _app
    
    _app = QApplication(sys.argv)
    _app.setStyle("Fusion")
    
    _jarvis_window = JarvisWindow()
    _jarvis_window.show()
    
    _app.exec()


def start_jarvis_ui():
    """Start the JARVIS UI in a background thread."""
    global _ui_thread
    
    if not PYQT_AVAILABLE:
        print("[JARVIS UI] PyQt6 not available. Install with: pip install PyQt6")
        return False
    
    if _ui_thread is not None and _ui_thread.is_alive():
        print("[JARVIS UI] Already running")
        return True
    
    _ui_thread = threading.Thread(target=_run_ui, daemon=True)
    _ui_thread.start()
    
    # Wait for window to be created
    for _ in range(50):
        if _jarvis_window is not None:
            print("[JARVIS UI] Started successfully")
            return True
        time.sleep(0.1)
    
    print("[JARVIS UI] Failed to start")
    return False


def add_message(role: str, content: str):
    """Add a message to the JARVIS UI."""
    if _jarvis_window is not None:
        _jarvis_window.add_message(role, content)


def set_state(state: str):
    """Set JARVIS state in the UI."""
    if _jarvis_window is not None:
        _jarvis_window.set_state(state)


def is_running() -> bool:
    """Check if UI is running."""
    return _jarvis_window is not None and _ui_thread is not None and _ui_thread.is_alive()


# ============================================================================
# TEST
# ============================================================================
if __name__ == "__main__":
    print("Testing JARVIS UI...")
    
    start_jarvis_ui()
    time.sleep(1)
    
    # Test messages
    add_message("system", "JARVIS initialized successfully")
    time.sleep(0.5)
    
    set_state("listening")
    add_message("user", "Search GitHub for email automation")
    time.sleep(1)
    
    set_state("processing")
    time.sleep(1)
    
    add_message("tool", "Found 5 repositories:\n\n1. ⭐ email-bot - Automated email sender\n   🔗 https://github.com/example/email-bot\n\n2. ⭐ mail-automator - Python email automation\n   🔗 https://github.com/example/mail-automator")
    
    set_state("speaking")
    add_message("jarvis", "I found 5 GitHub repositories for email automation. The top result is email-bot with 1.2k stars.")
    time.sleep(1)
    
    set_state("idle")
    
    # Keep running
    input("Press Enter to exit...")
