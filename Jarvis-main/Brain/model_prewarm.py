"""
Model Pre-warmer for JARVIS.

Loads all Ollama models into GPU VRAM at startup via 1-token keepalive pings.
This eliminates the cold-start latency for the first user command after launch.

Usage (called once from Jarvis.py at startup):
    from Brain.model_prewarm import prewarm_models_async
    prewarm_models_async()   # Non-blocking, runs in background thread
"""

import threading
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fix OLLAMA_HOST if pointing to server binding address
if os.environ.get("OLLAMA_HOST", "").strip() in ("0.0.0.0", "0.0.0.0:11434"):
    os.environ["OLLAMA_HOST"] = "127.0.0.1:11434"

# All models used anywhere in JARVIS — must stay in sync with:
#   Brain/intent_engine.py   → qwen3:8b   (IntentEngine.MODEL)
#   Brain/task_queue.py      → qwen3:8b   (TaskDecomposer.MODEL)
#   Brain/secondary_brain.py → deepseek-r1:8b (SecondaryBrain MODEL)
#   Agents/WhatsApp_Agent/   → qwen3:8b   (independent instance)
MODELS_TO_PREWARM = [
    "qwen2.5:0.5b",    # Primary: IntentEngine + TaskDecomposer + WhatsApp Agent
    "deepseek-r1:8b",  # Secondary Brain
]

# How long to wait between pinging each model (avoids VRAM spike)
_STAGGER_SECONDS = 2.0


def _safe_print(msg: str):
    """Print safely on Windows cp1252 consoles."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"))


def ensure_ollama_running():
    """Verify if Ollama server is running. If not, auto-start it in the background."""
    import urllib.request
    import subprocess
    import time
    
    url = "http://127.0.0.1:11434/"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=2.0) as response:
            if response.status == 200:
                _safe_print("[ModelPrewarmer] Ollama server is already running.")
                return True
    except Exception:
        pass
        
    _safe_print("[ModelPrewarmer] Ollama server is offline. Attempting auto-start...")
    
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        _safe_print("[ModelPrewarmer] Spawned 'ollama serve' subprocess.")
    except Exception as e:
        _safe_print(f"[ModelPrewarmer] Failed to launch Ollama subprocess: {e}")
        return False
        
    _safe_print("[ModelPrewarmer] Waiting for Ollama server to initialize...")
    for attempt in range(30):
        time.sleep(0.5)
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as response:
                if response.status == 200:
                    _safe_print("[ModelPrewarmer] Ollama server initialized successfully!")
                    return True
        except Exception:
            pass
            
    _safe_print("[ModelPrewarmer] Warning: Ollama server startup check timed out.")
    return False


class ModelPrewarmer:
    """
    Sends 1-token "keepalive" requests to each Ollama model at startup.

    Ollama will then:
      1. Pull the model weights from disk into GPU VRAM (the slow part, ~10-30s)
      2. Keep them loaded for subsequent requests (fast, < 1s per request)

    This makes the first real user command feel instant instead of frozen.
    """

    def __init__(self, models=None, stagger=_STAGGER_SECONDS):
        self.models = models or MODELS_TO_PREWARM
        self.stagger = stagger
        self._done = False
        self._thread = None

    def prewarm_all_async(self) -> threading.Thread:
        """
        Start a daemon background thread that warms all models.
        Returns immediately — does NOT block the main thread.
        """
        self._thread = threading.Thread(
            target=self._prewarm_all,
            daemon=True,
            name="JarvisModelPrewarmer",
        )
        self._thread.start()
        return self._thread

    def _prewarm_all(self):
        """Background worker: ping each model with a 1-token request."""
        # Auto-start Ollama server if it's not running
        ensure_ollama_running()
        
        try:
            import ollama
        except ImportError:
            _safe_print("[ModelPrewarmer] 'ollama' package not installed — skipping pre-warm")
            return

        _safe_print(
            f"[ModelPrewarmer] Starting GPU pre-warm for {len(self.models)} models..."
        )
        warmed = 0

        for model in self.models:
            try:
                t0 = time.time()
                # 1-token generation → just enough to force the model into VRAM
                ollama.generate(
                    model=model,
                    prompt="hi",
                    options={"num_predict": 1},
                )
                elapsed = time.time() - t0
                _safe_print(f"[ModelPrewarmer] {model:20s} ready ({elapsed:.1f}s)")
                warmed += 1
            except Exception as e:
                _safe_print(f"[ModelPrewarmer] {model:20s} SKIP — {e}")

            # Stagger requests slightly so we don't slam disk I/O simultaneously
            if model != self.models[-1]:
                time.sleep(self.stagger)

        self._done = True
        _safe_print(
            f"[ModelPrewarmer] Done! {warmed}/{len(self.models)} models "
            f"are hot in GPU VRAM — commands will now respond instantly."
        )

    @property
    def is_done(self) -> bool:
        return self._done


# ── Singleton instance ──────────────────────────────────────────────────────

_prewarm_instance = ModelPrewarmer()


def prewarm_models_async() -> threading.Thread:
    """
    Called once from Jarvis.py at startup to pre-warm all LLM models.

    Non-blocking: returns immediately while warming happens in the background.
    Safe to call multiple times — will just spawn another background pass.
    """
    return _prewarm_instance.prewarm_all_async()
