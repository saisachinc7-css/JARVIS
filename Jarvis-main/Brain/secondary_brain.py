"""
Secondary Brain for JARVIS â€” Deep Thinker
Model: llama3.1:8b via Ollama

Activated ONLY when Primary Brain detects:
- Multi-step reasoning required
- Multi-agentic tasks
- Complex tool assignment
- Code generation
- Long planning or analysis

CONNECTIONS (mirrors Primary Brain):
    SecondaryBrain
    â”œâ”€â”€ IntentEngine      â€” Can classify intents itself
    â”œâ”€â”€ IntentRouter      â€” Can route to tools/agents/automations
    â”œâ”€â”€ ToolsProvider     â€” Universal tool access
    â”œâ”€â”€ Memory            â€” Recall + store
    â”œâ”€â”€ Agents/           â€” WhatsApp, Browser, RAG
    â”œâ”€â”€ Automations/      â€” Custom workflows, Webhooks
    â””â”€â”€ Laptop_Controls/  â€” System controls
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

from TextToSpeech.Fast_DF_TTS import speak
from shared_state import ui_jarvis_message


# ============================================================================
# SECONDARY BRAIN CONFIGURATION
# ============================================================================
MODEL = "deepseek-r1:8b"

SYSTEM_PROMPT = """You are JARVIS's Deep Thinker â€” the analytical mind behind a personal voice assistant.

You are activated ONLY for complex tasks that require careful reasoning:
- Multi-step problem solving and planning
- Multi-agentic task coordination (e.g., "search GitHub, save to Obsidian, and message CONTACT_NAME_THREE")
- Complex tool assignment when multiple tools are needed
- Code generation and debugging
- Comparative analysis (pros/cons)
- Long-form content creation

You have FULL ACCESS to all tools, agents, automations, and laptop controls.

PERSONALITY:
- Thorough but concise â€” explain clearly without being verbose
- Use "sir" occasionally and naturally
- Structure complex answers with clear steps
- For code: provide working, complete solutions
- For analysis: give clear conclusions, not just observations

OUTPUT RULES:
- Think through the problem carefully
- Execute tools/agents as needed to fulfill the request
- For spoken responses: keep to 2-3 sentences
- For code/detailed output: provide the full content
- NEVER state or claim "As an AI language model I don't have access to files or digital content". You are an autonomous AI operating system with direct access to local files, documents, PDFs, system controls, and tools.


KNOWLEDGE BASE:
- Accountpilot.in is an AI-native platform designed to automate bookkeeping, GST compliance, and profit analytics for businesses. The platform leverages AI and OCR technology to streamline financial management and provide actionable insights for growth-oriented users. Respond to questions about AccountPilot with this specific description.
"""


class SecondaryBrain:
    """
    Deep thinker brain using llama3.1:8b.
    Has ALL the same connections as PrimaryBrain.
    
    Handles:
    - Complex reasoning
    - Multi-agentic tasks
    - Multi-tool orchestration
    - Code generation
    - Deep planning
    """

    def __init__(self):
        self.model = MODEL
        self._available = None
        
        # Full connections â€” SAME as Primary Brain
        self._engine = None
        self._router = None
        self._tools = None
        self._memory = None
        self._agents = None
        self._automations = None
        self._controls = None

    # ===== CONNECTIONS (lazy-loaded) =====
    
    @property
    def engine(self):
        """IntentEngine â€” can classify intents."""
        if self._engine is None:
            from Brain.intent_engine import get_engine
            self._engine = get_engine()
        return self._engine

    @property
    def router(self):
        """IntentRouter â€” can route to tools, agents, automations, laptop."""
        if self._router is None:
            from Brain.intent_router import get_router
            self._router = get_router()
        return self._router

    @property
    def tools(self):
        """ToolsProvider â€” universal tool access."""
        if self._tools is None:
            from Brain.tools_provider import get_tools
            self._tools = get_tools()
        return self._tools

    @property
    def memory(self):
        """Memory Manager â€” recall + store."""
        if self._memory is None:
            try:
                from Brain.Memory.memory_manager import MemoryManager
                self._memory = MemoryManager()
            except Exception:
                pass
        return self._memory

    @property
    def agents(self):
        """Agents provider â€” routes to WhatsApp, Browser, RAG."""
        if self._agents is None:
            from Agents.agents_provider import get_agents
            self._agents = get_agents()
        return self._agents

    @property
    def automations(self):
        """Automations provider â€” routes to workflows, webhooks."""
        if self._automations is None:
            from Automations.automations_provider import get_automations
            self._automations = get_automations()
        return self._automations

    @property
    def controls(self):
        """Laptop controls provider â€” brightness, volume, WiFi, power."""
        if self._controls is None:
            from Laptop_Controls.controls_provider import get_controls
            self._controls = get_controls()
        return self._controls

    def is_available(self) -> bool:
        """Check if llama3.1:8b is available in Ollama."""
        if self._available is not None:
            return self._available

        if not OLLAMA_AVAILABLE:
            self._available = False
            return False

        try:
            response = ollama.generate(
                model=self.model,
                prompt="Say OK",
                options={"num_predict": 5}
            )
            self._available = True
            print(f"[SecondaryBrain] [OK] {self.model} available")
        except Exception as e:
            print(f"[SecondaryBrain] âœ— {self.model} not available: {e}")
            self._available = False

        return self._available

    def process(self, user_input: str, context: str = "") -> dict:
        """
        Process a complex request with deep reasoning.
        
        Has TWO modes:
        1. TOOL MODE: If the task needs tool execution, use IntentRouter
        2. THINK MODE: If purely reasoning, use llama3.1:8b directly
        
        Args:
            user_input: The user's request
            context: Optional memory context from Primary Brain
            
        Returns:
            Dict with status, response, and metadata
        """
        # First, try to use ToolsRegistry/IntentRouter for actionable tasks
        if self._is_actionable(user_input):
            print("[SecondaryBrain] â†’ Actionable task detected, using IntentRouter")
            try:
                result = self.router.process(user_input)
                if result.get("status") == "success":
                    return {**result, "model": self.model, "mode": "tool_execution"}
            except Exception as e:
                print(f"[SecondaryBrain] Router fallback: {e}")

        # Fall through to deep thinking mode
        return self._deep_think(user_input, context)

    def _is_actionable(self, user_input: str) -> bool:
        """Check if the input needs tool/agent execution vs pure reasoning."""
        action_signals = [
            "open", "play", "search", "send", "message", "whatsapp",
            "brightness", "volume", "wifi", "shutdown", "restart",
            "create", "check", "battery", "weather", "close",
        ]
        input_lower = user_input.lower()
        return any(signal in input_lower for signal in action_signals)

    def _deep_think(self, user_input: str, context: str = "") -> dict:
        """Pure reasoning with llama3.1:8b."""
        if not self.is_available():
            return {
                "status": "error",
                "error": f"{self.model} not available",
                "response": "I'm sorry sir, my deep thinking module isn't available right now."
            }

        try:
            # Check memory for additional context
            if self.memory and not context:
                try:
                    relevant = self.memory.recall(user_input)
                    if relevant:
                        context = f"[Memory: {relevant}]"
                except Exception:
                    pass

            # Build the full prompt
            prompt = SYSTEM_PROMPT + "\n\n"
            if context:
                prompt += f"CONTEXT FROM MEMORY:\n{context}\n\n"
            prompt += f"USER REQUEST:\n{user_input}\n\nYour response:"

            # Generate with llama3.1:8b
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                options={
                    "temperature": 0.6,
                    "num_predict": 1000,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1,
                }
            )

            answer = response.get("response", "").strip()
            if not answer:
                answer = "I couldn't generate a good answer for that, sir. Could you rephrase?"

            # Send to UI
            ui_jarvis_message(answer)

            # Speak a short version (first 2 sentences for TTS)
            tts_text = ". ".join(answer.split(". ")[:2]) + "."
            if len(tts_text) > 300:
                tts_text = tts_text[:297] + "..."
            
            import threading
            threading.Thread(target=speak, args=(tts_text,), daemon=True).start()

            # Store to memory if appropriate
            if self.memory:
                try:
                    from Brain.Memory.memory_classifier import MemoryClassifier
                    classifier = MemoryClassifier()
                    threading.Thread(
                        target=classifier.classify_and_store,
                        args=(user_input, {"response": answer}),
                        daemon=True
                    ).start()
                except Exception:
                    pass

            return {
                "status": "success",
                "intent": "DEEP_THINKING",
                "response": answer,
                "model": self.model,
                "mode": "deep_reasoning",
            }

        except Exception as e:
            error_msg = f"Deep thinking error: {e}"
            print(f"[SecondaryBrain] {error_msg}")
            return {
                "status": "error",
                "error": error_msg,
                "response": "I ran into an issue while thinking deeply about that, sir."
            }


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================
_secondary_brain = None


def get_secondary_brain() -> SecondaryBrain:
    """Get the global SecondaryBrain instance."""
    global _secondary_brain
    if _secondary_brain is None:
        _secondary_brain = SecondaryBrain()
    return _secondary_brain

