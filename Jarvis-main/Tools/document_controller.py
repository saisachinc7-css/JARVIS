"""
Document Controller for JARVIS Document Intelligence
Handles launching files in system default viewers, active window verification,
page scrolling, zooming, page navigation, and window closure.
"""

import os
import sys
import time
import subprocess
import pyautogui as gui

gui.FAILSAFE = False

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from Tools.Simple_Automations.active_window import get_active_window_info


def open_document(file_path: str, timeout: float = 12.0) -> bool:
    """
    Launch document in default viewer and wait until active window verifies load.
    """
    if not os.path.exists(file_path):
        print(f"[DocumentController] File path does not exist: {file_path}")
        return False

    print(f"[DocumentController] Launching document: {file_path}")
    
    # Launch in system default app
    try:
        if sys.platform == "win32":
            os.startfile(file_path)
        else:
            subprocess.Popen(["open", file_path])
    except Exception as e:
        print(f"[DocumentController] os.startfile failed ({e}), using start shell command...")
        subprocess.Popen(f'start "" "{file_path}"', shell=True)

    # Wait for viewer window to become active
    fname = os.path.basename(file_path).lower()
    fname_no_ext = os.path.splitext(fname)[0]

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            info = get_active_window_info()
            title = info.get("title", "").lower()
            if fname_no_ext in title or fname in title or any(w in title for w in ["acrobat", "reader", "word", "powerpoint", "chrome", "edge", "notepad"]):
                print(f"[DocumentController] Document window verified: {title}")
                return True
        except Exception:
            pass
        time.sleep(0.5)

    print("[DocumentController] Viewer launched (window load polling timed out, continuing).")
    return True


def scroll_document(direction: str = "down", amount: int = 4) -> bool:
    """Scroll active document up or down."""
    try:
        key = "pagedown" if direction.lower() in ["down", "next"] else "pageup"
        for _ in range(amount):
            gui.press(key)
            time.sleep(0.1)
        return True
    except Exception as e:
        print(f"[DocumentController] Scroll error: {e}")
        return False


def zoom_document(direction: str = "in") -> bool:
    """Zoom in or zoom out of active document."""
    try:
        key = "=" if direction.lower() in ["in", "more"] else "-"
        for _ in range(3):
            gui.hotkey("ctrl", key)
            time.sleep(0.1)
        return True
    except Exception as e:
        print(f"[DocumentController] Zoom error: {e}")
        return False


def goto_page_in_viewer(page_num: int) -> bool:
    """Navigate to specific page in active document viewer."""
    try:
        # Common viewer hotkey: Ctrl + G or Alt + G
        gui.hotkey("ctrl", "g")
        time.sleep(0.3)
        gui.typewrite(str(page_num))
        time.sleep(0.2)
        gui.press("enter")
        return True
    except Exception as e:
        print(f"[DocumentController] Page navigation error: {e}")
        return False


def close_document_viewer() -> bool:
    """Close active document viewer window."""
    try:
        gui.hotkey("ctrl", "w")
        time.sleep(0.5)
        return True
    except Exception as e:
        print(f"[DocumentController] Close window error: {e}")
        return False
