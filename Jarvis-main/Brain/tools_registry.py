"""
Tools Registry for JARVIS Voice Assistant.
Maps intent types to executable tool functions with validation.
"""

import sys
import os
from typing import Dict, Any, Callable, Optional, List, Union
from dataclasses import dataclass, field

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class ToolDefinition:
    """Definition of a tool that can be executed."""
    name: str
    description: str
    handler: Optional[Callable] = None
    required_params: List[str] = field(default_factory=list)
    optional_params: List[str] = field(default_factory=list)


class ToolsRegistry:
    """
    Registry of all available tools.
    Maps tool names to their definitions and handlers.
    """
    
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._register_all_tools()
    
    def _register_all_tools(self):
        """Register all available tools from the Automation module."""
        
        # Import handlers lazily to avoid circular imports
        from Tools.Simple_Automations.Play_Music_spotify import play_music_on_spotify
        from Tools.Simple_Automations.Play_Music_YT import play_music_on_youtube
        from Tools.Simple_Automations.App_open import open_App
        from Tools.Simple_Automations.Web_open import open_web
        from Tools.weather import get_weather_by_address
        from Tools.create_file import create_file
        from TextToSpeech.Fast_DF_TTS import speak
        
        # MOOD TO SONG MAPPING - When LLM sends mood instead of title
        MOOD_SONGS = {
            "bored": ("Uptown Funk", "Bruno Mars"),
            "sad": ("Here Comes The Sun", "The Beatles"),
            "depressed": ("Three Little Birds", "Bob Marley"),
            "excited": ("Can't Stop The Feeling", "Justin Timberlake"),
            "stressed": ("Weightless", "Marconi Union"),
            "happy": ("Happy", "Pharrell Williams"),
            "lonely": ("You've Got A Friend", "Carole King"),
            "moody": ("Three Little Birds", "Bob Marley"),
            "tired": ("Wake Me Up", "Avicii"),
            "anxious": ("Breathe", "Télépopmusik"),
            "angry": ("Eye of the Tiger", "Survivor"),
            "relaxed": ("Sunset Lover", "Petit Biscuit"),
        }
        
        def play_spotify_with_mood_fallback(params):
            title = params.get("title", "")
            mood = params.get("mood", "")
            
            # If no title but we have a mood, pick a song
            if not title and mood:
                mood_lower = mood.lower()
                for mood_key, (song_title, artist) in MOOD_SONGS.items():
                    if mood_key in mood_lower:
                        print(f"[Tools] Mood '{mood}' mapped to song: {song_title} by {artist}")
                        return play_music_on_spotify(f"{song_title} {artist}")
                # Default fallback for unknown moods
                print(f"[Tools] Unknown mood '{mood}', playing default feel-good song")
                return play_music_on_spotify("Three Little Birds Bob Marley")
            
            # Normal case: we have a title
            if title:
                artist = params.get("artist", "")
                search_query = f"{title} {artist}".strip() if artist else title
                return play_music_on_spotify(search_query)
            
            # No title and no mood - shouldn't happen but fallback
            print("[Tools] No title or mood provided, playing default song")
            return play_music_on_spotify("Happy Pharrell Williams")
        
        # Play Music - Spotify (with mood fallback)
        self.register(ToolDefinition(
            name="play_music_spotify",
            description="Play a song on Spotify",
            handler=play_spotify_with_mood_fallback,
            required_params=[],  # No required - we handle missing title via mood
            optional_params=["title", "artist", "mood"]
        ))
        
        # Play Music - YouTube
        self.register(ToolDefinition(
            name="play_music_youtube",
            description="Play a song/video on YouTube",
            handler=lambda params: play_music_on_youtube(params.get("query", "")),
            required_params=["query"]
        ))
        
        # Open App
        self.register(ToolDefinition(
            name="open_app",
            description="Open a desktop application",
            handler=lambda params: self._handle_open_app(params, open_App),
            required_params=["app_name"]
        ))
        
        # Open Web
        self.register(ToolDefinition(
            name="open_web",
            description="Open a website, optionally with search query",
            handler=lambda params: self._handle_open_web(params, open_web),
            required_params=["site_name"],
            optional_params=["search_query"]
        ))
        
        # Close Window
        self.register(ToolDefinition(
            name="close_window",
            description="Close the current active window",
            handler=lambda params: self._close_window(),
            required_params=[]
        ))
        
        # Close App (terminate specific application by name)
        self.register(ToolDefinition(
            name="close_app",
            description="Close/terminate a specific application by name",
            handler=lambda params: self._handle_close_app(params),
            required_params=["app_name"]
        ))
        
        # Volume Control
        self.register(ToolDefinition(
            name="volume_control",
            description="Control system volume",
            handler=lambda params: self._handle_volume(params),
            required_params=["action"],
            optional_params=["level"]
        ))
        
        # System Screenshot
        self.register(ToolDefinition(
            name="system_screenshot",
            description="Take a system-level screenshot of the primary monitor",
            handler=lambda params: self._handle_system_screenshot(params),
            required_params=[]
        ))
        
        # Weather
        self.register(ToolDefinition(
            name="get_weather",
            description="Get weather information for a location",
            handler=lambda params: self._handle_weather(params, get_weather_by_address, speak),
            optional_params=["location"]
        ))
        
        # Create File
        self.register(ToolDefinition(
            name="create_file",
            description="Create a new file",
            handler=lambda params: create_file(f"create {params.get('file_type', 'text')} file named {params.get('filename', 'demo')}"),
            required_params=["filename"],
            optional_params=["file_type"]
        ))
        
        # WhatsApp (placeholder - uses existing skill)
        self.register(ToolDefinition(
            name="send_whatsapp",
            description="Send a WhatsApp message",
            handler=lambda params: self._handle_whatsapp(params),
            required_params=["contact", "message"]
        ))
        
        # Answer Query (returns response for TTS)
        self.register(ToolDefinition(
            name="answer_query",
            description="Answer a general question",
            handler=lambda params: params,  # Just pass through, response is in the intent
            optional_params=["query"]
        ))
        
        # Research via ChatGPT - opens ChatGPT and pastes improved query
        self.register(ToolDefinition(
            name="research_chatgpt",
            description="Research a topic using ChatGPT - opens ChatGPT and pastes query",
            handler=lambda params: self._handle_research_chatgpt(params),
            required_params=["improved_query"],
            optional_params=["original_query"]
        ))
        
        # Find/Search via Claude Desktop - pastes query as-is (no enhancement)
        self.register(ToolDefinition(
            name="find_claude",
            description="Find/search information using Claude Desktop - pastes your query as-is",
            handler=lambda params: self._handle_find_claude(params),
            required_params=["original_query"],
            optional_params=[]
        ))
        
        # Create Obsidian Note
        self.register(ToolDefinition(
            name="create_obsidian_note",
            description="Create or update an Obsidian note",
            handler=lambda params: self._handle_obsidian_note(params),
            required_params=["title"],
            optional_params=["content"]
        ))
        
        # WhatsApp Chat Bot (read + reply)
        self.register(ToolDefinition(
            name="whatsapp_chat",
            description="Chat/reply on WhatsApp with LLM-generated responses",
            handler=lambda params: self._handle_whatsapp_chat(params),
            required_params=["contact"],
            optional_params=["mode", "topic"]
        ))
        
        # Stop Chat Session
        self.register(ToolDefinition(
            name="stop_chat",
            description="Stop the current WhatsApp chat session",
            handler=lambda params: self._handle_stop_chat(),
            required_params=[]
        ))
        
        # ===== GOOGLE WORKSPACE TOOLS =====
        
        # Gmail: Check Unread
        self.register(ToolDefinition(
            name="gmail_check_unread",
            description="Check unread Gmail emails",
            handler=lambda params: self._handle_gmail_unread(params),
            optional_params=["limit"]
        ))
        
        # Gmail: Summarize Inbox
        self.register(ToolDefinition(
            name="gmail_summarize",
            description="Summarize Gmail inbox for a period",
            handler=lambda params: self._handle_gmail_summarize(params),
            optional_params=["period"]
        ))
        
        # Gmail: Search
        self.register(ToolDefinition(
            name="gmail_search",
            description="Search Gmail by sender, subject, or keyword",
            handler=lambda params: self._handle_gmail_search(params),
            optional_params=["from", "subject", "keyword", "query"]
        ))
        
        # Gmail: Send Email
        self.register(ToolDefinition(
            name="gmail_send",
            description="Send an email via Gmail",
            handler=lambda params: self._handle_gmail_send(params),
            required_params=["to", "subject", "body"],
            optional_params=["cc", "bcc"]
        ))
        
        # Calendar: Today's Agenda
        self.register(ToolDefinition(
            name="calendar_today",
            description="Get today's calendar agenda",
            handler=lambda params: self._handle_calendar_today(params),
            required_params=[]
        ))
        
        # Calendar: Create Event
        self.register(ToolDefinition(
            name="calendar_create_event",
            description="Create a new Google Calendar event",
            handler=lambda params: self._handle_calendar_create_event(params),
            required_params=["title", "start_time", "end_time"],
            optional_params=["description", "location", "attendees"]
        ))
        
        # Drive: List Files
        self.register(ToolDefinition(
            name="drive_list",
            description="List Google Drive files",
            handler=lambda params: self._handle_drive_list(params),
            optional_params=["file_type", "query"]
        ))
        
        # Drive: Create Document
        self.register(ToolDefinition(
            name="drive_create_doc",
            description="Create a new Google Doc",
            handler=lambda params: self._handle_drive_create_doc(params),
            required_params=["title"],
            optional_params=["content"]
        ))
        
        # Sheets: Append Row (for expense tracking etc.)
        self.register(ToolDefinition(
            name="sheets_log",
            description="Log/append data to a Google Sheet",
            handler=lambda params: self._handle_sheets_log(params),
            required_params=["spreadsheet_id", "values"],
            optional_params=["sheet_name"]
        ))
        
        # ===== MCP TOOLS (Autonomous Selection) =====
        
        # DuckDuckGo Web Search - for real-time info, current news, etc.
        self.register(ToolDefinition(
            name="mcp_web_search",
            description="Search the web for real-time information using DuckDuckGo",
            handler=lambda params: self._handle_mcp_web_search(params),
            required_params=["query"]
        ))
        
        # GitHub Repository Search
        self.register(ToolDefinition(
            name="mcp_github_search",
            description="Search GitHub repositories",
            handler=lambda params: self._handle_mcp_github_search(params),
            required_params=["query"]
        ))
        
        # Image Search via Browser (Playwright MCP)
        self.register(ToolDefinition(
            name="mcp_image_search",
            description="Search for images on the web",
            handler=lambda params: self._handle_mcp_image_search(params),
            required_params=["query"]
        ))
        
        # Fetch URL Content
        self.register(ToolDefinition(
            name="mcp_fetch_url",
            description="Fetch content from a URL",
            handler=lambda params: self._handle_mcp_fetch_url(params),
            required_params=["url"]
        ))
        
        # ===== PLAYWRIGHT BROWSER AUTOMATION TOOLS =====
        
        # Browser Navigation
        self.register(ToolDefinition(
            name="browser_navigate",
            description="Navigate browser to a URL",
            handler=lambda params: self._handle_browser_navigate(params),
            required_params=["url"]
        ))
        
        self.register(ToolDefinition(
            name="browser_navigate_back",
            description="Go back in browser history",
            handler=lambda params: self._handle_browser_navigate_back(params)
        ))
        
        self.register(ToolDefinition(
            name="browser_navigate_forward",
            description="Go forward in browser history",
            handler=lambda params: self._handle_browser_navigate_forward(params)
        ))
        
        self.register(ToolDefinition(
            name="browser_close",
            description="Close the current browser page",
            handler=lambda params: self._handle_browser_close(params)
        ))
        
        # Page Inspection
        self.register(ToolDefinition(
            name="browser_snapshot",
            description="Get accessibility tree snapshot of current page for AI understanding",
            handler=lambda params: self._handle_browser_snapshot(params)
        ))
        
        self.register(ToolDefinition(
            name="browser_screenshot",
            description="Take a visual screenshot of the page",
            handler=lambda params: self._handle_browser_screenshot(params),
            optional_params=["path", "full_page"]
        ))
        
        # User Interactions
        self.register(ToolDefinition(
            name="browser_click",
            description="Click an element on the page",
            handler=lambda params: self._handle_browser_click(params),
            required_params=["element"],
            optional_params=["ref"]
        ))
        
        self.register(ToolDefinition(
            name="browser_hover",
            description="Hover over an element on the page",
            handler=lambda params: self._handle_browser_hover(params),
            required_params=["ref"]
        ))
        
        self.register(ToolDefinition(
            name="browser_type",
            description="Type text into an input field",
            handler=lambda params: self._handle_browser_type(params),
            required_params=["ref", "text"]
        ))
        
        self.register(ToolDefinition(
            name="browser_press_key",
            description="Press a keyboard key",
            handler=lambda params: self._handle_browser_press_key(params),
            required_params=["key"]
        ))
        
        self.register(ToolDefinition(
            name="browser_fill_form",
            description="Fill multiple form fields at once",
            handler=lambda params: self._handle_browser_fill_form(params),
            required_params=["fields"]
        ))
        
        self.register(ToolDefinition(
            name="browser_select_option",
            description="Select an option from a dropdown",
            handler=lambda params: self._handle_browser_select_option(params),
            required_params=["ref", "value"]
        ))
        
        # Dialog & JavaScript
        self.register(ToolDefinition(
            name="browser_handle_dialog",
            description="Handle browser dialogs (alert, confirm, prompt)",
            handler=lambda params: self._handle_browser_dialog(params),
            required_params=["accept"],
            optional_params=["text"]
        ))
        
        self.register(ToolDefinition(
            name="browser_evaluate",
            description="Execute custom JavaScript on the page",
            handler=lambda params: self._handle_browser_evaluate(params),
            required_params=["code"]
        ))
        
        # Tab Management
        self.register(ToolDefinition(
            name="browser_tabs",
            description="Manage browser tabs (list, create, switch, close)",
            handler=lambda params: self._handle_browser_tabs(params),
            required_params=["action"],
            optional_params=["index", "url"]
        ))
        
        # Window Control
        self.register(ToolDefinition(
            name="browser_resize",
            description="Resize browser window",
            handler=lambda params: self._handle_browser_resize(params),
            required_params=["width", "height"]
        ))
        
        self.register(ToolDefinition(
            name="browser_wait_for",
            description="Wait for a specific element or condition",
            handler=lambda params: self._handle_browser_wait_for(params),
            required_params=["selector"],
            optional_params=["timeout", "state"]
        ))

    def _handle_open_app(self, params: Dict, open_func: Callable):
        """Handle opening single or multiple apps."""
        app_name = params.get("app_name", "")
        if isinstance(app_name, list):
            for app in app_name:
                open_func(app)
        else:
            open_func(app_name)
    
    def _handle_open_web(self, params: Dict, open_func: Callable):
        """Handle opening websites with optional search."""
        import pyautogui as gui
        import time
        import webbrowser
        from Tools.Simple_Automations.active_window import get_active_window_info
        
        site = params.get("site_name", "")
        search_query = params.get("search_query")
        
        # If there's a search query, try direct URL navigation first for reliability
        if search_query:
            search_query_encoded = search_query.replace(" ", "+")
            if site.lower() == "youtube":
                webbrowser.open(f"https://www.youtube.com/results?search_query={search_query_encoded}")
                print(f"[ToolsRegistry] Direct URL YouTube search opened: '{search_query}'")
                return
            elif site.lower() == "google":
                webbrowser.open(f"https://www.google.com/search?q={search_query_encoded}")
                print(f"[ToolsRegistry] Direct URL Google search opened: '{search_query}'")
                return
        
        # Open the website normally
        open_func(site)
        
        # Fallback if other sites use search query
        if search_query:
            # Wait for browser/site to load
            time.sleep(2)
            gui.hotkey("ctrl", "l")  # Focus address bar
            time.sleep(0.2)
            gui.write(search_query, interval=0.03)
            gui.press("enter")
    
    def _close_window(self):
        """Close the current active window."""
        import pyautogui as gui
        gui.hotkey("alt", "F4")
        print("Closing current window...")
    
    def _handle_close_app(self, params: Dict):
        """Close/terminate a specific application by name."""
        import psutil
        from TextToSpeech.Fast_DF_TTS import speak
        import threading
        
        app_name = params.get("app_name", "").lower()
        
        # Map common app names to their process names
        app_process_map = {
            "spotify": "spotify.exe",
            "chrome": "chrome.exe",
            "firefox": "firefox.exe",
            "edge": "msedge.exe",
            "code": "Code.exe",
            "vscode": "Code.exe",
            "vs code": "Code.exe",
            "visual studio code": "Code.exe",
            "notepad": "notepad.exe",
            "word": "WINWORD.EXE",
            "excel": "EXCEL.EXE",
            "discord": "Discord.exe",
            "telegram": "Telegram.exe",
            "whatsapp": "WhatsApp.exe",
            "brave": "brave.exe",
            "vlc": "vlc.exe",
        }
        
        # Get the process name to look for
        process_name = app_process_map.get(app_name)
        if not process_name:
            # Try to guess the process name
            process_name = f"{app_name}.exe"
        
        # Find and terminate the process
        found = False
        terminated = False
        
        try:
            for proc in psutil.process_iter(['name', 'pid']):
                try:
                    proc_name = proc.info['name']
                    if proc_name and proc_name.lower() == process_name.lower():
                        found = True
                        proc.terminate()  # Graceful termination
                        print(f"[JARVIS] Terminated {proc_name} (PID: {proc.info['pid']})")
                        terminated = True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            if terminated:
                msg = f"{app_name.title()} has been closed"
                print(f"[JARVIS] {msg}")
                threading.Thread(target=speak, args=(msg,), daemon=True).start()
                return {"success": True, "app": app_name, "message": msg}
            elif not found:
                msg = f"{app_name.title()} is not running"
                print(f"[JARVIS] {msg}")
                threading.Thread(target=speak, args=(msg,), daemon=True).start()
                return {"success": False, "app": app_name, "message": msg}
            else:
                msg = f"Could not close {app_name.title()}"
                threading.Thread(target=speak, args=(msg,), daemon=True).start()
                return {"success": False, "app": app_name, "message": msg}
                
        except Exception as e:
            msg = f"Error closing {app_name}: {str(e)}"
            print(f"[JARVIS] {msg}")
            threading.Thread(target=speak, args=("Sorry, I couldn't close that app.",), daemon=True).start()
            return {"success": False, "error": str(e)}
    
    def _handle_volume(self, params: Dict):
        """Handle volume control actions."""
        import pyautogui as gui
        
        action = params.get("action", "").lower()
        level = params.get("level")
        
        if action == "up":
            for _ in range(level or 5):
                gui.press("volumeup")
        elif action == "down":
            for _ in range(level or 5):
                gui.press("volumedown")
        elif action == "mute":
            gui.press("volumemute")
        elif action == "unmute":
            gui.press("volumemute")
        
        print(f"Volume: {action}")
        
    def _handle_system_screenshot(self, params: Dict) -> str:
        """Handle system-level screenshot."""
        from Laptop_Controls.controller import get_laptop_controller
        lc = get_laptop_controller()
        res = lc.execute("screenshot")
        return res.get("message", "Screenshot command executed")
    
    def _handle_weather(self, params: Dict, weather_func: Callable, speak_func: Callable):
        """Handle weather queries with TTS response."""
        import threading
        
        location = params.get("location") or "Singapore"
        report = weather_func(location)
        
        if report and "Error" not in report and "Could not" not in report:
            lines = report.split('\n')
            summary = f"{lines[0]}. {lines[1]}. {lines[2]}."
            print(f"[JARVIS] Weather Data: {summary}")
            return report
        else:
            return "Sorry, I couldn't get the weather information."
    
    def _handle_research_chatgpt(self, params: Dict):
        """Open ChatGPT and paste the improved research query."""
        import pyautogui as gui
        import time
        import webbrowser
        import pyperclip
        from TextToSpeech.Fast_DF_TTS import speak
        import threading
        
        # Get the improved query (or original if improved not available)
        query = params.get("improved_query") or params.get("original_query", "")
        
        if not query:
            threading.Thread(target=speak, args=("I didn't catch what you want to research.",), daemon=True).start()
            return {"success": False, "error": "No query provided"}
        
        print(f"[JARVIS] Opening ChatGPT for research: {query[:50]}...")
        
        # Speak confirmation
        threading.Thread(target=speak, args=("Opening ChatGPT for research.",), daemon=True).start()
        
        try:
            # Open ChatGPT in browser
            webbrowser.open("https://chatgpt.com")
            
            # Wait for page to load
            time.sleep(3)
            
            # Copy the improved query to clipboard
            pyperclip.copy(query)
            
            # Select all and clear existing text (to prevent accumulation)
            gui.hotkey("ctrl", "a")
            time.sleep(0.1)
            gui.press("backspace")
            time.sleep(0.1)
            
            # Paste it (Ctrl+V)
            gui.hotkey("ctrl", "v")
            
            print(f"[JARVIS] Pasted research query: {query}")
            
            return {"success": True, "query": query}
            
        except Exception as e:
            print(f"[JARVIS] Research error: {e}")
            threading.Thread(target=speak, args=("Sorry, I couldn't open ChatGPT.",), daemon=True).start()
            return {"success": False, "error": str(e)}
    
    def _handle_find_claude(self, params: Dict):
        """Open Claude Desktop and paste the query as-is (no enhancement)."""
        import pyautogui as gui
        import time
        import webbrowser
        import pyperclip
        from TextToSpeech.Fast_DF_TTS import speak
        import threading
        
        # Get the original query (no enhancement)
        query = params.get("original_query", "")
        
        if not query:
            threading.Thread(target=speak, args=("I didn't catch what you want to find.",), daemon=True).start()
            return {"success": False, "error": "No query provided"}
        
        print(f"[JARVIS] Opening Claude Desktop to find: {query}")
        
        # Speak confirmation
        threading.Thread(target=speak, args=("Opening Claude to find that.",), daemon=True).start()
        
        try:
            # Copy the improved query to clipboard first
            pyperclip.copy(query)
            print(f"[JARVIS] Copied query to clipboard: {query}")
            
            # Open Claude Desktop using URL protocol
            webbrowser.open("claude://")
            print("[JARVIS] Opened Claude Desktop")
            
            # Wait for Claude to fully load
            time.sleep(4)
            
            # Use Ctrl+N to create new chat (this focuses the input field automatically)
            print("[JARVIS] Creating new chat (Ctrl+N)...")
            gui.hotkey("ctrl", "n")
            time.sleep(1.5)  # Wait for new chat to be ready
            
            # Clear any existing text in the input (in case there's template text)
            print("[JARVIS] Clearing chat box...")
            gui.hotkey("ctrl", "a")
            time.sleep(0.2)
            gui.press("backspace")
            time.sleep(0.3)
            
            # Now paste the query - input should be focused and clear
            print("[JARVIS] Pasting query...")
            gui.hotkey("ctrl", "v")
            time.sleep(0.5)
            
            print(f"[JARVIS] [OK] Successfully pasted query to Claude")
            
            return {"success": True, "query": query}
            
        except Exception as e:
            print(f"[JARVIS] Claude error: {e}")
            import traceback
            traceback.print_exc()
            threading.Thread(target=speak, args=("Sorry, I couldn't open Claude Desktop.",), daemon=True).start()
            return {"success": False, "error": str(e)}
    
    def _handle_whatsapp(self, params: Dict):
        """Handle WhatsApp commands by directly using parsed contact/message."""
        from Agents.WhatsApp_Agent.contact_manager import ContactManager
        from Agents.WhatsApp_Agent.wa_web_automator import WhatsAppWebAutomator
        from TextToSpeech.Fast_DF_TTS import speak
        from Brain.intent_engine import get_engine
        import threading
        
        contact_query = params.get("contact", "")
        message = params.get("message", "")
        
        # Check for special message generation flags
        if message == "__GENERATE__":
            # Generate LLM answer for the query
            query = params.get("query", "")
            if query:
                print(f"[WhatsApp] Generating answer for: '{query}'")
                threading.Thread(target=speak, args=(f"Generating answer about {query}",), daemon=True).start()
                
                engine = get_engine()
                message = engine.generate_answer(query)
                print(f"[WhatsApp] Generated: {message[:100]}...")
                
                # Also speak the generated answer
                threading.Thread(target=speak, args=(message,), daemon=True).start()
            else:
                message = "No query provided"
        
        elif message == "__WEATHER__":
            # Get weather info
            from Tools.weather import get_weather_by_address
            location = params.get("location") or "Singapore"
            print(f"[WhatsApp] Getting weather for: {location}")
            
            weather_report = get_weather_by_address(location)
            if weather_report and "Error" not in weather_report:
                message = weather_report
            else:
                message = f"Couldn't get weather for {location}"
        
        print(f"[WhatsApp] Contact: '{contact_query}', Message: '{message[:50]}...'")
        
        
        # Resolve contact
        contact_manager = ContactManager()
        contact_result = contact_manager.resolve(contact_query)
        
        if not contact_result.get("found"):
            error_msg = f"Contact '{contact_query}' not found"
            print(f"[WhatsApp] {error_msg}")
            threading.Thread(target=speak, args=(error_msg,), daemon=True).start()
            return {"success": False, "error": error_msg}
        
        contact = contact_result["contact"]
        phone = contact["phone"]
        contact_name = contact["name"]
        
        print(f"[WhatsApp] Resolved to: {contact_name} ({phone})")
        
        # Speak confirmation
        threading.Thread(target=speak, args=(f"Preparing message for {contact_name}",), daemon=True).start()
        
        # Open WhatsApp and draft the message
        try:
            automator = WhatsAppWebAutomator(headless=False)
            result = automator.draft_message(phone, message)
            
            if result.get("success"):
                print(f"[WhatsApp] [OK] Message drafted for {contact_name}")
                threading.Thread(target=speak, args=(f"Message ready for {contact_name}. Please review and send manually.",), daemon=True).start()
                return {"success": True, "contact": contact_name, "message": message}
            else:
                error_msg = result.get("error", "Failed to draft message")
                print(f"[WhatsApp] ✗ {error_msg}")
                threading.Thread(target=speak, args=(f"Sorry, couldn't prepare the message. {error_msg}",), daemon=True).start()
                return {"success": False, "error": error_msg}
                
        except Exception as e:
            error_msg = str(e)
            print(f"[WhatsApp] ✗ Error: {error_msg}")
            threading.Thread(target=speak, args=("Sorry, WhatsApp automation failed.",), daemon=True).start()
            return {"success": False, "error": error_msg}
    
    def _handle_obsidian_note(self, params: Dict):
        """Create an Obsidian note."""
        from Brain.tools.create_obsidian_note import create_obsidian_note
        from TextToSpeech.Fast_DF_TTS import speak
        import threading
        
        title = params.get("title", "Untitled Note")
        content = params.get("content", "")
        
        try:
            result = create_obsidian_note(title, content)
            print(f"[JARVIS] {result}")
            threading.Thread(target=speak, args=(f"Note created: {title}",), daemon=True).start()
            return {"success": True, "note": title, "path": result}
        except Exception as e:
            error_msg = f"Failed to create note: {str(e)}"
            print(f"[JARVIS] {error_msg}")
            threading.Thread(target=speak, args=("Sorry, couldn't create the note.",), daemon=True).start()
            return {"success": False, "error": error_msg}
    
    def _handle_whatsapp_chat(self, params: Dict):
        """Handle WhatsApp chat/reply commands."""
        from Agents.WhatsApp_Agent.wa_chat_bot import get_chat_bot, ChatMode
        from TextToSpeech.Fast_DF_TTS import speak
        import threading
        
        contact = params.get("contact", "")
        mode = params.get("mode", "single")  # draft, single, or loop
        topic = params.get("topic")
        user_context = params.get("user_context")  # User's situation/intent
        
        # Auto-upgrade to LOOP when user provides context/topic — they want a conversation
        if (user_context or topic) and mode == "single":
            print(f"[ChatBot] Context/topic provided — upgrading single -> loop for ongoing chat")
            mode = "loop"
        
        print(f"[ChatBot] Starting {mode} chat with {contact}")
        if topic:
            print(f"[ChatBot] Topic: {topic}")
        if user_context:
            print(f"[ChatBot] Context: {user_context}")
        
        try:
            # Get chat bot and set context
            bot = get_chat_bot()
            # Use user_context if available, otherwise use topic as the guiding context
            bot.user_context = user_context or topic  # CRITICAL: topic has the user's instruction
            
            # Map mode string to enum
            mode_map = {
                "draft": ChatMode.DRAFT,
                "single": ChatMode.SINGLE,
                "loop": ChatMode.LOOP,
                "manual": ChatMode.DRAFT,
                "auto": ChatMode.LOOP
            }
            chat_mode = mode_map.get(mode.lower(), ChatMode.SINGLE)
            
            result = bot.chat_session(contact, chat_mode, topic)
            return result
        except Exception as e:
            error_msg = str(e)
            print(f"[ChatBot] Error: {error_msg}")
            threading.Thread(target=speak, args=("Sorry, chat automation failed.",), daemon=True).start()
            return {"success": False, "error": error_msg}
    
    def _handle_stop_chat(self):
        """Stop the current WhatsApp chat session."""
        from Agents.WhatsApp_Agent.wa_chat_bot import stop_chat
        from TextToSpeech.Fast_DF_TTS import speak
        import threading
        
        result = stop_chat()
        threading.Thread(target=speak, args=("Chat session stopped.",), daemon=True).start()
        return result
    
    # ===== GOOGLE WORKSPACE HANDLERS =====
    
    def _handle_gmail_unread(self, params: Dict) -> str:
        """Check unread Gmail emails"""
        from Brain.google_workspace_client import get_google_client
        import json
        
        client = get_google_client()
        limit = params.get("limit", 5)
        
        result = client.gmail_list_unread(limit)
        
        if result.get("status") == "error":
            raise ValueError(f"Gmail error: {result.get('error')}")
        
        return json.dumps(result["data"])
    
    def _handle_gmail_summarize(self, params: Dict) -> str:
        """Summarize Gmail — fetches emails locally then uses LLM to summarize.
        Avoids slow Apps Script AI summarization (timeout issues).
        """
        from Brain.google_workspace_client import get_google_client
        import json
        
        client = get_google_client()
        period = params.get("period", "today")
        
        # Determine how many emails to fetch based on the query
        # "last email" / "last 1" → 1 email, otherwise 5
        limit = 1
        if period:
            period_lower = period.lower()
            for word in period_lower.split():
                if word.isdigit():
                    limit = min(int(word), 10)
                    break
            if "last email" in period_lower or "latest" in period_lower:
                limit = 1
        
        # Fetch emails locally (fast — no timeout)
        result = client.gmail_list_unread(limit)
        
        if result.get("status") == "error":
            raise ValueError(f"Gmail error: {result.get('error')}")
        
        data = result["data"]
        emails = data.get("emails", [])
        
        if not emails:
            return json.dumps({
                "emails": [],
                "count": 0,
                "totalUnread": data.get("totalUnread", 0),
                "summary": "No unread emails found."
            })
        
        # Build summary text from fetched emails
        email_texts = []
        for i, e in enumerate(emails, 1):
            sender = e.get("from", "Unknown").split("<")[0].strip()
            subject = e.get("subject", "(no subject)")
            snippet = e.get("snippet", "")[:200]
            email_texts.append(f"Email {i}: From {sender}, Subject: {subject}, Preview: {snippet}")
        
        emails_context = "\n".join(email_texts)
        
        # Use local LLM to generate a natural summary
        try:
            from Brain.intent_engine import get_engine
            engine = get_engine()
            
            if limit == 1:
                prompt = f"The user asked to summarize their last email. Here it is:\n{emails_context}\n\nGive a brief, natural summary of this email in 1-2 sentences."
            else:
                prompt = f"The user wants a summary of their {limit} most recent emails:\n{emails_context}\n\nSummarize these emails briefly and naturally."
            
            summary = engine._generate_natural(prompt)
        except Exception:
            # Fallback: just use the snippets
            summary = "; ".join([f"{e.get('subject', '?')} from {e.get('from', '?').split('<')[0].strip()}" for e in emails])
        
        # Return combined data with summary for popup + speech
        data["summary"] = summary
        return json.dumps(data)
    
    def _handle_gmail_search(self, params: Dict) -> str:
        """Search Gmail"""
        from Brain.google_workspace_client import get_google_client
        import json
        
        client = get_google_client()
        
        from_email = params.get("from", "")
        subject = params.get("subject", "")
        keyword = params.get("keyword", "")
        query = params.get("query", "")
        
        result = client.gmail_search(
            query=query,
            from_email=from_email,
            subject=subject,
            keyword=keyword
        )
        
        if result.get("status") == "error":
            raise ValueError(f"Gmail error: {result.get('error')}")
        
        return json.dumps(result["data"])
    
    def _handle_gmail_send(self, params: Dict) -> str:
        """Send email via 3-Tier Autonomous Email Engine"""
        import json
        from Tools.email_tool import send_email

        to = params.get("to", "")
        subject = params.get("subject", "Message from JARVIS")
        body = params.get("body", "")
        cc = params.get("cc", "")
        bcc = params.get("bcc", "")

        result = send_email(to=to, subject=subject, body=body, cc=cc, bcc=bcc)

        if result.get("status") == "error":
            raise ValueError(f"Email error: {result.get('error')}")

        return json.dumps(result)

    
    def _handle_calendar_today(self, params: Dict) -> str:
        """Get today's calendar events + Google Tasks combined"""
        from Brain.google_workspace_client import get_google_client
        import json
        
        client = get_google_client()
        
        # 1. Get calendar events
        cal_result = client.calendar_get_today()
        if cal_result.get("status") == "error":
            raise ValueError(f"Calendar error: {cal_result.get('error')}")
        
        data = cal_result["data"]
        events = data.get("events", [])
        
        # 2. Try to get Google Tasks (best-effort — may not be deployed yet)
        try:
            tasks_result = client.tasks_get_today()
            if tasks_result.get("status") == "success":
                tasks = tasks_result.get("data", {}).get("tasks", [])
                # Convert tasks to event-like format and merge
                for task in tasks:
                    events.append({
                        "title": f"[Task] {task.get('title', 'Untitled')}",
                        "start": task.get("due", ""),
                        "location": "",
                        "is_task": True
                    })
        except Exception:
            pass  # Tasks API not available yet — skip silently
        
        data["events"] = events
        data["count"] = len(events)
        
        return json.dumps(data)
    
    def _handle_calendar_create_event(self, params: Dict) -> str:
        """Create a new Google Calendar event"""
        from Brain.google_workspace_client import get_google_client
        from TextToSpeech.Fast_DF_TTS import speak
        import json
        import threading
        
        client = get_google_client()
        
        title = params.get("title", "Untitled Event")
        start_time = params.get("start_time")
        end_time = params.get("end_time")
        description = params.get("description", "")
        location = params.get("location", "")
        attendees = params.get("attendees")
        
        result = client.calendar_create_event(
            title, start_time, end_time, description, location, attendees
        )
        
        if result.get("status") == "error":
            raise ValueError(f"Calendar error: {result.get('error')}")
        
        threading.Thread(
            target=speak,
            args=(f"Event '{title}' has been added to your calendar.",),
            daemon=True
        ).start()
        
        return json.dumps(result.get("data", result))
    
    def _handle_drive_list(self, params: Dict) -> str:
        """List Google Drive files"""
        from Brain.google_workspace_client import get_google_client
        import json
        
        client = get_google_client()
        
        file_type = params.get("file_type")
        query = params.get("query", "")
        
        result = client.drive_list_files(file_type=file_type, query=query)
        
        if result.get("status") == "error":
            raise ValueError(f"Drive error: {result.get('error')}")
        
        return json.dumps(result["data"])
    
    def _handle_drive_create_doc(self, params: Dict) -> str:
        """Create Google Doc"""
        from Brain.google_workspace_client import get_google_client
        import json
        
        client = get_google_client()
        
        title = params.get("title")
        content = params.get("content", "")
        
        result = client.drive_create_doc(title, content)
        
        if result.get("status") == "error":
            raise ValueError(f"Drive error: {result.get('error')}")
        
        return json.dumps(result["data"])
    
    def _handle_sheets_log(self, params: Dict) -> str:
        """Append row to Google Sheets"""
        from Brain.google_workspace_client import get_google_client
        import json
        
        client = get_google_client()
        
        spreadsheet_id = params.get("spreadsheet_id")
        values = params.get("values")
        sheet_name = params.get("sheet_name", "Sheet1")
        
        result = client.sheets_append(spreadsheet_id, sheet_name, values)
        
        if result.get("status") == "error":
            raise ValueError(f"Sheets error: {result.get('error')}")
        
        return json.dumps(result["data"])
    
    # ===== MCP HANDLERS =====
    
    def _handle_mcp_web_search(self, params: Dict) -> str:
        """Search the web using DuckDuckGo MCP for real-time information"""
        from Tools.MCP.mcp_client import search_web_sync
        from TextToSpeech.Fast_DF_TTS import speak
        import threading
        
        query = params.get("query", "")
        print(f"[MCP] Web searching: {query}")
        
        try:
            result = search_web_sync(query)
            threading.Thread(target=speak, args=(f"Here's what I found about {query}",), daemon=True).start()
            return result
        except Exception as e:
            error_msg = f"Web search error: {e}"
            print(f"[MCP] {error_msg}")
            return error_msg
    
    def _handle_mcp_github_search(self, params: Dict) -> str:
        """Search GitHub repositories using MCP"""
        from Tools.MCP.mcp_manager import search_github_sync
        from TextToSpeech.Fast_DF_TTS import speak
        import threading
        
        query = params.get("query", "")
        print(f"[MCP] GitHub searching: {query}")
        
        try:
            result = search_github_sync(query)
            threading.Thread(target=speak, args=(f"Found GitHub repositories for {query}",), daemon=True).start()
            return result
        except Exception as e:
            error_msg = f"GitHub search error: {e}"
            print(f"[MCP] {error_msg}")
            return error_msg
    
    def _handle_mcp_image_search(self, params: Dict) -> str:
        """Search for images using browser automation (Playwright MCP)"""
        import webbrowser
        from TextToSpeech.Fast_DF_TTS import speak
        import threading
        
        query = params.get("query", "")
        print(f"[MCP] Image searching: {query}")
        
        try:
            # Open Google Images with search query
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&tbm=isch"
            webbrowser.open(search_url)
            threading.Thread(target=speak, args=(f"Opening images for {query}",), daemon=True).start()
            return f"Opened Google Images for: {query}"
        except Exception as e:
            error_msg = f"Image search error: {e}"
            print(f"[MCP] {error_msg}")
            return error_msg
    
    def _handle_mcp_fetch_url(self, params: Dict) -> str:
        """Fetch content from a URL"""
        import requests
        
        url = params.get("url", "")
        print(f"[MCP] Fetching URL: {url}")
        
        try:
            response = requests.get(url, timeout=10)
            return response.text[:2000]  # Return first 2000 chars
        except Exception as e:
            error_msg = f"URL fetch error: {e}"
            print(f"[MCP] {error_msg}")
            return error_msg

    # ===== PLAYWRIGHT BROWSER HANDLERS =====
    
    def _handle_browser_navigate(self, params: Dict) -> str:
        """Navigate browser to a URL"""
        from Agents.Browser_Agent.playwright_mcp_client import browser_navigate_sync
        from TextToSpeech.Fast_DF_TTS import speak
        import threading
        import json
        
        url = params.get("url", "")
        print(f"[Playwright] Navigating to: {url}")
        
        try:
            result = browser_navigate_sync(url)
            if result.get("success"):
                threading.Thread(target=speak, args=(f"Opening {result.get('title', url)}",), daemon=True).start()
                return json.dumps(result)
            else:
                return f"Navigation error: {result.get('error')}"
        except Exception as e:
            error_msg = f"Navigation error: {e}"
            print(f"[Playwright] {error_msg}")
            return error_msg
    
    def _handle_browser_navigate_back(self, params: Dict) -> str:
        """Navigate back in browser history"""
        from Agents.Browser_Agent.playwright_mcp_client import browser_navigate_back_sync
        import json
        
        try:
            result = browser_navigate_back_sync()
            return json.dumps(result)
        except Exception as e:
            return f"Navigate back error: {e}"
    
    def _handle_browser_navigate_forward(self, params: Dict) -> str:
        """Navigate forward in browser history"""
        from Agents.Browser_Agent.playwright_mcp_client import browser_navigate_forward_sync
        import json
        
        try:
            result = browser_navigate_forward_sync()
            return json.dumps(result)
        except Exception as e:
            return f"Navigate forward error: {e}"
    
    def _handle_browser_close(self, params: Dict) -> str:
        """Close current browser page"""
        from Agents.Browser_Agent.playwright_mcp_client import browser_close_sync
        import json
        
        try:
            result = browser_close_sync()
            return json.dumps(result)
        except Exception as e:
            return f"Close page error: {e}"
    
    def _handle_browser_snapshot(self, params: Dict) -> str:
        """Get accessibility tree snapshot of current page"""
        from Agents.Browser_Agent.playwright_mcp_client import browser_snapshot_sync
        from TextToSpeech.Fast_DF_TTS import speak
        import threading
        import json
        
        print("[Playwright] Getting page snapshot...")
        
        try:
            result = browser_snapshot_sync()
            if result.get("success"):
                title = result.get("title", "Unknown page")
                text = result.get("text_content", "")[:500]
                threading.Thread(target=speak, args=(f"Here's what's on {title}. {text[:200]}",), daemon=True).start()
                return json.dumps(result)
            else:
                return f"Snapshot error: {result.get('error')}"
        except Exception as e:
            return f"Snapshot error: {e}"
    
    def _handle_browser_screenshot(self, params: Dict) -> str:
        """Take screenshot of the page"""
        from Agents.Browser_Agent.playwright_mcp_client import browser_screenshot_sync
        from TextToSpeech.Fast_DF_TTS import speak
        import threading
        import json
        
        path = params.get("path")
        full_page = params.get("full_page", False)
        
        print("[Playwright] Taking screenshot...")
        
        try:
            result = browser_screenshot_sync(path, full_page)
            if result.get("success"):
                threading.Thread(target=speak, args=("Screenshot captured",), daemon=True).start()
                return json.dumps(result)
            else:
                return f"Screenshot error: {result.get('error')}"
        except Exception as e:
            return f"Screenshot error: {e}"
    
    def _handle_browser_click(self, params: Dict) -> str:
        """Click an element on the page"""
        from Agents.Browser_Agent.playwright_mcp_client import browser_click_sync
        from TextToSpeech.Fast_DF_TTS import speak
        import threading
        import json
        
        element = params.get("element", "")
        ref = params.get("ref")
        
        print(f"[Playwright] Clicking: {element}")
        
        try:
            result = browser_click_sync(element, ref)
            if result.get("success"):
                threading.Thread(target=speak, args=(f"Clicked {element}",), daemon=True).start()
                return json.dumps(result)
            else:
                return f"Click error: {result.get('error')}"
        except Exception as e:
            return f"Click error: {e}"
    
    def _handle_browser_hover(self, params: Dict) -> str:
        """Hover over an element"""
        from Agents.Browser_Agent.playwright_mcp_client import browser_hover_sync
        import json
        
        ref = params.get("ref", "")
        
        try:
            result = browser_hover_sync(ref)
            return json.dumps(result)
        except Exception as e:
            return f"Hover error: {e}"
    
    def _handle_browser_type(self, params: Dict) -> str:
        """Type text into an input field"""
        from Agents.Browser_Agent.playwright_mcp_client import browser_type_sync
        from TextToSpeech.Fast_DF_TTS import speak
        import threading
        import json
        
        ref = params.get("ref", "")
        text = params.get("text", "")
        
        print(f"[Playwright] Typing into: {ref}")
        
        try:
            result = browser_type_sync(ref, text)
            if result.get("success"):
                threading.Thread(target=speak, args=("Done typing",), daemon=True).start()
                return json.dumps(result)
            else:
                return f"Type error: {result.get('error')}"
        except Exception as e:
            return f"Type error: {e}"
    
    def _handle_browser_press_key(self, params: Dict) -> str:
        """Press a keyboard key"""
        from Agents.Browser_Agent.playwright_mcp_client import browser_press_key_sync
        import json
        
        key = params.get("key", "")
        
        print(f"[Playwright] Pressing key: {key}")
        
        try:
            result = browser_press_key_sync(key)
            return json.dumps(result)
        except Exception as e:
            return f"Press key error: {e}"
    
    def _handle_browser_fill_form(self, params: Dict) -> str:
        """Fill multiple form fields"""
        from Agents.Browser_Agent.playwright_mcp_client import browser_fill_form_sync
        from TextToSpeech.Fast_DF_TTS import speak
        import threading
        import json
        
        fields = params.get("fields", [])
        
        print(f"[Playwright] Filling form with {len(fields)} fields")
        
        try:
            result = browser_fill_form_sync(fields)
            if result.get("success"):
                threading.Thread(target=speak, args=("Form filled",), daemon=True).start()
                return json.dumps(result)
            else:
                return f"Fill form error: {result.get('error')}"
        except Exception as e:
            return f"Fill form error: {e}"
    
    def _handle_browser_select_option(self, params: Dict) -> str:
        """Select option from dropdown"""
        from Agents.Browser_Agent.playwright_mcp_client import browser_select_option_sync
        import json
        
        ref = params.get("ref", "")
        value = params.get("value", "")
        
        try:
            result = browser_select_option_sync(ref, value)
            return json.dumps(result)
        except Exception as e:
            return f"Select error: {e}"
    
    def _handle_browser_dialog(self, params: Dict) -> str:
        """Handle browser dialogs"""
        from Agents.Browser_Agent.playwright_mcp_client import browser_handle_dialog_sync
        import json
        
        accept = params.get("accept", True)
        text = params.get("text")
        
        try:
            result = browser_handle_dialog_sync(accept, text)
            return json.dumps(result)
        except Exception as e:
            return f"Dialog error: {e}"
    
    def _handle_browser_evaluate(self, params: Dict) -> str:
        """Execute JavaScript on the page"""
        from Agents.Browser_Agent.playwright_mcp_client import browser_evaluate_sync
        import json
        
        code = params.get("code", "")
        
        print(f"[Playwright] Evaluating JavaScript")
        
        try:
            result = browser_evaluate_sync(code)
            return json.dumps(result)
        except Exception as e:
            return f"Evaluate error: {e}"
    
    def _handle_browser_tabs(self, params: Dict) -> str:
        """Manage browser tabs"""
        from Agents.Browser_Agent.playwright_mcp_client import browser_tabs_sync
        import json
        
        action = params.get("action", "list")
        index = params.get("index")
        url = params.get("url")
        
        try:
            result = browser_tabs_sync(action, index, url)
            return json.dumps(result)
        except Exception as e:
            return f"Tabs error: {e}"
    
    def _handle_browser_resize(self, params: Dict) -> str:
        """Resize browser window"""
        from Agents.Browser_Agent.playwright_mcp_client import browser_resize_sync
        import json
        
        width = params.get("width", 1280)
        height = params.get("height", 720)
        
        try:
            result = browser_resize_sync(width, height)
            return json.dumps(result)
        except Exception as e:
            return f"Resize error: {e}"
    
    def _handle_browser_wait_for(self, params: Dict) -> str:
        """Wait for element/condition"""
        from Agents.Browser_Agent.playwright_mcp_client import browser_wait_for_sync
        import json
        
        selector = params.get("selector", "")
        timeout = params.get("timeout", 30000)
        state = params.get("state", "visible")
        
        try:
            result = browser_wait_for_sync(selector, timeout, state)
            return json.dumps(result)
        except Exception as e:
            return f"Wait error: {e}"

    def register(self, tool: ToolDefinition):
        """Register a tool definition."""
        self._tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def execute(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """
        Execute a tool with the given parameters.
        
        Args:
            tool_name: Name of the tool to execute
            params: Parameters for the tool
            
        Returns:
            Result of the tool execution
            
        Raises:
            ValueError: If tool not found or required params missing
        """
        tool = self.get_tool(tool_name)
        
        if not tool:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        # Validate required params
        missing = [p for p in tool.required_params if p not in params or not params[p]]
        if missing:
            raise ValueError(f"Missing required parameters for {tool_name}: {missing}")
        
        if tool.handler:
            return tool.handler(params)
        else:
            raise ValueError(f"No handler registered for tool: {tool_name}")
    
    def get_tool_descriptions(self) -> str:
        """Get formatted descriptions of all tools for LLM context."""
        lines = ["Available tools:"]
        for name, tool in self._tools.items():
            params = tool.required_params + [f"{p}?" for p in tool.optional_params]
            params_str = ", ".join(params) if params else "none"
            lines.append(f"- {name}: {tool.description} (params: {params_str})")
        return "\n".join(lines)
    
    def list_tools(self) -> List[str]:
        """Get list of all registered tool names."""
        return list(self._tools.keys())


# Global registry instance
_registry: Optional[ToolsRegistry] = None


def get_registry() -> ToolsRegistry:
    """Get the global tools registry instance."""
    global _registry
    if _registry is None:
        _registry = ToolsRegistry()
    return _registry


if __name__ == "__main__":
    # Test the registry
    registry = get_registry()
    print(registry.get_tool_descriptions())
    print("\nRegistered tools:", registry.list_tools())
