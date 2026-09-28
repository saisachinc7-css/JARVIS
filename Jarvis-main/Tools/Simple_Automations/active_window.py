"""
Active Window Detection Module
Detects which app or website the user is currently viewing/working on.
"""
import time
import threading

try:
    import win32gui
    import win32process
    import psutil
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    print("[JARVIS] Warning: pywin32 or psutil not installed. Active window detection disabled.")


# Known browsers and their process names
BROWSERS = {
    "chrome.exe": "Chrome",
    "msedge.exe": "Edge",
    "firefox.exe": "Firefox",
    "opera.exe": "Opera",
    "brave.exe": "Brave",
    "vivaldi.exe": "Vivaldi",
    "operagx.exe": "Opera GX",
    "comet.exe": "Comet",
}

# Current active window info (shared state)
_current_window = {
    "title": "",
    "app_name": "",
    "process_name": "",
    "is_browser": False,
    "url_hint": "",  # Best guess at website from title
}
_lock = threading.Lock()


def is_browser_active():
    """
    Check if the currently active window is a browser.
    Returns True if Edge, Opera GX, Comet, Chrome, or any known browser is active.
    """
    info = get_active_window_info()
    return info["is_browser"]


def get_active_window_info():
    """
    Get information about the currently active window.
    Returns a dict with: title, app_name, process_name, is_browser, url_hint
    """
    if not WIN32_AVAILABLE:
        return {"title": "", "app_name": "Unknown", "process_name": "", "is_browser": False, "url_hint": ""}
    
    try:
        # Get the foreground window handle
        hwnd = win32gui.GetForegroundWindow()
        
        if hwnd == 0:
            return {"title": "", "app_name": "Unknown", "process_name": "", "is_browser": False, "url_hint": ""}
        
        # Get window title
        window_title = win32gui.GetWindowText(hwnd)
        
        # Get process ID
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        
        # Get process name
        try:
            process = psutil.Process(pid)
            process_name = process.name().lower()
            app_name = process.name().replace(".exe", "").title()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            process_name = ""
            app_name = "Unknown"
        
        # Check if it's a browser
        is_browser = process_name in BROWSERS
        if is_browser:
            app_name = BROWSERS[process_name]
        
        # Try to extract website info from browser title
        url_hint = ""
        if is_browser and window_title:
            url_hint = extract_website_from_title(window_title)
        
        return {
            "title": window_title,
            "app_name": app_name,
            "process_name": process_name,
            "is_browser": is_browser,
            "url_hint": url_hint,
        }
        
    except Exception as e:
        return {"title": "", "app_name": "Unknown", "process_name": "", "is_browser": False, "url_hint": ""}


def extract_website_from_title(title):
    """
    Extract website name from browser window title.
    Most browsers show: "Page Title - Website Name - Browser"
    """
    title = title.lower()
    
    # Common website patterns
    websites = {
        "youtube": ["youtube", "- youtube"],
        "spotify": ["spotify"],
        "netflix": ["netflix"],
        "github": ["github"],
        "google": ["google search", "- google"],
        "twitter": ["twitter", "/ x"],
        "facebook": ["facebook"],
        "instagram": ["instagram"],
        "linkedin": ["linkedin"],
        "reddit": ["reddit"],
        "amazon": ["amazon"],
        "whatsapp": ["whatsapp"],
        "discord": ["discord"],
        "slack": ["slack"],
        "notion": ["notion"],
        "figma": ["figma"],
        "perplexity": ["perplexity"],
        "chatgpt": ["chatgpt", "openai"],
        "claude": ["claude"],
        "stackoverflow": ["stack overflow"],
        "medium": ["medium"],
        "twitch": ["twitch"],
    }
    
    for site, patterns in websites.items():
        for pattern in patterns:
            if pattern in title:
                return site
    
    return ""


def get_current_app():
    """
    Get the name of the current app/website the user is viewing.
    Returns a user-friendly string.
    """
    info = get_active_window_info()
    
    if info["is_browser"] and info["url_hint"]:
        return f"{info['url_hint'].title()} ({info['app_name']})"
    elif info["is_browser"]:
        return f"{info['app_name']} Browser"
    else:
        return info["app_name"]


def get_current_context():
    """
    Get detailed context about what the user is currently doing.
    Returns a formatted string for display.
    """
    info = get_active_window_info()
    
    if info["is_browser"]:
        if info["url_hint"]:
            return f"Viewing {info['url_hint'].title()} in {info['app_name']}"
        else:
            return f"Using {info['app_name']} browser"
    else:
        return f"Using {info['app_name']}"


def _monitor_active_window(callback=None, interval=1.0):
    """
    Continuously monitor the active window.
    Optionally call a callback function when the window changes.
    
    Args:
        callback: Function to call with new window info when it changes
        interval: How often to check (in seconds)
    """
    global _current_window
    last_title = ""
    
    while True:
        try:
            info = get_active_window_info()
            
            with _lock:
                _current_window = info
            
            # Only trigger callback on change
            if info["title"] != last_title:
                last_title = info["title"]
                if callback:
                    callback(info)
                    
        except Exception as e:
            pass
            
        time.sleep(interval)


def start_window_monitor(callback=None, interval=1.0):
    """
    Start monitoring the active window in a background thread.
    
    Args:
        callback: Optional function to call when active window changes
        interval: How often to check (in seconds)
    
    Returns:
        The monitoring thread
    """
    monitor_thread = threading.Thread(
        target=_monitor_active_window, 
        args=(callback, interval),
        daemon=True
    )
    monitor_thread.start()
    return monitor_thread


def get_cached_window_info():
    """
    Get the most recently cached window info (from the monitor thread).
    Use this for fast, non-blocking access to window info.
    """
    with _lock:
        return _current_window.copy()


# Simple logging callback for debugging
def log_window_change(info):
    """Default callback that prints window changes"""
    if info["is_browser"] and info["url_hint"]:
        print(f"[ACTIVE] Viewing: {info['url_hint'].title()} in {info['app_name']}")
    elif info["title"]:
        print(f"[ACTIVE] App: {info['app_name']} - {info['title'][:50]}...")


if __name__ == "__main__":
    # Test the module
    print("Testing Active Window Detection...")
    print("Switch between different windows to see the detection in action.")
    print("Press Ctrl+C to stop.\n")
    
    start_window_monitor(callback=log_window_change, interval=0.5)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")
