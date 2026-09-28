"""
Alert module - Shows visual notifications using Windows toast notifications
"""
from win10toast import ToastNotifier
import threading

# Create a single notifier instance
_notifier = ToastNotifier()
_alert_lock = threading.Lock()


def Alert(message, title="JARVIS"):
    """Show a Windows toast notification"""
    with _alert_lock:
        try:
            _notifier.show_toast(
                title,
                message,
                duration=5,
                threaded=True
            )
        except Exception as e:
            print(f"[Alert] {title}: {message}")
