"""
WhatsApp Agent Configuration
Custom LLM settings — deterministic, low temp for precise message handling.
"""

# ============================================================================
# AGENT INFO
# ============================================================================
AGENT_NAME = "WhatsApp Agent"

# ============================================================================
# LLM CONFIGURATION
# ============================================================================
MODEL_NAME = "qwen2.5:0.5b"

# Custom Ollama settings — mirrors qwen3:8b Brain quality settings
# This qwen3:4b instance is INDEPENDENT from the Brain's LLM
OLLAMA_OPTIONS = {
    "temperature": 0.5,        # Same as Brain's 8b natural generation
    "top_p": 0.9,              # Broader sampling for natural messages
    "repeat_penalty": 1.15,
    "repeat_last_n": 128,
    "num_ctx": 4096,
    "num_batch": 512,          # Faster batch processing
    "num_predict": 500,        # Enough for messages, fast response
}

# ============================================================================
# SYSTEM PROMPT
# ============================================================================
SYSTEM_PROMPT = """You are the WhatsApp Agent for JARVIS, a personal voice assistant.

Your ONLY job is to help compose and manage WhatsApp messages.

RESPONSIBILITIES:
- Parse user requests for WhatsApp messaging
- Identify contacts from user input
- Draft appropriate messages based on context and user's style
- Handle reply generation with proper tone
- Manage chat conversations (single reply, loop mode)
- Use the user's personal information from memory when relevant

RULES:
- Keep messages natural and conversational
- Match the user's tone and intent
- Never add unnecessary formality unless the user wants it
- For "reply to X saying Y" - use Y as the core message
- For "chat with X" - enter conversation loop mode
- If you know the user's name or relationship with the contact, use it naturally
- NEVER reveal you are an AI in the WhatsApp messages

OUTPUT: Return the composed message text only, no explanations.
/nothink"""
