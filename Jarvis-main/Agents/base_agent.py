"""
Base Agent for JARVIS
Standard interface that ALL agents must follow.

Every agent:
  1. Has its own LLM config (model, temperature, etc.) in config.py
  2. Has access to main memory (facts, schedule, preferences)
  3. Implements process(request) -> dict
  4. Generates responses using its own LLM settings
"""

import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


class BaseAgent:
    """
    Abstract base class for all JARVIS agents.
    
    Subclasses must:
      1. Set AGENT_NAME
      2. Set LLM config (MODEL, OLLAMA_OPTIONS, SYSTEM_PROMPT) in their config.py
      3. Implement process(request) -> dict
    """

    AGENT_NAME = "BaseAgent"

    def __init__(self):
        # Load agent-specific config
        self._load_config()
        
        # Connect to main memory
        self._memory = None
        self._init_memory()

    def _load_config(self):
        """Load LLM config. Override in subclass or set via config.py."""
        self.model = "qwen3:4b"
        self.system_prompt = "You are a JARVIS agent."
        self.ollama_options = {
            "temperature": 0.15,
            "top_p": 0.85,
            "repeat_penalty": 1.15,
            "repeat_last_n": 128,
            "num_ctx": 4096,
            "num_batch": 256,
            "seed": 42,
            "num_predict": 1500,
        }

    def _init_memory(self):
        """Connect to JARVIS's main memory system."""
        try:
            from Brain.Memory.memory_manager import get_memory
            self._memory = get_memory()
            if self._memory and self._memory.is_available():
                print(f"[{self.AGENT_NAME}] Memory connected")
            else:
                self._memory = None
        except Exception as e:
            safe_err = str(e).encode('ascii', errors='replace').decode()
            print(f"[{self.AGENT_NAME}] Memory unavailable: {safe_err}")
            self._memory = None

    @property
    def memory(self):
        """Access main memory. Returns None if unavailable."""
        return self._memory

    def recall_memory(self, query: str = "") -> str:
        """Recall relevant memories for this request."""
        if not self._memory:
            return ""
        try:
            return self._memory.recall(query) or ""
        except Exception:
            return ""

    LLM_TIMEOUT = 30  # Max seconds to wait for any single LLM call

    def llm_generate(self, prompt: str, system: str = None) -> str:
        """
        Call Ollama with THIS AGENT's custom LLM settings.
        Each agent has its own temperature, top_p, seed, etc.

        Enforces a timeout so a slow/stuck LLM never blocks the pipeline.
        """
        if not OLLAMA_AVAILABLE:
            return ""

        sys_prompt = system or self.system_prompt
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt},
        ]

        import threading

        result_box = [""]  # Mutable container for thread result
        error_box = [None]

        def _call():
            try:
                response = ollama.chat(
                    model=self.model,
                    messages=messages,
                    options=self.ollama_options,
                )
                answer = response.get("message", {}).get("content", "").strip()

                # Clean thinking tags (qwen3)
                answer = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL).strip()
                answer = re.sub(r'<think>.*$', '', answer, flags=re.DOTALL).strip()
                answer = re.sub(r'</think>', '', answer).strip()

                result_box[0] = answer
            except Exception as e:
                error_box[0] = e

        t = threading.Thread(target=_call, daemon=True)
        t.start()
        t.join(timeout=self.LLM_TIMEOUT)

        if t.is_alive():
            print(f"[{self.AGENT_NAME}] LLM timed out after {self.LLM_TIMEOUT}s — skipping")
            return ""

        if error_box[0]:
            safe_err = str(error_box[0]).encode('ascii', errors='replace').decode()
            print(f"[{self.AGENT_NAME}] LLM error: {safe_err}")
            return ""

        return result_box[0]

    def process(self, request: str, **kwargs) -> dict:
        """
        Process a request. EVERY agent must implement this.
        
        Args:
            request: User's natural language request
            
        Returns:
            dict with:
                - success: bool
                - response: str (what to tell the user)
                - agent: str (agent name)
                - data: any (optional, agent-specific data)
        """
        raise NotImplementedError(f"{self.AGENT_NAME} must implement process()")

    def log(self, message: str):
        """Print a log message with agent name prefix."""
        safe_msg = str(message).encode('ascii', errors='replace').decode()
        print(f"[{self.AGENT_NAME}] {safe_msg}")
