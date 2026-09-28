import time
import psutil
import subprocess
import webbrowser

try:
    import pyautogui as ui
except ImportError:
    ui = None

def is_spotify_running():
    """Check if Spotify process is running"""
    try:
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and 'spotify.exe' in proc.info['name'].lower():
                return True
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        pass
    return False

def play_music_on_spotify(song_name):
    """Opens Spotify desktop app, searches for a song, and plays it"""

    if ui is None:
        query = song_name.replace(" ", "%20")
        webbrowser.open(f"https://open.spotify.com/search/{query}")
        print(f"Spotify GUI automation unavailable; opened search for '{song_name}' in browser.")
        return
    
    # Check if Spotify is already running (Cold Start Detection)
    was_running = is_spotify_running()
    print(f"Spotify running status: {was_running}")
    
    # Open Spotify app via Windows Start menu
    ui.press("win")
    time.sleep(0.1)
    ui.write("spotify", interval=0.02)
    time.sleep(0.2)
    ui.press("enter")
    
    # SMART WAIT: Wait for Spotify to be the active window
    print("Waiting for Spotify to open...")
    start_time = time.time()
    spotify_focused = False
    
    # Try to import active window detection
    try:
        from Tools.Simple_Automations.active_window import get_active_window_info
        
        while time.time() - start_time < 15:  # 15s timeout
            info = get_active_window_info()
            app_name = info.get("app_name", "").lower()
            title = info.get("title", "").lower()
            
            if "spotify" in app_name or "spotify" in title:
                print("Spotify detected!")
                spotify_focused = True
                break
            time.sleep(0.2)
    except ImportError:
        # Fallback if module not found
        print("Active window module not found, using fixed sleep...")
        time.sleep(4)
        spotify_focused = True
        
    if not spotify_focused:
        print("Spotify launch timed out, trying to proceed anyway...")

    # Extra wait for Cold Start (UI loading time)
    if not was_running:
        print("Cold start detected: Waiting extra 5 seconds for UI to load...")
        time.sleep(5)
    else:
        # Small buffer even if already running
        time.sleep(0.5)
        
    # Open search with Ctrl+L (Spotify desktop shortcut)
    ui.hotkey("ctrl", "l")
    time.sleep(0.5) # Increased buffer
    
    # Type the song name
    ui.write(song_name, interval=0.01)
    time.sleep(0.5)
    
    # Press Enter to search
    ui.press("enter")
    time.sleep(2.0)  # Wait for search results
    
    # Press Enter to play the first result
    ui.press("enter")
    print(f"Playing '{song_name}' on Spotify...")

if __name__ == "__main__":
    while True:
        x = input("Song name: ")
        if x.strip():
            play_music_on_spotify(x.strip())
