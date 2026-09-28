"""
Browser Agent — Standard Agent Implementation
Wraps Playwright MCP for browser automation.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Agents.base_agent import BaseAgent
from Agents.Browser_Agent import config


class BrowserAgent(BaseAgent):
    """Browser Agent — handles web navigation and automation."""

    AGENT_NAME = config.AGENT_NAME

    def _load_config(self):
        self.model = config.MODEL_NAME
        self.system_prompt = config.SYSTEM_PROMPT
        self.ollama_options = config.OLLAMA_OPTIONS.copy()

    def process(self, request: str, **kwargs) -> dict:
        """
        Process a browser request.
        Routes to Playwright MCP for execution.
        """
        self.log(f"Processing: {request}")
        input_lower = request.lower()

        try:
            if "navigate" in input_lower or "go to" in input_lower:
                url = request.split("to")[-1].strip()
                from Agents.Browser_Agent.playwright_mcp_client import browser_navigate_sync
                result = browser_navigate_sync(url)
                return {"success": True, "agent": self.AGENT_NAME, "response": f"Navigated to {url}", "data": result}

            elif "screenshot" in input_lower:
                from Agents.Browser_Agent.playwright_mcp_client import browser_screenshot_sync
                result = browser_screenshot_sync()
                return {"success": True, "agent": self.AGENT_NAME, "response": "Screenshot taken", "data": result}

            elif "click" in input_lower:
                element = request.split("click")[-1].strip()
                from Agents.Browser_Agent.playwright_mcp_client import browser_click_sync
                result = browser_click_sync(element=element)
                return {"success": True, "agent": self.AGENT_NAME, "response": f"Clicked on {element}", "data": result}

            # Use LLM to interpret complex browser requests
            interpretation = self.llm_generate(
                f"User wants a browser action: '{request}'. What URL or action should I perform? Reply with just the action."
            )
            return {
                "success": False,
                "agent": self.AGENT_NAME,
                "response": f"Browser action not clear. Interpreted as: {interpretation}",
            }
        except Exception as e:
            safe_err = str(e).encode('ascii', errors='replace').decode()
            self.log(f"Error: {safe_err}")
            return {"success": False, "agent": self.AGENT_NAME, "response": f"Browser error: {safe_err[:100]}"}


_agent = None

def get_browser_agent() -> BrowserAgent:
    global _agent
    if _agent is None:
        _agent = BrowserAgent()
    return _agent
