"""
Laptop Controls Provider for JARVIS
Central router for all system-level controls.

Connected to both Primary and Secondary Brain.
Works like ToolsProvider but for laptop hardware/system controls.

Usage:
    from Laptop_Controls.controls_provider import get_controls
    ctrl = get_controls()
    result = ctrl.route("increase brightness")
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Laptop_Controls.controller import LaptopController, get_laptop_controller


class ControlsProvider:
    """
    Central router for all laptop/system controls.
    Analyzes the request and routes to the correct control action.
    
    Controls:
        1. Brightness    — screen brightness up/down/set
        2. Volume        — system volume up/down/mute
        3. WiFi          — enable/disable WiFi
        4. Bluetooth     — enable/disable Bluetooth
        5. Power         — sleep, shutdown, restart
        6. Screen        — lock, screenshot
    """

    CONTROL_KEYWORDS = {
        "brightness": [
            "brightness", "screen light", "dim", "brighten",
            "screen brighter", "screen darker",
        ],
        "volume": [
            "volume", "louder", "quieter", "mute", "unmute",
            "sound up", "sound down",
        ],
        "wifi": [
            "wifi", "wi-fi", "wireless", "internet connection",
        ],
        "bluetooth": [
            "bluetooth", "bt ", "wireless device",
        ],
        "sleep": [
            "sleep", "hibernate", "standby",
        ],
        "shutdown": [
            "shutdown", "shut down", "power off", "turn off laptop",
            "turn off computer",
        ],
        "restart": [
            "restart", "reboot", "re-start",
        ],
        "screenshot": [
            "screenshot", "screen capture", "capture screen",
            "print screen",
        ],
        "start_recording": [
            "start screen recording", "start recording", "record screen",
            "record my screen", "screen recording start",
        ],
        "stop_recording": [
            "stop screen recording", "stop recording", "stop record",
            "stop my screen record", "screen recording stop",
        ],
        "lock": [
            "lock screen", "lock computer", "lock laptop",
            "lock my pc",
        ],
    }

    def __init__(self):
        self.controller = get_laptop_controller()

    def route(self, user_input: str) -> dict:
        """
        Route a request to the appropriate laptop control.
        
        Args:
            user_input: The user's request
            
        Returns:
            Dict with action, success status, and result
        """
        action, kwargs = self._parse_request(user_input)
        
        if not action:
            return {
                "success": False,
                "action": None,
                "message": "No matching laptop control found."
            }

        print(f"[ControlsProvider] Executing: {action} with {kwargs}")
        
        result = self.controller.execute(action, **kwargs)
        return {**result, "action": action}

    def _parse_request(self, user_input: str) -> tuple:
        """Parse the request to identify action and parameters."""
        input_lower = user_input.lower()
        
        # Find matching action
        best_action = None
        best_score = 0
        
        for action, keywords in self.CONTROL_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in input_lower)
            if score > best_score:
                best_score = score
                best_action = action
        
        if not best_action:
            return None, {}

        # Extract parameters
        kwargs = {}
        
        if best_action == "brightness":
            # Check for level (number)
            import re
            numbers = re.findall(r'\d+', user_input)
            if numbers:
                kwargs["level"] = int(numbers[0])
            elif any(w in input_lower for w in ["up", "increase", "brighter", "more"]):
                kwargs["action"] = "up"
            elif any(w in input_lower for w in ["down", "decrease", "dim", "less", "darker"]):
                kwargs["action"] = "down"
        
        elif best_action == "volume":
            import re
            numbers = re.findall(r'\d+', user_input)
            if "mute" in input_lower:
                kwargs["action"] = "mute"
            elif "unmute" in input_lower:
                kwargs["action"] = "unmute"
            elif any(w in input_lower for w in ["up", "increase", "louder", "more"]):
                kwargs["action"] = "up"
                if numbers:
                    kwargs["level"] = int(numbers[0])
            elif any(w in input_lower for w in ["down", "decrease", "quieter", "less"]):
                kwargs["action"] = "down"
                if numbers:
                    kwargs["level"] = int(numbers[0])
        
        elif best_action in ("wifi", "bluetooth"):
            if any(w in input_lower for w in ["off", "disable", "turn off"]):
                kwargs["action"] = "off"
            elif any(w in input_lower for w in ["on", "enable", "turn on"]):
                kwargs["action"] = "on"
            else:
                kwargs["action"] = "status"
        
        elif best_action == "shutdown":
            import re
            numbers = re.findall(r'\d+', user_input)
            if numbers:
                kwargs["timer"] = int(numbers[0])
        
        return best_action, kwargs

    # ===== DIRECT ACCESS =====

    def brightness(self, level: int = None, action: str = None):
        return self.controller.execute("brightness", level=level, action=action)

    def volume(self, action: str = "up", level: int = None):
        return self.controller.execute("volume", action=action, level=level)

    def wifi(self, action: str = "status"):
        return self.controller.execute("wifi", action=action)

    def sleep(self):
        return self.controller.execute("sleep")

    def shutdown(self, timer: int = 0):
        return self.controller.execute("shutdown", timer=timer)

    def restart(self):
        return self.controller.execute("restart")

    def screenshot(self):
        return self.controller.execute("screenshot")

    def start_recording(self):
        return self.controller.execute("start_recording")

    def stop_recording(self):
        return self.controller.execute("stop_recording")

    def lock(self):
        return self.controller.execute("lock")


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================
_controls_provider = None


def get_controls() -> ControlsProvider:
    """Get the global ControlsProvider instance."""
    global _controls_provider
    if _controls_provider is None:
        _controls_provider = ControlsProvider()
    return _controls_provider
