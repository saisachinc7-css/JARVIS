"""
Playwright MCP Client for JARVIS Voice Assistant
Full browser automation via voice commands using Playwright MCP.

Capabilities:
- Navigation & page control
- Page inspection & analysis
- User interactions (click, type, hover)
- Form handling
- Dialog handling
- Tab management
- JavaScript evaluation
"""

import asyncio
import json
import threading
import os
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum


class BrowserAction(Enum):
    """Browser action types"""
    NAVIGATE = "browser_navigate"
    NAVIGATE_BACK = "browser_navigate_back"
    NAVIGATE_FORWARD = "browser_navigate_forward"
    CLOSE = "browser_close"
    SNAPSHOT = "browser_snapshot"
    SCREENSHOT = "browser_take_screenshot"
    CLICK = "browser_click"
    HOVER = "browser_hover"
    TYPE = "browser_type"
    PRESS_KEY = "browser_press_key"
    FILL_FORM = "browser_fill_form"
    SELECT_OPTION = "browser_select_option"
    FILE_UPLOAD = "browser_file_upload"
    HANDLE_DIALOG = "browser_handle_dialog"
    EVALUATE = "browser_evaluate"
    TABS = "browser_tabs"
    RESIZE = "browser_resize"
    WAIT_FOR = "browser_wait_for"
    CONSOLE_MESSAGES = "browser_console_messages"
    NETWORK_REQUESTS = "browser_network_requests"
    DRAG = "browser_drag"


@dataclass
class PlaywrightTool:
    """Definition of a Playwright MCP tool"""
    name: str
    description: str
    required_params: List[str] = field(default_factory=list)
    optional_params: List[str] = field(default_factory=list)


# All available Playwright MCP tools
PLAYWRIGHT_TOOLS = {
    BrowserAction.NAVIGATE: PlaywrightTool(
        name="browser_navigate",
        description="Navigate browser to a URL",
        required_params=["url"]
    ),
    BrowserAction.NAVIGATE_BACK: PlaywrightTool(
        name="browser_navigate_back",
        description="Go back in browser history"
    ),
    BrowserAction.NAVIGATE_FORWARD: PlaywrightTool(
        name="browser_navigate_forward",
        description="Go forward in browser history"
    ),
    BrowserAction.CLOSE: PlaywrightTool(
        name="browser_close",
        description="Close the current browser page"
    ),
    BrowserAction.SNAPSHOT: PlaywrightTool(
        name="browser_snapshot",
        description="Get accessibility tree snapshot of current page (better than screenshots for AI understanding)"
    ),
    BrowserAction.SCREENSHOT: PlaywrightTool(
        name="browser_take_screenshot",
        description="Take a visual screenshot of the page",
        optional_params=["path", "full_page"]
    ),
    BrowserAction.CLICK: PlaywrightTool(
        name="browser_click",
        description="Click an element on the page",
        required_params=["element"],
        optional_params=["ref"]
    ),
    BrowserAction.HOVER: PlaywrightTool(
        name="browser_hover",
        description="Hover over an element",
        required_params=["ref"]
    ),
    BrowserAction.TYPE: PlaywrightTool(
        name="browser_type",
        description="Type text into an input field",
        required_params=["ref", "text"]
    ),
    BrowserAction.PRESS_KEY: PlaywrightTool(
        name="browser_press_key",
        description="Press a keyboard key",
        required_params=["key"]
    ),
    BrowserAction.FILL_FORM: PlaywrightTool(
        name="browser_fill_form",
        description="Fill multiple form fields at once",
        required_params=["fields"]
    ),
    BrowserAction.SELECT_OPTION: PlaywrightTool(
        name="browser_select_option",
        description="Select an option from a dropdown",
        required_params=["ref", "value"]
    ),
    BrowserAction.FILE_UPLOAD: PlaywrightTool(
        name="browser_file_upload",
        description="Upload a file",
        required_params=["ref", "path"]
    ),
    BrowserAction.HANDLE_DIALOG: PlaywrightTool(
        name="browser_handle_dialog",
        description="Handle browser dialogs (alert, confirm, prompt)",
        required_params=["accept"],
        optional_params=["text"]
    ),
    BrowserAction.EVALUATE: PlaywrightTool(
        name="browser_evaluate",
        description="Execute custom JavaScript on the page",
        required_params=["code"]
    ),
    BrowserAction.TABS: PlaywrightTool(
        name="browser_tabs",
        description="Manage browser tabs (list, create, switch, close)",
        required_params=["action"],
        optional_params=["index", "url"]
    ),
    BrowserAction.RESIZE: PlaywrightTool(
        name="browser_resize",
        description="Resize browser window",
        required_params=["width", "height"]
    ),
    BrowserAction.WAIT_FOR: PlaywrightTool(
        name="browser_wait_for",
        description="Wait for a specific condition",
        required_params=["selector"],
        optional_params=["timeout", "state"]
    ),
    BrowserAction.CONSOLE_MESSAGES: PlaywrightTool(
        name="browser_console_messages",
        description="Get console messages/errors from the page"
    ),
    BrowserAction.NETWORK_REQUESTS: PlaywrightTool(
        name="browser_network_requests",
        description="Monitor network traffic"
    ),
    BrowserAction.DRAG: PlaywrightTool(
        name="browser_drag",
        description="Drag and drop elements",
        required_params=["source_ref", "target_ref"]
    ),
}


class PlaywrightSession:
    """
    Manages a Playwright browser session.
    Handles browser lifecycle and provides high-level methods.
    """
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self._browser = None
        self._context = None
        self._page = None
        self._pages: List[Any] = []
        self._current_page_index = 0
        self._lock = threading.Lock()
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize Playwright browser session"""
        if self._initialized:
            return True
        
        try:
            from playwright.async_api import async_playwright
            
            print("[Playwright] Launching browser...")
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']
            )
            self._context = await self._browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            self._page = await self._context.new_page()
            self._pages = [self._page]
            self._initialized = True
            print("[Playwright] [OK] Browser session ready")
            return True
            
        except ImportError:
            print("[Playwright] ✗ Playwright not installed. Run: pip install playwright && playwright install chromium")
            return False
        except Exception as e:
            print(f"[Playwright] ✗ Initialization error: {e}")
            return False
    
    async def close(self):
        """Close browser session"""
        if self._browser:
            await self._browser.close()
        if hasattr(self, '_playwright') and self._playwright:
            await self._playwright.stop()
        self._initialized = False
        print("[Playwright] Session closed")
    
    @property
    def page(self):
        """Get current active page"""
        return self._pages[self._current_page_index] if self._pages else None
    
    # ===== NAVIGATION =====
    
    async def navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to a URL"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Ensure URL has protocol
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            await self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            title = await self.page.title()
            
            return {
                "success": True,
                "url": self.page.url,
                "title": title,
                "message": f"Navigated to {title}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def navigate_back(self) -> Dict[str, Any]:
        """Go back in browser history"""
        try:
            await self.page.go_back()
            return {"success": True, "message": "Navigated back"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def navigate_forward(self) -> Dict[str, Any]:
        """Go forward in browser history"""
        try:
            await self.page.go_forward()
            return {"success": True, "message": "Navigated forward"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def close_page(self) -> Dict[str, Any]:
        """Close current page"""
        try:
            if len(self._pages) > 1:
                await self.page.close()
                self._pages.pop(self._current_page_index)
                self._current_page_index = max(0, self._current_page_index - 1)
                return {"success": True, "message": "Page closed"}
            else:
                return {"success": False, "error": "Cannot close last page"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ===== PAGE INSPECTION =====
    
    async def snapshot(self) -> Dict[str, Any]:
        """Get accessibility tree snapshot of the page"""
        try:
            # Get accessibility snapshot for AI understanding
            snapshot = await self.page.accessibility.snapshot()
            
            # Also get readable text content
            text_content = await self.page.evaluate('''() => {
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT,
                    null,
                    false
                );
                let text = "";
                let node;
                while(node = walker.nextNode()) {
                    if (node.textContent.trim()) {
                        text += node.textContent.trim() + " ";
                    }
                }
                return text.substring(0, 5000);  // Limit length
            }''')
            
            return {
                "success": True,
                "title": await self.page.title(),
                "url": self.page.url,
                "accessibility_tree": snapshot,
                "text_content": text_content[:2000],
                "message": "Page snapshot captured"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def screenshot(self, path: Optional[str] = None, full_page: bool = False) -> Dict[str, Any]:
        """Take a screenshot of the page"""
        try:
            if not path:
                # Default to JARVIS screenshots folder
                screenshots_dir = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "DATA", "screenshots"
                )
                os.makedirs(screenshots_dir, exist_ok=True)
                
                import time
                timestamp = int(time.time())
                path = os.path.join(screenshots_dir, f"screenshot_{timestamp}.png")
            
            await self.page.screenshot(path=path, full_page=full_page)
            
            return {
                "success": True,
                "path": path,
                "message": f"Screenshot saved to {path}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_console_messages(self) -> Dict[str, Any]:
        """Get console messages from the page"""
        try:
            messages = []
            
            def on_console(msg):
                messages.append({
                    "type": msg.type,
                    "text": msg.text
                })
            
            self.page.on("console", on_console)
            # Wait briefly for any pending messages
            await asyncio.sleep(0.5)
            
            return {
                "success": True,
                "messages": messages[:50],  # Limit to 50 messages
                "count": len(messages)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ===== USER INTERACTIONS =====
    
    async def click(self, element: str, ref: Optional[str] = None) -> Dict[str, Any]:
        """Click an element on the page"""
        try:
            # Try different selector strategies
            selector = ref if ref else element
            
            # Try accessibility selector first
            locator = self.page.get_by_role("button", name=element)
            if await locator.count() > 0:
                await locator.first.click()
                return {"success": True, "message": f"Clicked button: {element}"}
            
            # Try link
            locator = self.page.get_by_role("link", name=element)
            if await locator.count() > 0:
                await locator.first.click()
                return {"success": True, "message": f"Clicked link: {element}"}
            
            # Try text content
            locator = self.page.get_by_text(element, exact=False)
            if await locator.count() > 0:
                await locator.first.click()
                return {"success": True, "message": f"Clicked text: {element}"}
            
            # Try CSS selector
            try:
                await self.page.click(selector, timeout=5000)
                return {"success": True, "message": f"Clicked: {selector}"}
            except:
                pass
            
            return {"success": False, "error": f"Element not found: {element}"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def hover(self, ref: str) -> Dict[str, Any]:
        """Hover over an element"""
        try:
            await self.page.hover(ref)
            return {"success": True, "message": f"Hovering over: {ref}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def type_text(self, ref: str, text: str) -> Dict[str, Any]:
        """Type text into an input field"""
        try:
            # Try multiple selector strategies
            
            # Try by placeholder
            locator = self.page.get_by_placeholder(ref)
            if await locator.count() > 0:
                await locator.first.fill(text)
                return {"success": True, "message": f"Typed into placeholder '{ref}'"}
            
            # Try by label
            locator = self.page.get_by_label(ref)
            if await locator.count() > 0:
                await locator.first.fill(text)
                return {"success": True, "message": f"Typed into field '{ref}'"}
            
            # Try by role textbox
            locator = self.page.get_by_role("textbox", name=ref)
            if await locator.count() > 0:
                await locator.first.fill(text)
                return {"success": True, "message": f"Typed into textbox '{ref}'"}
            
            # Try CSS selector
            try:
                await self.page.fill(ref, text)
                return {"success": True, "message": f"Typed into: {ref}"}
            except:
                pass
            
            return {"success": False, "error": f"Input field not found: {ref}"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def press_key(self, key: str) -> Dict[str, Any]:
        """Press a keyboard key"""
        try:
            # Map common key names
            key_map = {
                "enter": "Enter",
                "tab": "Tab",
                "escape": "Escape",
                "esc": "Escape",
                "space": " ",
                "backspace": "Backspace",
                "delete": "Delete",
                "up": "ArrowUp",
                "down": "ArrowDown",
                "left": "ArrowLeft",
                "right": "ArrowRight",
            }
            
            mapped_key = key_map.get(key.lower(), key)
            await self.page.keyboard.press(mapped_key)
            
            return {"success": True, "message": f"Pressed key: {key}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def fill_form(self, fields: List[Dict[str, str]]) -> Dict[str, Any]:
        """Fill multiple form fields at once"""
        try:
            filled = []
            errors = []
            
            for field in fields:
                ref = field.get("ref", "")
                value = field.get("value", "")
                
                result = await self.type_text(ref, value)
                if result["success"]:
                    filled.append(ref)
                else:
                    errors.append(f"{ref}: {result.get('error', 'unknown error')}")
            
            if errors:
                return {
                    "success": len(filled) > 0,
                    "message": f"Filled {len(filled)} fields",
                    "filled": filled,
                    "errors": errors
                }
            
            return {
                "success": True,
                "message": f"Filled all {len(filled)} fields successfully",
                "filled": filled
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def select_option(self, ref: str, value: str) -> Dict[str, Any]:
        """Select an option from a dropdown"""
        try:
            await self.page.select_option(ref, value)
            return {"success": True, "message": f"Selected {value} in {ref}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def upload_file(self, ref: str, path: str) -> Dict[str, Any]:
        """Upload a file"""
        try:
            await self.page.set_input_files(ref, path)
            return {"success": True, "message": f"Uploaded file: {path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def drag(self, source_ref: str, target_ref: str) -> Dict[str, Any]:
        """Drag and drop elements"""
        try:
            await self.page.drag_and_drop(source_ref, target_ref)
            return {"success": True, "message": f"Dragged {source_ref} to {target_ref}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ===== DIALOGS & JAVASCRIPT =====
    
    async def handle_dialog(self, accept: bool, text: Optional[str] = None) -> Dict[str, Any]:
        """Handle browser dialogs (alert, confirm, prompt)"""
        try:
            async def dialog_handler(dialog):
                if accept:
                    if text and dialog.type == "prompt":
                        await dialog.accept(text)
                    else:
                        await dialog.accept()
                else:
                    await dialog.dismiss()
            
            self.page.on("dialog", dialog_handler)
            
            return {
                "success": True,
                "message": f"Dialog handler set to {'accept' if accept else 'dismiss'}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def evaluate(self, code: str) -> Dict[str, Any]:
        """Execute custom JavaScript on the page"""
        try:
            result = await self.page.evaluate(code)
            return {
                "success": True,
                "result": result,
                "message": "JavaScript executed successfully"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ===== TAB MANAGEMENT =====
    
    async def manage_tabs(self, action: str, index: Optional[int] = None, url: Optional[str] = None) -> Dict[str, Any]:
        """Manage browser tabs"""
        try:
            if action == "list":
                tabs = []
                for i, page in enumerate(self._pages):
                    tabs.append({
                        "index": i,
                        "url": page.url,
                        "title": await page.title(),
                        "active": i == self._current_page_index
                    })
                return {"success": True, "tabs": tabs, "count": len(tabs)}
            
            elif action == "create" or action == "new":
                new_page = await self._context.new_page()
                self._pages.append(new_page)
                self._current_page_index = len(self._pages) - 1
                if url:
                    await self.navigate(url)
                return {"success": True, "message": "New tab created", "index": self._current_page_index}
            
            elif action == "switch" and index is not None:
                if 0 <= index < len(self._pages):
                    self._current_page_index = index
                    await self._pages[index].bring_to_front()
                    return {"success": True, "message": f"Switched to tab {index}"}
                else:
                    return {"success": False, "error": f"Invalid tab index: {index}"}
            
            elif action == "close":
                return await self.close_page()
            
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ===== WINDOW CONTROL =====
    
    async def resize(self, width: int, height: int) -> Dict[str, Any]:
        """Resize browser window"""
        try:
            await self.page.set_viewport_size({"width": width, "height": height})
            return {"success": True, "message": f"Resized to {width}x{height}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def wait_for(self, selector: str, timeout: int = 30000, state: str = "visible") -> Dict[str, Any]:
        """Wait for a specific condition"""
        try:
            await self.page.wait_for_selector(selector, timeout=timeout, state=state)
            return {"success": True, "message": f"Element found: {selector}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ============================================================================
# GLOBAL SESSION & SYNC WRAPPERS
# ============================================================================

_session: Optional[PlaywrightSession] = None
_session_lock = threading.Lock()


def get_playwright_session(headless: bool = False) -> PlaywrightSession:
    """Get or create global Playwright session"""
    global _session
    
    with _session_lock:
        if _session is None:
            _session = PlaywrightSession(headless=headless)
    
    return _session


async def _ensure_initialized() -> PlaywrightSession:
    """Ensure session is initialized"""
    session = get_playwright_session()
    if not session._initialized:
        await session.initialize()
    return session


# Synchronous wrappers for JARVIS integration

def browser_navigate_sync(url: str) -> Dict[str, Any]:
    """Navigate to URL (sync)"""
    async def _run():
        session = await _ensure_initialized()
        return await session.navigate(url)
    return asyncio.run(_run())


def browser_navigate_back_sync() -> Dict[str, Any]:
    """Navigate back (sync)"""
    async def _run():
        session = await _ensure_initialized()
        return await session.navigate_back()
    return asyncio.run(_run())


def browser_navigate_forward_sync() -> Dict[str, Any]:
    """Navigate forward (sync)"""
    async def _run():
        session = await _ensure_initialized()
        return await session.navigate_forward()
    return asyncio.run(_run())


def browser_close_sync() -> Dict[str, Any]:
    """Close current page (sync)"""
    async def _run():
        session = await _ensure_initialized()
        return await session.close_page()
    return asyncio.run(_run())


def browser_snapshot_sync() -> Dict[str, Any]:
    """Get page snapshot (sync)"""
    async def _run():
        session = await _ensure_initialized()
        return await session.snapshot()
    return asyncio.run(_run())


def browser_screenshot_sync(path: Optional[str] = None, full_page: bool = False) -> Dict[str, Any]:
    """Take screenshot (sync)"""
    async def _run():
        session = await _ensure_initialized()
        return await session.screenshot(path, full_page)
    return asyncio.run(_run())


def browser_click_sync(element: str, ref: Optional[str] = None) -> Dict[str, Any]:
    """Click element (sync)"""
    async def _run():
        session = await _ensure_initialized()
        return await session.click(element, ref)
    return asyncio.run(_run())


def browser_hover_sync(ref: str) -> Dict[str, Any]:
    """Hover over element (sync)"""
    async def _run():
        session = await _ensure_initialized()
        return await session.hover(ref)
    return asyncio.run(_run())


def browser_type_sync(ref: str, text: str) -> Dict[str, Any]:
    """Type text (sync)"""
    async def _run():
        session = await _ensure_initialized()
        return await session.type_text(ref, text)
    return asyncio.run(_run())


def browser_press_key_sync(key: str) -> Dict[str, Any]:
    """Press key (sync)"""
    async def _run():
        session = await _ensure_initialized()
        return await session.press_key(key)
    return asyncio.run(_run())


def browser_fill_form_sync(fields: List[Dict[str, str]]) -> Dict[str, Any]:
    """Fill form (sync)"""
    async def _run():
        session = await _ensure_initialized()
        return await session.fill_form(fields)
    return asyncio.run(_run())


def browser_select_option_sync(ref: str, value: str) -> Dict[str, Any]:
    """Select option (sync)"""
    async def _run():
        session = await _ensure_initialized()
        return await session.select_option(ref, value)
    return asyncio.run(_run())


def browser_upload_file_sync(ref: str, path: str) -> Dict[str, Any]:
    """Upload file (sync)"""
    async def _run():
        session = await _ensure_initialized()
        return await session.upload_file(ref, path)
    return asyncio.run(_run())


def browser_handle_dialog_sync(accept: bool, text: Optional[str] = None) -> Dict[str, Any]:
    """Handle dialog (sync)"""
    async def _run():
        session = await _ensure_initialized()
        return await session.handle_dialog(accept, text)
    return asyncio.run(_run())


def browser_evaluate_sync(code: str) -> Dict[str, Any]:
    """Evaluate JavaScript (sync)"""
    async def _run():
        session = await _ensure_initialized()
        return await session.evaluate(code)
    return asyncio.run(_run())


def browser_tabs_sync(action: str, index: Optional[int] = None, url: Optional[str] = None) -> Dict[str, Any]:
    """Manage tabs (sync)"""
    async def _run():
        session = await _ensure_initialized()
        return await session.manage_tabs(action, index, url)
    return asyncio.run(_run())


def browser_resize_sync(width: int, height: int) -> Dict[str, Any]:
    """Resize browser (sync)"""
    async def _run():
        session = await _ensure_initialized()
        return await session.resize(width, height)
    return asyncio.run(_run())


def browser_wait_for_sync(selector: str, timeout: int = 30000, state: str = "visible") -> Dict[str, Any]:
    """Wait for element (sync)"""
    async def _run():
        session = await _ensure_initialized()
        return await session.wait_for(selector, timeout, state)
    return asyncio.run(_run())


def browser_drag_sync(source_ref: str, target_ref: str) -> Dict[str, Any]:
    """Drag and drop (sync)"""
    async def _run():
        session = await _ensure_initialized()
        return await session.drag(source_ref, target_ref)
    return asyncio.run(_run())


def close_browser_session():
    """Close browser session"""
    global _session
    if _session:
        asyncio.run(_session.close())
        _session = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_available_tools() -> List[str]:
    """Get list of all available Playwright tools"""
    return [tool.value for tool in BrowserAction]


def get_tool_info(tool_name: str) -> Optional[PlaywrightTool]:
    """Get info about a specific tool"""
    for action, tool in PLAYWRIGHT_TOOLS.items():
        if tool.name == tool_name:
            return tool
    return None


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("🎭 Playwright MCP Client for JARVIS")
    print("=" * 50)
    print(f"Available tools: {len(PLAYWRIGHT_TOOLS)}")
    print()
    
    for action, tool in PLAYWRIGHT_TOOLS.items():
        params = tool.required_params + [f"{p}?" for p in tool.optional_params]
        params_str = ", ".join(params) if params else "none"
        print(f"  {tool.name}: {tool.description}")
        print(f"    Params: {params_str}")
        print()
