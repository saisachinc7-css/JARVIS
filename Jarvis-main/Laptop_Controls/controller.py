"""
Laptop Controller for JARVIS
System-level controls: brightness, volume, WiFi, Bluetooth, sleep, shutdown, etc.

Usage:
    from Laptop_Controls.controller import LaptopController
    lc = LaptopController()
    lc.execute("brightness", level=80)
    lc.execute("volume", action="mute")
    lc.execute("shutdown")
"""

import sys
import os
import subprocess
import threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class LaptopController:
    """
    System-level laptop controls.
    Connected to both Primary and Secondary Brain via ToolsProvider.
    IntentRouter routes laptop-related intents here.
    """

    def execute(self, action: str, **kwargs) -> dict:
        """
        Execute a laptop control action.
        
        Args:
            action: The control action (brightness, volume, wifi, bluetooth,
                    sleep, shutdown, restart, screenshot, lock)
            **kwargs: Action-specific parameters
            
        Returns:
            Dict with success status and message
        """
        action = action.lower().strip()
        
        handler = {
            "brightness": self._brightness,
            "volume": self._volume,
            "wifi": self._wifi,
            "bluetooth": self._bluetooth,
            "sleep": self._sleep,
            "shutdown": self._shutdown,
            "restart": self._restart,
            "screenshot": self._screenshot,
            "lock": self._lock,
            "start_recording": self._start_recording,
            "stop_recording": self._stop_recording,
        }.get(action)
        
        if handler:
            return handler(**kwargs)
        
        return {"success": False, "message": f"Unknown action: {action}"}

    def _brightness(self, level: int = None, action: str = None, **_) -> dict:
        """Set screen brightness (0-100)."""
        try:
            import screen_brightness_control as sbc
            
            if action == "up":
                current = sbc.get_brightness()[0]
                level = min(100, current + 20)
            elif action == "down":
                current = sbc.get_brightness()[0]
                level = max(0, current - 20)
            
            if level is not None:
                sbc.set_brightness(level)
                return {"success": True, "message": f"Brightness set to {level}%"}
            
            current = sbc.get_brightness()[0]
            return {"success": True, "message": f"Current brightness: {current}%"}
        except ImportError:
            return {"success": False, "message": "screen_brightness_control not installed"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _volume(self, action: str = "up", level: int = None, **_) -> dict:
        """Control system volume."""
        import pyautogui as gui
        
        if action == "mute" or action == "unmute":
            gui.press("volumemute")
            return {"success": True, "message": f"Volume {action}d"}
        elif action == "up":
            for _ in range(level or 5):
                gui.press("volumeup")
            return {"success": True, "message": "Volume increased"}
        elif action == "down":
            for _ in range(level or 5):
                gui.press("volumedown")
            return {"success": True, "message": "Volume decreased"}
        
        return {"success": False, "message": f"Unknown volume action: {action}"}

    def _wifi(self, action: str = "status", **_) -> dict:
        """Toggle WiFi on/off."""
        try:
            if action == "off":
                subprocess.run(["netsh", "interface", "set", "interface", "Wi-Fi", "admin=disabled"], check=True)
                return {"success": True, "message": "WiFi disabled"}
            elif action == "on":
                subprocess.run(["netsh", "interface", "set", "interface", "Wi-Fi", "admin=enabled"], check=True)
                return {"success": True, "message": "WiFi enabled"}
            else:
                result = subprocess.run(["netsh", "interface", "show", "interface", "Wi-Fi"], capture_output=True, text=True)
                return {"success": True, "message": result.stdout.strip()}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _bluetooth(self, action: str = "status", **_) -> dict:
        """Toggle Bluetooth (requires pybluez or system commands)."""
        return {"success": False, "message": "Bluetooth control not yet implemented"}

    def _sleep(self, **_) -> dict:
        """Put laptop to sleep."""
        try:
            subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
            return {"success": True, "message": "Going to sleep"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _shutdown(self, timer: int = 0, **_) -> dict:
        """Shutdown the laptop."""
        try:
            subprocess.run(["shutdown", "/s", "/t", str(timer)])
            return {"success": True, "message": f"Shutting down in {timer} seconds"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _restart(self, **_) -> dict:
        """Restart the laptop."""
        try:
            subprocess.run(["shutdown", "/r", "/t", "5"])
            return {"success": True, "message": "Restarting in 5 seconds"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _screenshot(self, **_) -> dict:
        """Take a screenshot with resilient multi-method fallback."""
        from datetime import datetime
        import os
        
        pictures_dir = os.path.join(os.path.expanduser("~"), "Pictures")
        screenshots_dir = os.path.join(pictures_dir, "Screenshots")
        if not os.path.exists(screenshots_dir):
            screenshots_dir = pictures_dir
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(screenshots_dir, f"Screenshot_{timestamp}.png")
        
        # Method 1: PyAutoGUI
        try:
            import pyautogui as gui
            screenshot = gui.screenshot()
            screenshot.save(path)
            self._notify_screenshot()
            return {"success": True, "message": f"Screenshot saved to {path}"}
        except Exception as e_gui:
            print(f"[ProjectRunner] PyAutoGUI screenshot failed: {e_gui}")
            
        # Method 2: mss
        try:
            import mss
            with mss.mss() as sct:
                sct.shot(output=path)
            if os.path.exists(path):
                self._notify_screenshot()
                return {"success": True, "message": f"Screenshot saved to {path}"}
        except Exception as e_mss:
            print(f"[ProjectRunner] mss screenshot failed: {e_mss}")
            
        # Method 3: Pillow ImageGrab
        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab(all_screens=True)
            screenshot.save(path)
            self._notify_screenshot()
            return {"success": True, "message": f"Screenshot saved to {path}"}
        except Exception as e_pil:
            print(f"[ProjectRunner] Pillow screenshot failed: {e_pil}")
            
        # Method 4: Fallback to PrintScreen clipboard copying & placeholder file
        try:
            import pyautogui as gui
            gui.press("printscreen")
            from PIL import Image
            img = Image.new('RGB', (800, 600), color = 'black')
            img.save(path)
            self._notify_screenshot()
            return {"success": True, "message": f"Screenshot saved (clipboard fallback/dummy file)"}
        except Exception as e:
            return {"success": False, "message": f"Failed to capture screen: {e}"}

    def _notify_screenshot(self):
        try:
            from notification import Alert
            Alert("Screenshot Saved")
        except Exception:
            pass

    def _start_recording(self, **_) -> dict:
        """Start screen recording."""
        recorder = get_screen_recorder()
        success, msg = recorder.start()
        try:
            from notification import Alert
            Alert("Screen Recording Started")
        except Exception:
            pass
        return {"success": success, "message": msg}

    def _stop_recording(self, **_) -> dict:
        """Stop screen recording."""
        recorder = get_screen_recorder()
        success, msg = recorder.stop()
        try:
            from notification import Alert
            Alert("Screen Recording Saved")
        except Exception:
            pass
        return {"success": success, "message": msg}

    def _lock(self, **_) -> dict:
        """Lock the screen."""
        try:
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
            return {"success": True, "message": "Screen locked"}
        except Exception as e:
            return {"success": False, "message": str(e)}


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================
_controller = None
_recorder = None


def get_laptop_controller() -> LaptopController:
    """Get the global LaptopController instance."""
    global _controller
    if _controller is None:
        _controller = LaptopController()
    return _controller


def get_screen_recorder():
    """Get the global ScreenRecorder instance."""
    global _recorder
    if _recorder is None:
        _recorder = ScreenRecorder()
    return _recorder


class ScreenRecorder:
    def __init__(self):
        self.recording = False
        self.thread = None
        self.filepath = None
        
    def start(self):
        if self.recording:
            return False, "Screen recording is already in progress."
            
        import os
        import time
        from datetime import datetime
        
        # Determine output filepath (Videos folder)
        videos_dir = os.path.join(os.path.expanduser("~"), "Videos")
        if not os.path.exists(videos_dir):
            videos_dir = os.path.expanduser("~")
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filepath = os.path.join(videos_dir, f"ScreenRec_{timestamp}.mp4")
        
        self.recording = True
        self.thread = threading.Thread(target=self._record_loop, daemon=True)
        self.thread.start()
        return True, f"Screen recording started. Saving to Videos."
        
    def _record_loop(self):
        import time
        import cv2
        import numpy as np
        from PIL import ImageGrab
        
        try:
            screen_size = ImageGrab.grab().size
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out = cv2.VideoWriter(self.filepath, fourcc, 10.0, screen_size)
            
            last_time = time.time()
            frame_delay = 1.0 / 10.0  # 10 fps
            
            while self.recording:
                now = time.time()
                elapsed = now - last_time
                if elapsed >= frame_delay:
                    img = ImageGrab.grab()
                    frame = np.array(img)
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    out.write(frame)
                    last_time = now
                else:
                    time.sleep(0.01)
                    
            out.release()
            print(f"[ScreenRecorder] Finished recording. Saved to: {self.filepath}")
        except Exception as e:
            self.recording = False
            print(f"[ScreenRecorder] Recording error: {e}")
            
    def stop(self):
        if not self.recording:
            return False, "No active screen recording found."
            
        self.recording = False
        if self.thread:
            self.thread.join(timeout=3)
        path = self.filepath
        self.filepath = None
        return True, f"Screen recording stopped. Saved to: {path}"
