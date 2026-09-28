"""
Screen Vision Module for JARVIS.

Captures the current screen and uses a vision-capable AI model to analyze
and describe what is visible. Tries the following providers in order:

    1. Google Gemini API  (requires GEMINI_API_KEY in .env)
    2. Ollama llava model  (requires `ollama pull llava:7b` locally)
    3. Graceful text-only fallback (reports active window title only)

Usage:
    from Tools.screen_vision import ScreenVision
    sv = ScreenVision()
    result = sv.capture_and_analyze()
    print(result["description"])
"""

import os
import sys
import threading
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# SCREEN CAPTURE HELPER
# ============================================================================

def _capture_screen(save_path: str) -> bool:
    """
    Capture the current screen using 4-method fallback chain.
    Returns True on success, False on total failure.
    """
    # Method 1: PyAutoGUI
    try:
        import pyautogui as gui
        img = gui.screenshot()
        img.save(save_path)
        if os.path.exists(save_path) and os.path.getsize(save_path) > 1024:
            return True
    except Exception as e:
        print(f"[ScreenVision] PyAutoGUI failed: {e}")

    # Method 2: mss
    try:
        import mss
        with mss.mss() as sct:
            sct.shot(output=save_path)
        if os.path.exists(save_path) and os.path.getsize(save_path) > 1024:
            return True
    except Exception as e:
        print(f"[ScreenVision] mss failed: {e}")

    # Method 3: Pillow ImageGrab
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(all_screens=True)
        img.save(save_path)
        if os.path.exists(save_path) and os.path.getsize(save_path) > 1024:
            return True
    except Exception as e:
        print(f"[ScreenVision] Pillow failed: {e}")

    # Method 4: PrintScreen placeholder
    try:
        import pyautogui as gui
        gui.press("printscreen")
        from PIL import Image
        img = Image.new("RGB", (1920, 1080), color="black")
        img.save(save_path)
        return True
    except Exception as e:
        print(f"[ScreenVision] Fallback failed: {e}")

    return False


# ============================================================================
# VISION ANALYSIS PROVIDERS
# ============================================================================

def _analyze_with_gemini(image_path: str, api_key: str) -> str:
    """
    Analyze screen image using Google Gemini Vision API (new google-genai SDK).
    Returns empty string on ANY failure so the caller automatically falls back to Ollama.
    """
    use_ollama_only = os.getenv("USE_OLLAMA_ONLY", "false").lower() in ("true", "1", "yes")
    if use_ollama_only or not api_key or "YOUR_" in api_key:
        return ""

    try:
        from google import genai

        client = genai.Client(api_key=api_key)

        from PIL import Image
        img = Image.open(image_path)

        prompt = (
            "You are JARVIS, an AI assistant analyzing the user's screen. "
            "Look at this screenshot and describe clearly:\n"
            "1. Which applications or windows are open.\n"
            "2. What the user appears to be working on.\n"
            "3. Any important text, code, browser tabs, or interface elements visible.\n"
            "4. The overall context of what the user is doing right now.\n\n"
            "Keep your response concise (3-5 sentences), natural, and professional. "
            "Address the user as 'Sir'. Do not describe technical file paths or GUI chrome — "
            "focus on meaningful context."
        )

        # Try Gemini models from fastest to lightest — any quota/error → next model
        models_to_try = [
            "gemini-2.5-flash",
            "gemini-2.0-flash-lite",
            "gemini-2.0-flash",
        ]

        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[prompt, img],
                )
                text = response.text.strip() if response.text else ""
                if text:
                    print(f"[ScreenVision] Gemini success via: {model_name}")
                    return text
            except Exception as model_err:
                # Log but NEVER raise — always try next model, then fall back to Ollama
                err_str = str(model_err)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    print(f"[ScreenVision] {model_name} — quota exceeded, trying next...")
                elif "404" in err_str or "not found" in err_str.lower():
                    print(f"[ScreenVision] {model_name} — not available, trying next...")
                else:
                    print(f"[ScreenVision] {model_name} — error: {err_str[:120]}, trying next...")
                continue

        # All Gemini models failed — return "" so Ollama takes over
        print("[ScreenVision] All Gemini models failed — handing off to Ollama.")
        return ""

    except ImportError:
        print("[ScreenVision] google-genai not installed — handing off to Ollama.")
        return ""
    except Exception as e:
        print(f"[ScreenVision] Gemini setup error: {e} — handing off to Ollama.")
        return ""


def _analyze_with_ollama_llava(image_path: str) -> str:
    """
    Analyze screen image using local Ollama vision model.
    Tries multiple llava model name variants — uses whichever is installed.
    """
    try:
        import ollama
        import base64

        # Auto-detect which vision model is available
        available_models: list = []
        try:
            models_resp = ollama.list()
            # models_resp is a dict with 'models' key
            raw_models = models_resp.get("models", []) if isinstance(models_resp, dict) else getattr(models_resp, "models", [])
            available_models = [
                (m.get("name", "") if isinstance(m, dict) else getattr(m, "name", "")).lower()
                for m in raw_models
            ]
        except Exception:
            pass  # Can't list models — will try hardcoded names

        # Priority order: most capable → most likely to be installed
        candidates = [
            "llava:13b",
            "llava:7b",
            "llava",
            "llava:latest",
            "llava-llama3",
            "bakllava",
            "moondream",
        ]

        # If we could list models, filter to only installed ones (preserving priority order)
        if available_models:
            candidates = [c for c in candidates if any(c in m for m in available_models)]
            if not candidates:
                print("[ScreenVision] No vision model found in Ollama. Run: ollama pull llava")
                return ""

        with open(image_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode("utf-8")

        prompt = (
            "You are JARVIS, an AI assistant analyzing the user's screen. "
            "Describe what you see clearly in 3-5 sentences. "
            "Mention which applications are open, what the user is working on, "
            "and any key visible information. Address the user as 'Sir'."
        )

        for model_name in candidates:
            try:
                response = ollama.chat(
                    model=model_name,
                    messages=[{
                        "role": "user",
                        "content": prompt,
                        "images": [img_data]
                    }],
                    options={"temperature": 0.2}
                )
                text = ""
                if isinstance(response, dict):
                    text = response.get("message", {}).get("content", "").strip()
                else:
                    text = getattr(getattr(response, "message", None), "content", "").strip()

                if text:
                    print(f"[ScreenVision] Ollama model used: {model_name}")
                    return text
            except Exception as e:
                err = str(e)
                if "model" in err.lower() and ("not found" in err.lower() or "pull" in err.lower()):
                    print(f"[ScreenVision] Ollama model '{model_name}' not installed — trying next...")
                    continue
                else:
                    print(f"[ScreenVision] Ollama '{model_name}' error: {e}")
                    continue

        print("[ScreenVision] No working Ollama vision model found. Run: ollama pull llava")
        return ""

    except ImportError:
        print("[ScreenVision] ollama package not installed — skipping Ollama.")
        return ""
    except Exception as e:
        print(f"[ScreenVision] Ollama analysis failed: {e}")
        return ""


def _analyze_with_window_title_fallback() -> str:
    """Fallback: read active window title + running processes for basic context."""
    try:
        from Tools.Simple_Automations.active_window import get_active_window_info
        info = get_active_window_info()
        title = info.get("title", "Unknown")
        is_browser = info.get("is_browser", False)
        url_hint = info.get("url_hint", "")

        if is_browser and url_hint:
            return (
                f"Sir, I can see a browser window is active. "
                f"It appears to be showing {url_hint}. "
                f"I'm unable to visually analyze the full screen content right now, "
                f"but the active tab appears to be: {title}."
            )
        else:
            return (
                f"Sir, the active window on your screen is titled '{title}'. "
                f"I'm unable to perform a full visual analysis right now — "
                f"a vision model (Gemini API or Ollama llava) is required for that. "
                f"Please configure GEMINI_API_KEY in your .env file or run 'ollama pull llava:7b'."
            )
    except Exception as e:
        return (
            "Sir, I'm unable to analyze the screen at this moment. "
            "Please configure a vision model (GEMINI_API_KEY or Ollama llava) to enable this feature."
        )


# ============================================================================
# MAIN SCREEN VISION CLASS
# ============================================================================

class ScreenVision:
    """
    Analyzes the current screen using available vision AI providers.

    Priority order:
        1. Gemini API (if GEMINI_API_KEY configured in .env)
        2. Ollama llava (if llava:7b model is pulled)
        3. Active window title fallback (always available)
    """

    def __init__(self):
        self._api_key = self._load_gemini_key()

    def _load_gemini_key(self) -> str:
        """Load Gemini API key from environment or .env file."""
        # Check environment first
        key = os.environ.get("GEMINI_API_KEY", "")
        if key and key != "YOUR_GEMINI_API_KEY_HERE":
            return key

        # Try loading from .env file
        try:
            env_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                ".env"
            )
            if os.path.exists(env_path):
                with open(env_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GEMINI_API_KEY="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val and val != "YOUR_GEMINI_API_KEY_HERE":
                                return val
        except Exception:
            pass

        return ""

    def capture(self) -> str:
        """
        Take a screenshot and return the saved file path.
        Returns empty string on failure.
        """
        pictures_dir = os.path.join(os.path.expanduser("~"), "Pictures", "Screenshots")
        os.makedirs(pictures_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(pictures_dir, f"Vision_{timestamp}.png")

        success = _capture_screen(path)
        if success and os.path.exists(path):
            print(f"[ScreenVision] Screenshot captured: {path}")
            return path

        print("[ScreenVision] Screenshot capture failed entirely.")
        return ""

    def analyze(self, image_path: str) -> dict:
        """
        Analyze a screenshot image using the best available vision provider.

        Returns a dict with keys:
            - description (str): Natural language description
            - provider (str): Which model was used
            - image_path (str): Path to the screenshot
        """
        description = ""
        provider = "fallback"

        # Try Gemini first (fastest, most capable)
        if self._api_key:
            print("[ScreenVision] Trying Gemini API...")
            description = _analyze_with_gemini(image_path, self._api_key)
            if description:
                provider = "gemini"

        # Try Ollama llava second
        if not description:
            print("[ScreenVision] Trying Ollama llava...")
            description = _analyze_with_ollama_llava(image_path)
            if description:
                provider = "ollama_llava"

        # Fallback: window title only
        if not description:
            print("[ScreenVision] Using window-title fallback.")
            description = _analyze_with_window_title_fallback()
            provider = "fallback"

        return {
            "description": description,
            "provider": provider,
            "image_path": image_path
        }

    def custom_analyze(self, image_path: str, custom_prompt: str) -> str:
        """Analyze a screenshot using a custom prompt via Gemini or Ollama."""
        if self._api_key:
            try:
                from google import genai
                client = genai.Client(api_key=self._api_key)
                from PIL import Image
                img = Image.open(image_path)
                
                models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash-lite", "gemini-2.0-flash"]
                for model_name in models_to_try:
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=[custom_prompt, img]
                        )
                        text = response.text.strip() if response.text else ""
                        if text:
                            return text
                    except Exception:
                        continue
            except Exception:
                pass
        
        # Fallback to Ollama if local model available
        try:
            import ollama
            import base64
            with open(image_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode("utf-8")
            response = ollama.chat(
                model="llava",
                messages=[{"role": "user", "content": custom_prompt, "images": [img_data]}],
                options={"temperature": 0.1}
            )
            if isinstance(response, dict):
                return response.get("message", {}).get("content", "").strip()
            else:
                return getattr(getattr(response, "message", None), "content", "").strip()
        except Exception:
            pass
            
        return ""

    def capture_and_analyze(self) -> dict:
        """
        Full pipeline: capture the screen then analyze it.

        Returns the result dict from analyze(), or an error dict on failure.
        """
        path = self.capture()

        if not path:
            description = _analyze_with_window_title_fallback()
            return {
                "description": description,
                "provider": "fallback",
                "image_path": ""
            }

        return self.analyze(path)


# ============================================================================
# GLOBAL SINGLETON
# ============================================================================

_vision_instance: ScreenVision = None


def get_screen_vision() -> ScreenVision:
    """Get or create the global ScreenVision instance."""
    global _vision_instance
    if _vision_instance is None:
        _vision_instance = ScreenVision()
    return _vision_instance
