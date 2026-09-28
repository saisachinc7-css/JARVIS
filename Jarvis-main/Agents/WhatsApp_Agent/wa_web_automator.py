"""
WhatsApp Web Automator
Playwright-based browser automation for WhatsApp Web.
IMPORTANT: This NEVER sends messages automatically - only drafts them.

Updated for WhatsApp Web 2025/2026 frontend:
- Search box is now <input> (not contenteditable div)
- Message input discovered dynamically per-session
- Self-healing selectors with multi-strategy fallback
"""

import asyncio
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
import time
import json

# Fix for running sync Playwright inside asyncio loop (e.g., when MCP is active)
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass

try:
    from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("[WAWebAutomator] Playwright not installed. Run: pip install playwright && playwright install chromium")


class WhatsAppWebAutomator:
    """
    Automates WhatsApp Web using Playwright.
    
    SAFETY: This class NEVER sends messages. It only:
    1. Opens WhatsApp Web
    2. Navigates to the correct chat
    3. Types the message in the input field
    4. STOPS - leaving the human to review and send manually
    
    SELECTOR STRATEGY:
    Uses a priority-ordered list of selectors per element type.
    Selectors are based on stable attributes (aria-label, role, data-tab)
    rather than CSS classes (which WhatsApp obfuscates/changes frequently).
    """
    
    # WhatsApp Web URLs
    WA_WEB_URL = "https://web.whatsapp.com"
    WA_SEND_URL = "https://web.whatsapp.com/send?phone={phone}&text={text}"
    
    # =========================================================================
    # SELF-HEALING SELECTORS
    # Priority-ordered: most stable first, least stable last.
    # Updated Feb 2026 based on live DOM inspection.
    # =========================================================================
    SELECTORS = {
        # Search box (sidebar) - <input> element with data-tab="3"
        "search_box": [
            'input[data-tab="3"]',
            'input[placeholder*="Search"]',
            'input[role="textbox"][aria-label*="Search"]',
            '#side input[type="text"]',
            '#side [role="textbox"]',
        ],
        
        # Message input (compose area) - Lexical rich text editor
        "message_input": [
            'div[data-tab="10"][contenteditable="true"]',
            'div[data-lexical-editor="true"]',
            '[aria-placeholder="Type a message"]',
            '[role="textbox"][contenteditable="true"]',
            '#main [contenteditable="true"]',
            'footer [contenteditable="true"]',
            'footer [role="textbox"]',
            '[aria-label*="Type"][contenteditable="true"]',
        ],
        
        # QR code (login screen)
        "qr_code": [
            '[data-ref]',
            'canvas[aria-label*="Scan"]',
            'canvas[aria-label*="QR"]',
            '[aria-label*="QR"]',
            'canvas',
        ],
        
        # Chat header (contact name display)
        "chat_header": [
            '#main header span[title]',
            '#main header [role="button"] span',
            '#main header span[dir="auto"]',
        ],
        
        # Send button
        "send_button": [
            'button[data-tab="11"]',
            '[aria-label="Send"]',
            'footer button[aria-label="Send"]',
        ],
    }
    
    def __init__(self, user_data_dir: Optional[str] = None, headless: bool = False):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright is required. Install with: pip install playwright && playwright install chromium")
        
        if user_data_dir is None:
            jarvis_root = Path(__file__).parent.parent.parent
            user_data_dir = jarvis_root / "DATA" / "whatsapp_session"
        
        self.user_data_dir = Path(user_data_dir)
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self._is_running = False
        self._cached_selectors: Dict[str, str] = {}
        
    def _find_element(self, selector_key: str, timeout: int = 5000, custom_selectors: Optional[List[str]] = None):
        """Try multiple selectors and return the first match."""
        selectors = custom_selectors or self.SELECTORS.get(selector_key, [])
        
        # Try cached selector first
        if selector_key in self._cached_selectors:
            cached = self._cached_selectors[selector_key]
            try:
                element = self.page.wait_for_selector(cached, timeout=min(timeout, 3000), state="visible")
                if element:
                    return element
            except:
                del self._cached_selectors[selector_key]
        
        # Try each selector in priority order
        per_selector_timeout = max(timeout // max(len(selectors), 1), 1500)
        
        for selector in selectors:
            try:
                element = self.page.wait_for_selector(selector, timeout=per_selector_timeout, state="visible")
                if element:
                    self._cached_selectors[selector_key] = selector
                    print(f"[WAWebAutomator] Found '{selector_key}' via: {selector}")
                    return element
            except:
                continue
        
        return None
    
    def _find_element_js(self, selector_key: str) -> Optional[Any]:
        """Ultimate fallback: Use JavaScript to discover elements dynamically."""
        js_finders = {
            "message_input": """
                () => {
                    const main = document.querySelector('#main');
                    if (!main) return null;
                    const editables = main.querySelectorAll(
                        '[contenteditable="true"], input[type="text"], [role="textbox"], textarea'
                    );
                    for (const el of editables) {
                        const rect = el.getBoundingClientRect();
                        if (rect.bottom > window.innerHeight * 0.5 && rect.height > 10) {
                            return true;
                        }
                    }
                    return null;
                }
            """,
            "search_box": """
                () => {
                    const side = document.querySelector('#side');
                    if (!side) return null;
                    const input = side.querySelector('input, [role="textbox"], [contenteditable="true"]');
                    return input ? true : null;
                }
            """
        }
        
        js_code = js_finders.get(selector_key)
        if not js_code:
            return None
            
        try:
            result = self.page.evaluate(js_code)
            if result:
                if selector_key == "message_input":
                    return self.page.evaluate_handle("""
                        () => {
                            const main = document.querySelector('#main');
                            if (!main) return null;
                            const editables = main.querySelectorAll(
                                '[contenteditable="true"], input[type="text"], [role="textbox"], textarea'
                            );
                            for (const el of editables) {
                                const rect = el.getBoundingClientRect();
                                if (rect.bottom > window.innerHeight * 0.5 && rect.height > 10) {
                                    return el;
                                }
                            }
                            return null;
                        }
                    """)
                elif selector_key == "search_box":
                    return self.page.evaluate_handle("""
                        () => {
                            const side = document.querySelector('#side');
                            return side ? side.querySelector('input, [role="textbox"]') : null;
                        }
                    """)
        except Exception as e:
            print(f"[WAWebAutomator] JS finder error for {selector_key}: {e}")
        
        return None
    
    def _smart_find(self, selector_key: str, timeout: int = 10000):
        """Smart element finder: cached -> CSS selectors -> JS fallback."""
        element = self._find_element(selector_key, timeout=timeout)
        if element:
            return element
        
        print(f"[WAWebAutomator] CSS selectors failed for '{selector_key}', trying JS discovery...")
        js_element = self._find_element_js(selector_key)
        if js_element:
            print(f"[WAWebAutomator] Found '{selector_key}' via JS discovery")
            return js_element
        
        print(f"[WAWebAutomator] Could not find '{selector_key}' with any strategy")
        return None
    
    def _type_into_element(self, element, text: str, clear_first: bool = True) -> bool:
        """Type text into an element, handling Lexical editor and standard <input>."""
        try:
            el_info = self.page.evaluate("""
                (el) => {
                    if (!el) return null;
                    return {
                        tag: el.tagName,
                        isInput: el.tagName === 'INPUT' || el.tagName === 'TEXTAREA',
                        isLexical: el.hasAttribute('data-lexical-editor'),
                        isContentEditable: el.contentEditable === 'true'
                    };
                }
            """, element)
            
            if not el_info:
                return False
            
            if el_info['isInput']:
                element.click()
                time.sleep(0.1)
                if clear_first:
                    element.fill("")
                element.fill(text)
                return True
            
            # Contenteditable / Lexical editor — must use keyboard input
            element.click()
            time.sleep(0.2)
            
            if clear_first:
                self.page.keyboard.press("Control+A")
                time.sleep(0.1)
                self.page.keyboard.press("Backspace")
                time.sleep(0.1)
            
            self.page.keyboard.type(text, delay=8)
            return True
            
        except Exception as e:
            print(f"[WAWebAutomator] Type error: {e}")
            try:
                self.page.evaluate("""
                    (el) => {
                        if (!el) return;
                        el.focus();
                        const selection = window.getSelection();
                        const range = document.createRange();
                        range.selectNodeContents(el);
                        selection.removeAllRanges();
                        selection.addRange(range);
                        document.execCommand('delete', false);
                    }
                """, element)
                time.sleep(0.1)
                self.page.evaluate(f"""
                    () => {{
                        document.execCommand('insertText', false, {json.dumps(text)});
                    }}
                """)
                return True
            except Exception as e2:
                print(f"[WAWebAutomator] insertText fallback failed: {e2}")
                return False
    
    def start(self) -> bool:
        """Start the browser and navigate to WhatsApp Web."""
        # If already running and page is valid, just check login
        if self._is_running and self.page and not self.page.is_closed():
            try:
                _ = self.page.title()
                return self._check_login_status(timeout=3000)
            except:
                self._is_running = False
                self.playwright = None
                self.context = None
                self.page = None
        
        CHROME_ARGS = [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--restore-last-session',
            '--disable-session-crashed-bubble',
            '--hide-crash-restore-bubble',
        ]
        
        try:
            if self.playwright:
                try:
                    self.playwright.stop()
                except:
                    pass
                self.playwright = None
                self.context = None
                self.page = None
            
            self.playwright = sync_playwright().start()
            
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir),
                headless=self.headless,
                args=CHROME_ARGS,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 768},
                ignore_https_errors=True,
            )
            
            if self.context.pages:
                self.page = self.context.pages[0]
            else:
                self.page = self.context.new_page()
            
            self._is_running = True
            
            if "web.whatsapp.com" not in self.page.url:
                print("[WAWebAutomator] Opening WhatsApp Web...")
                self.page.goto(self.WA_WEB_URL, wait_until="domcontentloaded", timeout=60000)
            
            # Close any extra blank tabs
            for p in self.context.pages:
                if p != self.page:
                    try:
                        p.close()
                    except:
                        pass
            
            return self._check_login_status()
            
        except Exception as e:
            error_msg = str(e)
            if "asyncio" in error_msg.lower() or "thread" in error_msg.lower():
                print(f"[WAWebAutomator] Thread conflict - clearing state and retrying...")
                self._is_running = False
                self.playwright = None
                self.context = None
                self.page = None
                try:
                    try:
                        asyncio.set_event_loop(None)
                    except:
                        pass
                    
                    self.playwright = sync_playwright().start()
                    self.context = self.playwright.chromium.launch_persistent_context(
                        user_data_dir=str(self.user_data_dir),
                        headless=self.headless,
                        args=CHROME_ARGS,
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    )
                    if self.context.pages:
                        self.page = self.context.pages[0]
                    else:
                        self.page = self.context.new_page()
                    
                    self._is_running = True
                    if "web.whatsapp.com" not in self.page.url:
                        print("[WAWebAutomator] Opening WhatsApp Web...")
                        self.page.goto(self.WA_WEB_URL, wait_until="domcontentloaded", timeout=60000)
                    return self._check_login_status()
                except Exception as retry_err:
                    print(f"[WAWebAutomator] Retry failed: {retry_err}")
                    self._is_running = False
                    return False
            else:
                print(f"[WAWebAutomator] Error starting browser: {e}")
            self._is_running = False
            return False
            
    def _check_login_status(self, timeout: int = 8000) -> bool:
        """Check if WhatsApp Web is logged in."""
        try:
            search = self._find_element("search_box", timeout=timeout)
            if search:
                return True
            
            qr_element = self._find_element("qr_code", timeout=2000)
            if qr_element:
                print("[WAWebAutomator] QR code detected - please scan to log in")
                return False
            
            js_search = self._find_element_js("search_box")
            if js_search:
                return True
            
            search = self._find_element("search_box", timeout=15000)
            return search is not None
            
        except Exception as e:
            print(f"[WAWebAutomator] Error checking login: {e}")
            return False
    
    def wait_for_login(self, timeout_seconds: int = 120) -> bool:
        """Wait for user to scan QR code and log in."""
        print(f"[WAWebAutomator] Waiting up to {timeout_seconds}s for QR code scan...")
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            if self._find_element("search_box", timeout=2000):
                print("[WAWebAutomator] Login successful!")
                return True
            time.sleep(1)
        
        print("[WAWebAutomator] Login timeout - QR code not scanned")
        return False
    
    # =========================================================================
    # POPUP HANDLING (Production-grade)
    # WhatsApp shows different popups after /send?phone= navigation:
    # - "Phone number shared via url is invalid" (contains "invalid")
    # - "Continue to chat" button (valid number, not in contacts)
    # Both use div[data-animate-modal-popup="true"]
    # =========================================================================
    
    def _handle_wa_popup(self) -> str:
        """
        Check for and handle WhatsApp Web popups after URL navigation.
        
        Returns:
            'none' - No popup found
            'loading' - "Starting chat" loading indicator, waited for it
            'continued' - "Continue to chat" popup found and clicked
            'invalid' - Invalid phone number popup
            'unknown' - Unknown popup
        """
        try:
            popup = self.page.locator('div[data-animate-modal-popup="true"]').first
            if not popup.is_visible(timeout=2000):
                return "none"
            
            # Read popup text to determine what kind it is
            popup_text = ""
            try:
                popup_text = popup.inner_text(timeout=1000).lower()
            except:
                popup_text = ""
            
            print(f"[WAWebAutomator] Popup detected, text: '{popup_text[:100]}'")
            
            # Check for INVALID phone number
            if "invalid" in popup_text:
                print("[WAWebAutomator] Confirmed: invalid phone number popup")
                try:
                    ok_btn = popup.locator('div[role="button"]').first
                    if ok_btn.is_visible(timeout=1000):
                        ok_btn.click()
                        time.sleep(0.5)
                except:
                    pass
                return "invalid"
            
            # "Starting chat" = LOADING INDICATOR — do NOT click, just WAIT
            if "starting" in popup_text or "loading" in popup_text:
                print("[WAWebAutomator] Loading indicator — waiting for chat to open...")
                for i in range(15):
                    time.sleep(1)
                    try:
                        if not popup.is_visible(timeout=500):
                            print(f"[WAWebAutomator] Chat loaded after {i+1}s")
                            return "loading"
                    except:
                        print(f"[WAWebAutomator] Chat loaded after {i+1}s")
                        return "loading"
                print("[WAWebAutomator] Loading timed out after 15s")
                return "loading"
            
            # "Continue to chat" — click the link
            if "continue" in popup_text:
                print("[WAWebAutomator] 'Continue to chat' — clicking...")
                try:
                    clickable = popup.locator('a, div[role="button"], button').first
                    if clickable.is_visible(timeout=2000):
                        clickable.click()
                        time.sleep(3)
                        print("[WAWebAutomator] Clicked 'Continue to chat'")
                        return "continued"
                except Exception as e:
                    print(f"[WAWebAutomator] Click failed: {e}")
            
            # Unknown popup — wait for it to resolve, don't click anything
            print("[WAWebAutomator] Unknown popup — waiting for it to resolve...")
            time.sleep(5)
            try:
                if not popup.is_visible(timeout=500):
                    return "loading"
            except:
                return "loading"
            try:
                self.page.keyboard.press("Escape")
                time.sleep(0.5)
            except:
                pass
            return "unknown"
            
        except:
            return "none"
    
    # =========================================================================
    # SEARCH FALLBACK
    # If URL-based chat opening fails, search by contact name in sidebar.
    # =========================================================================
    
    def _open_chat_via_search(self, contact_name: str) -> bool:
        """Fallback: Open a chat by searching for contact name in sidebar."""
        try:
            print(f"[WAWebAutomator] Fallback: Searching for '{contact_name}' in sidebar...")
            
            if "web.whatsapp.com" not in self.page.url:
                self.page.goto(self.WA_WEB_URL, wait_until="domcontentloaded", timeout=30000)
                time.sleep(3)
            
            search = self._smart_find("search_box", timeout=10000)
            if not search:
                print("[WAWebAutomator] Search box not found")
                return False
            
            self._type_into_element(search, contact_name, clear_first=True)
            time.sleep(2)
            
            # Click the first matching search result
            result_selectors = [
                f'span[title*="{contact_name}" i]',
                f'span[title="{contact_name}"]',
                '#pane-side span[title]',
            ]
            
            for sel in result_selectors:
                try:
                    result = self.page.wait_for_selector(sel, timeout=3000, state="visible")
                    if result:
                        result.click()
                        time.sleep(2)
                        print(f"[WAWebAutomator] Opened chat via search: {contact_name}")
                        return True
                except:
                    continue
            
            print("[WAWebAutomator] No search results found")
            return False
            
        except Exception as e:
            print(f"[WAWebAutomator] Search fallback error: {e}")
            return False
    
    # =========================================================================
    # MAIN METHODS
    # =========================================================================
    
    def draft_message(self, phone: str, message: str) -> Dict[str, Any]:
        """Navigate to a chat and type a message WITHOUT SENDING."""
        phone = phone.replace("+", "").replace(" ", "").replace("-", "")
        
        try:
            logged_in = self.start()
            if not logged_in:
                if not self.wait_for_login():
                    return {"success": False, "error": "WhatsApp Web login required - please scan QR code"}
            
            from urllib.parse import quote
            encoded_message = quote(message)
            url = self.WA_SEND_URL.format(phone=phone, text=encoded_message)
            
            print(f"[WAWebAutomator] Navigating to draft: {url[:80]}...")
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            
            # Handle any popup (invalid number, continue to chat, etc.)
            popup_result = self._handle_wa_popup()
            if popup_result == "invalid":
                return {"success": False, "error": "WhatsApp says this phone number is invalid."}
            
            input_field = self._smart_find("message_input", timeout=20000)
            if not input_field:
                return {"success": False, "error": "Could not find message input field."}
            
            # Check if URL pre-filled the message
            try:
                current_text = self.page.evaluate("""
                    (el) => {
                        if (!el) return '';
                        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') return el.value || '';
                        return el.textContent || el.innerText || '';
                    }
                """, input_field)
                current_text = (current_text or "").strip()
            except:
                current_text = ""
            
            if not current_text or current_text != message:
                self._type_into_element(input_field, message, clear_first=True)
            
            print(f"[WAWebAutomator] Message drafted for {phone}")
            return {"success": True, "status": "Message drafted and ready for human review", "phone": phone, "message": message}
            
        except Exception as e:
            print(f"[WAWebAutomator] draft_message error: {e}")
            return {"success": False, "error": f"Automation error: {str(e)}"}
    
    def open_chat(self, phone: str, contact_name: str = "") -> Dict[str, Any]:
        """
        Open a chat without typing any message.
        Production-grade: handles popups + search-by-name fallback.
        
        Args:
            phone: Phone number (with country code, no +)
            contact_name: Optional name for search fallback
        """
        phone = phone.replace("+", "").replace(" ", "").replace("-", "")
        
        try:
            logged_in = self.start()
            if not logged_in:
                if not self.wait_for_login():
                    return {"success": False, "error": "Login required"}
            
            # === Attempt 1: URL-based navigation ===
            url = f"{self.WA_WEB_URL}/send?phone={phone}"
            print(f"[WAWebAutomator] Navigating to chat: {url}")
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            print("[WAWebAutomator] Waiting for chat to load...")
            time.sleep(4)
            
            # Handle any popup
            popup_result = self._handle_wa_popup()
            
            if popup_result == "invalid":
                # URL said invalid — try search fallback
                if contact_name and self._open_chat_via_search(contact_name):
                    if self._smart_find("message_input", timeout=10000):
                        return {"success": True, "status": f"Opened chat with {contact_name} (via search)"}
                return {"success": False, "error": f"Invalid phone number and search for '{contact_name}' failed"}
            
            if popup_result in ("continued", "loading"):
                time.sleep(2)  # Extra wait after popup resolved
            
            # Verify chat loaded
            print("[WAWebAutomator] Looking for message input field...")
            input_field = self._smart_find("message_input", timeout=15000)
            if input_field:
                print(f"[WAWebAutomator] Chat opened with {phone}")
                return {"success": True, "status": f"Opened chat with {phone}"}
            
            # === Attempt 2: Search by contact name ===
            if contact_name:
                print(f"[WAWebAutomator] URL method failed — trying search for '{contact_name}'...")
                if self._open_chat_via_search(contact_name):
                    if self._smart_find("message_input", timeout=10000):
                        return {"success": True, "status": f"Opened chat with {contact_name} (via search)"}
            
            print("[WAWebAutomator] All methods failed to open chat")
            return {"success": False, "error": "Could not open chat - all methods failed"}
                
        except Exception as e:
            print(f"[WAWebAutomator] open_chat exception: {e}")
            return {"success": False, "error": str(e)}
    
    def get_message_input(self):
        """Get the message input element in the currently open chat."""
        return self._smart_find("message_input", timeout=5000)
    
    def close(self):
        """Close the browser completely."""
        try:
            self._is_running = False
            self._cached_selectors.clear()
            if self.context:
                self.context.close()
            if self.playwright:
                self.playwright.stop()
            print("[WAWebAutomator] Browser closed")
        except:
            pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Convenience function for quick usage
def draft_whatsapp_message(phone: str, message: str) -> Dict[str, Any]:
    """
    Quick function to draft a WhatsApp message.
    Opens browser, navigates to chat, types message, returns.
    DOES NOT SEND - human must press Enter.
    """
    with WhatsAppWebAutomator() as automator:
        result = automator.draft_message(phone, message)
        if result["success"]:
            print("\n" + "="*50)
            print("MESSAGE READY FOR REVIEW")
            print("Press Enter in WhatsApp to send, or close to cancel")
            print("="*50 + "\n")
            input("Press Enter here when done...")
        return result


if __name__ == "__main__":
    print("WhatsApp Web Automator Test")
    print("=" * 40)
    
    test_phone = "YOUR_PHONE_NUMBER"
    test_message = "Hello! This is a test message from JARVIS assistant."
    
    print(f"Testing draft to: {test_phone}")
    print(f"Message: {test_message}")
    print()
    
    print("To test, uncomment the lines below and set a real phone number.")
    # result = draft_whatsapp_message(test_phone, test_message)
    # print(f"Result: {result}")
