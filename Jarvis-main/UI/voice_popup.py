"""
JARVIS Voice Popup - Professional Dark Gradient Design
Elegant dark gradient with spotlight effect, polished aesthetic.
"""

import sys
import math
from typing import Optional

try:
    from PySide6.QtWidgets import (
        QApplication, QWidget, QLabel, QHBoxLayout,
        QGraphicsDropShadowEffect, QVBoxLayout, QTextEdit, QPushButton
    )
    from PySide6.QtCore import (
        Qt, QTimer, Signal as pyqtSignal, QRectF, QPointF, QMetaObject, Q_ARG, Slot as pyqtSlot
    )
    from PySide6.QtGui import (
        QFont, QColor, QPainter, QRadialGradient, QLinearGradient,
        QPen, QBrush, QPainterPath, QPaintEvent
    )
    PYQT_AVAILABLE = True
except ImportError:
    try:
        from PyQt6.QtWidgets import (
            QApplication, QWidget, QLabel, QHBoxLayout,
            QGraphicsDropShadowEffect, QVBoxLayout, QTextEdit, QPushButton
        )
        from PyQt6.QtCore import (
            Qt, QTimer, pyqtSignal, QRectF, QPointF, QMetaObject, Q_ARG, pyqtSlot
        )
        from PyQt6.QtGui import (
            QFont, QColor, QPainter, QRadialGradient, QLinearGradient,
            QPen, QBrush, QPainterPath, QPaintEvent
        )
        PYQT_AVAILABLE = True
    except ImportError:
        PYQT_AVAILABLE = False


# ============================================================================
# PROFESSIONAL COLOR PALETTE
# ============================================================================
class Colors:
    # Gradient colors (from reference image - dark gray with spotlight)
    BG_DARK = "#2a2a2a"
    BG_DARKER = "#1a1a1a"
    SPOTLIGHT = "#4a4a4a"  # Subtle light spot
    
    # Accent colors (subtle, professional)
    ACCENT_1 = "#6b7280"  # Soft gray
    ACCENT_2 = "#9ca3af"  # Light gray
    
    # Text
    TEXT_PRIMARY = "#ffffff"
    TEXT_MUTED = "#9ca3af"
    
    # Results panel
    RESULT_BG = "#1e1e1e"
    RESULT_BORDER = "#3a3a3a"
    RESULT_HIGHLIGHT = "#4a90d9"


# Size constants
COMPACT_WIDTH = 260
COMPACT_HEIGHT = 52
EXPANDED_WIDTH = 420
EXPANDED_HEIGHT = 380
ANIMATION_DURATION = 250  # ms


# ============================================================================
# ANIMATED WAVEFORM - Sleek bars
# ============================================================================
class WaveformWidget(QWidget):
    """Sleek animated waveform with subtle gradient bars."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 28)
        self._active = False
        self._phase = 0.0
        self._bar_heights = [0.4, 0.6, 0.5, 0.7]
        
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(40)  # 25 FPS smooth
        
    def set_active(self, active: bool):
        self._active = active
        self.update()
        
    def _animate(self):
        if self._active:
            self._phase = (self._phase + 0.12) % (2 * math.pi)
            for i in range(4):
                offset = i * 0.7
                self._bar_heights[i] = 0.25 + 0.75 * abs(math.sin(self._phase + offset))
        else:
            for i in range(4):
                self._bar_heights[i] = max(0.2, self._bar_heights[i] * 0.92)
        self.update()
        
    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        bar_width = 4
        gap = 5
        total_width = 4 * bar_width + 3 * gap
        start_x = (self.width() - total_width) // 2
        max_height = self.height() - 6
        
        for i in range(4):
            x = start_x + i * (bar_width + gap)
            height = max(4, int(max_height * self._bar_heights[i]))
            y = (self.height() - height) // 2
            
            # Gradient bar - white to gray
            alpha = 200 if self._active else 80
            gradient = QLinearGradient(x, y, x, y + height)
            gradient.setColorAt(0, QColor(255, 255, 255, alpha))
            gradient.setColorAt(1, QColor(180, 180, 180, alpha - 50))
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(gradient))
            
            path = QPainterPath()
            path.addRoundedRect(x, y, bar_width, height, 2, 2)
            painter.drawPath(path)


# ============================================================================
# RESULTS WINDOW - Separate floating window for content
# ============================================================================
class ResultsWindow(QWidget):
    """Separate OPAQUE window for displaying results. No translucent background to avoid Windows DWM freeze."""
    
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        # NO WA_TranslucentBackground - that causes Windows DWM freeze!
        self.setFixedSize(420, 320)
        
        # Style the entire window with dark background
        self.setStyleSheet(f"""
            ResultsWindow {{
                background-color: {Colors.BG_DARK};
                border: 1px solid {Colors.RESULT_BORDER};
                border-radius: 12px;
            }}
        """)
        
        self._setup_ui()
        
    def _setup_ui(self):
        # Main layout directly on window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Header with title and close
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.title_label = QLabel("Result")
        self.title_label.setFont(QFont("Segoe UI Semibold", 11))
        self.title_label.setStyleSheet(f"color: {Colors.RESULT_HIGHLIGHT}; background: transparent;")
        header_layout.addWidget(self.title_label, 1)
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                color: {Colors.TEXT_MUTED};
                background: transparent;
                border: none;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ color: {Colors.TEXT_PRIMARY}; }}
        """)
        close_btn.clicked.connect(self.hide)
        header_layout.addWidget(close_btn)
        
        layout.addWidget(header)
        
        # Content area
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Consolas", 10))
        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Colors.RESULT_BG};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.RESULT_BORDER};
                border-radius: 6px;
                padding: 8px;
            }}
            QScrollBar:vertical {{
                background: {Colors.RESULT_BG};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {Colors.ACCENT_1};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.text_edit)
        
    def set_content(self, title: str, content: str):
        self.title_label.setText(f"📋 {title}")
        self.text_edit.setPlainText(content)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            
    def mouseMoveEvent(self, event):
        if hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)


# ============================================================================
# VOICE POPUP - Professional Dark Design with Expandable Results
# ============================================================================
class VoicePopup(QWidget):
    """Professional voice popup that controls a separate results window."""
    
    closed = pyqtSignal()
    # Thread-safe signals for UI updates from any thread
    results_requested = pyqtSignal(str, str, int)
    text_requested = pyqtSignal(str)
    status_requested = pyqtSignal(str)
    collapse_requested = pyqtSignal()
    listening_requested = pyqtSignal()
    idle_requested = pyqtSignal()
    show_requested = pyqtSignal()   # Thread-safe .show()
    hide_requested = pyqtSignal()   # Thread-safe .hide()
    
    def __init__(self):
        super().__init__()
        self._text = ""
        self._auto_hide_timer = None
        self._results_visible = False  # Track if results are currently displayed
        
        # Create separate results window
        self.results_window = ResultsWindow()
        
        self._setup_window()
        self._setup_ui()
        
        # Connect ALL thread-safe signals - MUST use QueuedConnection for cross-thread
        conn = Qt.ConnectionType.QueuedConnection
        self.results_requested.connect(self._show_results_slot, conn)
        self.text_requested.connect(self._set_text_slot, conn)
        self.status_requested.connect(self._set_status_slot, conn)
        self.collapse_requested.connect(self._collapse_slot, conn)
        self.listening_requested.connect(self._show_listening_slot, conn)
        self.idle_requested.connect(self._show_idle_slot, conn)
        self.show_requested.connect(self._show_slot, conn)
        self.hide_requested.connect(self._hide_slot, conn)
        
    def _setup_window(self):
        self.setWindowTitle("")
        # Fixed size pill
        self.setFixedSize(COMPACT_WIDTH, COMPACT_HEIGHT)
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Position at bottom center
        self._reposition()
        
    def _reposition(self):
        """Reposition popup to stay centered at bottom of screen."""
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            screen.height() - self.height() - 70
        )
        
    def _setup_ui(self):
        # Main vertical layout
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)
        
        # Only header widget (the pill)
        self._header_widget = QWidget()
        self._header_widget.setFixedSize(COMPACT_WIDTH, COMPACT_HEIGHT)
        header_layout = QHBoxLayout(self._header_widget)
        header_layout.setContentsMargins(16, 0, 12, 0)
        header_layout.setSpacing(12)
        
        # Waveform
        self.waveform = WaveformWidget()
        self.waveform.set_active(True)
        header_layout.addWidget(self.waveform)
        
        # Text label
        self.text_label = QLabel("Listening...")
        self.text_label.setFont(QFont("Segoe UI", 12))
        self.text_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        header_layout.addWidget(self.text_label, 1)
        
        # Close button
        close_btn = QLabel("×")
        close_btn.setFont(QFont("Segoe UI", 11))
        close_btn.setStyleSheet(f"color: {Colors.TEXT_MUTED}; background: transparent;")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.mousePressEvent = lambda e: self._on_close_clicked()
        header_layout.addWidget(close_btn)
        
        self._main_layout.addWidget(self._header_widget)
        
        # Shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 8)
        self.setGraphicsEffect(shadow)
    
    def _on_close_clicked(self):
        """Handle close button click."""
        self.collapse_results()
        self.hide()
        
    def paintEvent(self, event: QPaintEvent):
        """Custom paint for gradient background with spotlight."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Fixed pill shape
        rect = QRectF(0, 0, self.width(), self.height())
        path = QPainterPath()
        path.addRoundedRect(rect, 26, 26)
        
        # Dark gradient base
        base_gradient = QLinearGradient(0, 0, self.width(), self.height())
        base_gradient.setColorAt(0, QColor(58, 58, 62))
        base_gradient.setColorAt(0.3, QColor(42, 42, 46))
        base_gradient.setColorAt(1, QColor(28, 28, 32))
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(base_gradient))
        painter.drawPath(path)
        
        # Spotlight effect
        spotlight = QRadialGradient(30, 15, 80)
        spotlight.setColorAt(0, QColor(255, 255, 255, 25))
        spotlight.setColorAt(1, QColor(255, 255, 255, 0))
        
        painter.setBrush(QBrush(spotlight))
        painter.drawPath(path)
        
        # Subtle border
        painter.setPen(QPen(QColor(255, 255, 255, 20), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
    
    # ===== PUBLIC METHODS =====
    
    def show_results(self, title: str, content: str, auto_hide_seconds: int = 20):
        """Thread-safe: Emit signal to show results on main thread."""
        self.results_requested.emit(title, content, auto_hide_seconds)
    
    @pyqtSlot(str, str, int)
    def _show_results_slot(self, title: str, content: str, auto_hide_seconds: int):
        """Slot: Actually expand popup and display results (runs on main thread)."""
        print(f"[Popup] Showing results window: {title}")
        
        # Mark results as visible (prevents idle from immediately hiding them)
        self._results_visible = True
        
        # Update popup text
        self.text_label.setText(title)
        self.waveform.set_active(False)
        super().show()
        self.raise_()
        self.activateWindow()
        
        # Update results window
        self.results_window.set_content(title, content)
        
        # Position results ABOVE popup
        popup_geo = self.geometry()
        # Center horizontally relative to popup
        results_x = popup_geo.center().x() - (self.results_window.width() // 2)
        # Position above popup with gap
        results_y = popup_geo.top() - self.results_window.height() - 20
        
        # Ensure it doesn't go off screen top
        if results_y < 20:
            results_y = 20
            
        self.results_window.move(results_x, results_y)
        
        self.results_window.show()
        self.results_window.raise_()
        
        # Auto-hide timer
        if self._auto_hide_timer:
            self._auto_hide_timer.stop()
        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self.collapse_results)
        self._auto_hide_timer.start(auto_hide_seconds * 1000)
    
    def collapse_results(self):
        """Thread-safe: Emit signal to collapse results."""
        self.collapse_requested.emit()
    
    @pyqtSlot()
    def _collapse_slot(self):
        """Slot: Actually collapse results (runs on main thread)."""
        print("[Popup] Hiding results window")
        self._results_visible = False
        self.results_window.hide()
        
        # Reset header
        self.text_label.setText("Say Jarvis")
        self.waveform.set_active(False)
        
        if self._auto_hide_timer:
            self._auto_hide_timer.stop()
        
    def set_text(self, text: str):
        """Thread-safe: Emit signal to update text."""
        self.text_requested.emit(text)
    
    @pyqtSlot(str)
    def _set_text_slot(self, text: str):
        """Slot: Actually update text (runs on main thread)."""
        self._text = text
        self.text_label.setText(text if text else "Listening...")
        
    def set_status(self, status: str):
        """Thread-safe: Emit signal to update status."""
        self.status_requested.emit(status)
    
    @pyqtSlot(str)
    def _set_status_slot(self, status: str):
        """Slot: Actually update status (runs on main thread)."""
        self.text_label.setText(status)
        
    def set_active(self, active: bool):
        """Set waveform animation (call from main thread only)."""
        self.waveform.set_active(active)
        
    def show_listening(self):
        """Thread-safe: Emit signal to show listening state."""
        self.listening_requested.emit()
    
    @pyqtSlot()
    def _show_listening_slot(self):
        """Slot: Actually show listening state (runs on main thread)."""
        # Hide results when listening starts
        self._results_visible = False
        self.results_window.hide()
        self.text_label.setText("Listening...")
        self.waveform.set_active(True)
        super().show()
        self.raise_()
        
    def show_processing(self):
        """Show processing state."""
        self.status_requested.emit("Processing...")
        
    def show_idle(self):
        """Thread-safe: Emit signal to show idle state."""
        self.idle_requested.emit()
    
    @pyqtSlot()
    def _show_idle_slot(self):
        """Slot: Actually show idle state (runs on main thread)."""
        # DON'T hide results if they are currently being displayed!
        if self._results_visible:
            print("[Popup] Idle requested but results are visible - keeping results")
            return
        self.results_window.hide()
        self.text_label.setText("Say Jarvis")
        self.waveform.set_active(False)
        super().show()
        self.raise_()
        
    def safe_show(self):
        """Thread-safe show - emits signal."""
        self.show_requested.emit()
        
    def safe_hide(self):
        """Thread-safe hide - emits signal."""
        self.hide_requested.emit()
        
    @pyqtSlot()
    def _show_slot(self):
        """Slot: Actually show (runs on main thread)."""
        super().show()
        self.raise_()
        
    @pyqtSlot()
    def _hide_slot(self):
        """Slot: Actually hide (runs on main thread)."""
        self._results_visible = False
        super().hide()
        self.results_window.hide()
    
    def hide(self):
        """Override hide to also hide results."""
        self._results_visible = False
        super().hide()
        self.results_window.hide()
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            
    def mouseMoveEvent(self, event):
        if hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            # Move results window with it if visible
            if self.results_window.isVisible():
                popup_geo = self.geometry()
                results_x = popup_geo.center().x() - (self.results_window.width() // 2)
                results_y = popup_geo.top() - self.results_window.height() - 20
                if results_y < 20: results_y = 20
                self.results_window.move(results_x, results_y)


# ============================================================================
# GLOBAL FUNCTIONS
# ============================================================================
_voice_popup: Optional[VoicePopup] = None
_app: Optional[QApplication] = None


def get_popup() -> Optional[VoicePopup]:
    return _voice_popup


def show_voice_popup():
    global _voice_popup
    if _voice_popup:
        _voice_popup.set_active(True)
        _voice_popup.show_listening()
        # NO direct .show() - show_listening_slot handles it on main thread


def hide_voice_popup():
    global _voice_popup
    if _voice_popup:
        _voice_popup.safe_hide()  # Thread-safe via signal


def show_idle_popup():
    """Show popup in idle state - stopped animation, 'Say Friday' text."""
    global _voice_popup
    if _voice_popup:
        _voice_popup.show_idle()
        # NO direct .show() - _show_idle_slot handles it on main thread


def update_voice_text(text: str):
    global _voice_popup
    if _voice_popup:
        _voice_popup.set_text(text)


def set_popup_status(status: str):
    global _voice_popup
    if _voice_popup:
        _voice_popup.set_status(status)


def show_results_in_popup(title: str, content: str, auto_hide_seconds: int = 20):
    """Display results in the expandable voice popup panel."""
    global _voice_popup
    if _voice_popup:
        _voice_popup.show_results(title, content, auto_hide_seconds)


def collapse_popup_results():
    """Collapse the results panel."""
    global _voice_popup
    if _voice_popup:
        _voice_popup.collapse_results()


def create_popup(app: QApplication) -> VoicePopup:
    global _voice_popup, _app
    _app = app
    _voice_popup = VoicePopup()
    return _voice_popup


# ============================================================================
# TEST
# ============================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    popup = VoicePopup()
    popup.show()
    
    sys.exit(app.exec())
