"""
Browser Agent Configuration
Custom LLM settings for web navigation and browser automation.
"""

# ============================================================================
# AGENT INFO
# ============================================================================
AGENT_NAME = "Browser Agent"

# ============================================================================
# LLM CONFIGURATION
# ============================================================================
MODEL_NAME = "qwen3:4b"

OLLAMA_OPTIONS = {
    "temperature": 0.15,
    "top_p": 0.85,
    "repeat_penalty": 1.15,
    "repeat_last_n": 128,
    "num_ctx": 4096,
    "num_batch": 256,
    "seed": 42,
    "num_predict": 1500,
}

# ============================================================================
# SYSTEM PROMPT
# ============================================================================
SYSTEM_PROMPT = """You are the Browser Agent for JARVIS, a personal voice assistant.

Your ONLY job is to help automate browser interactions using Playwright.

RESPONSIBILITIES:
- Navigate to URLs
- Click elements on web pages
- Type text into input fields
- Take screenshots of pages
- Extract text/data from web pages
- Handle multi-step browser workflows

RULES:
- Always use the most reliable CSS selectors
- Wait for page loads before interacting
- Handle popups and cookie banners gracefully
- Report errors clearly if an element is not found
- Never expose sensitive data like passwords

OUTPUT: Return action results or extracted data.
/nothink"""
