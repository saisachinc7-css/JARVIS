"""
Universal Tools Provider for JARVIS
Central access point for ALL tools — used by both Primary and Secondary Brain.

This module exposes tools universally so that Agents, Automations, and
Laptop Controls can all access tools through either brain.

Architecture:
    Primary Brain ──┐
                    ├── ToolsProvider ──► Tools/ (weather, MCP, create_file, etc.)
    Secondary Brain ┘                ──► Tools/Simple_Automations/
                                     ──► Tools/MCP/
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ToolsProvider:
    """
    Universal tools provider accessible by both brains and all subsystems.
    
    Any agent, automation, or laptop control module can call:
        from Brain.tools_provider import get_tools
        tools = get_tools()
        tools.weather("Hyderabad")
        tools.simple_automations.open_app("chrome")
    """

    def __init__(self):
        self._weather = None
        self._mcp = None
        self._simple_automations = None
        self._create_file = None
        self._obsidian = None

    # ===== WEATHER =====
    def weather(self, location: str = "Singapore") -> str:
        """Get weather for a location."""
        from Tools.weather import get_weather_by_address
        return get_weather_by_address(location)

    # ===== MCP TOOLS =====
    def web_search(self, query: str) -> str:
        """Search the web via DuckDuckGo MCP."""
        from Tools.MCP.mcp_client import search_web_sync
        return search_web_sync(query)

    def github_search(self, query: str) -> str:
        """Search GitHub repositories."""
        from Tools.MCP.mcp_manager import search_github_sync
        return search_github_sync(query)

    def obsidian_search(self, query: str) -> str:
        """Search Obsidian notes."""
        from Tools.MCP.mcp_client import search_obsidian_sync
        return search_obsidian_sync(query)

    # ===== FILE TOOLS =====
    def create_file(self, command: str):
        """Create a new file."""
        from Tools.create_file import create_file
        return create_file(command)

    def create_obsidian_note(self, title: str, content: str = ""):
        """Create an Obsidian note."""
        from Tools.obsidian_integration import search_and_save_sync
        return search_and_save_sync(title)

    # ===== SIMPLE AUTOMATIONS (direct access) =====
    def open_app(self, app_name: str):
        """Open a desktop app."""
        from Tools.Simple_Automations.App_open import open_App
        return open_App(app_name)

    def open_web(self, site_name: str):
        """Open a website."""
        from Tools.Simple_Automations.Web_open import open_web
        return open_web(site_name)

    def play_spotify(self, query: str):
        """Play music on Spotify."""
        from Tools.Simple_Automations.Play_Music_spotify import play_music_on_spotify
        return play_music_on_spotify(query)

    def play_youtube(self, query: str):
        """Play music/video on YouTube."""
        from Tools.Simple_Automations.Play_Music_YT import play_music_on_youtube
        return play_music_on_youtube(query)

    def check_battery(self):
        """Check battery percentage."""
        from Tools.Simple_Automations.battery import check_percentage
        return check_percentage()

    def active_window(self):
        """Get current active window info."""
        from Tools.Simple_Automations.active_window import get_active_window_info
        return get_active_window_info()

    def is_browser_active(self) -> bool:
        """Check if browser is the active window."""
        from Tools.Simple_Automations.active_window import is_browser_active
        return is_browser_active()

    # ===== AGENTS (direct access) =====
    def whatsapp_send(self, contact: str, message: str):
        """Send a WhatsApp message."""
        from Agents.WhatsApp_Agent.whatsapp_skill import handle_whatsapp_command
        return handle_whatsapp_command(f"send {message} to {contact}")

    def browser_navigate(self, url: str):
        """Navigate browser to URL."""
        from Agents.Browser_Agent.playwright_mcp_client import browser_navigate_sync
        return browser_navigate_sync(url)

    # ===== LAPTOP CONTROLS (direct access) =====
    def laptop_control(self, action: str, **kwargs):
        """Execute a laptop control action."""
        from Laptop_Controls.controller import LaptopController
        controller = LaptopController()
        return controller.execute(action, **kwargs)


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================
_tools_provider = None


def get_tools() -> ToolsProvider:
    """Get the global ToolsProvider instance — accessible from anywhere."""
    global _tools_provider
    if _tools_provider is None:
        _tools_provider = ToolsProvider()
    return _tools_provider
