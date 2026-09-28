import os
import subprocess
import time

try:
    import pyautogui as gui
except ImportError:
    gui = None

def open_App(text):
    """Opens an app using Windows Start menu search"""
    if gui is not None:
        gui.press("win")
        time.sleep(0.4)  # Wait for Start menu to open
        gui.write(text, interval=0.05)  # Type slowly for reliability
        time.sleep(0.4)  # Wait for search results
        gui.press("enter")
        print(f"Opening {text}...")
        return

    # Fallback for environments without pyautogui. This is best-effort and
    # avoids crashing startup when GUI automation is unavailable.
    try:
        os.startfile(text)
        print(f"Opening {text}...")
    except OSError:
        try:
            subprocess.Popen(
                ["cmd", "/c", "start", "", text],
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"Opening {text}...")
        except Exception:
            print(f"[App_open] pyautogui unavailable; unable to open '{text}'")

if __name__ == "__main__":
    while True:
        x = input("App name: ")
        if x.strip():
            open_App(x.strip())
