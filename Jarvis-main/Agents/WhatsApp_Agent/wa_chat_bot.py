"""
WhatsApp Chat Bot Module for JARVIS
Enables LLM-powered automated conversations on WhatsApp.

Uses Playwright (same as wa_web_automator) for reliability.

Modes:
- DRAFT: Read message, generate reply, paste (no send)
- SINGLE: Read message, generate reply, paste, send once
- LOOP: Auto-reply loop until 30 second timeout

Updated for WhatsApp Web 2025/2026 frontend changes.
"""

import time
import threading
from typing import Optional, List, Dict
from enum import Enum

# Global state
_active_session = False
_stop_requested = False

# Timeout for loop mode
LOOP_TIMEOUT_SECONDS = 60


class ChatMode(Enum):
    DRAFT = "draft"      # Paste only, don't send
    SINGLE = "single"    # Send once, then stop
    LOOP = "loop"        # Auto-reply loop


class WhatsAppChatBot:
    """WhatsApp Chat Bot using Playwright for reliable automation."""
    
    def __init__(self):
        from Agents.WhatsApp_Agent.wa_web_automator import WhatsAppWebAutomator
        from Agents.WhatsApp_Agent.intent_analyzer import IntentAnalyzer
        from Agents.WhatsApp_Agent.context_validator import ContextValidator
        from Agents.WhatsApp_Agent.reply_generator import ReplyGenerator
        
        self.automator = WhatsAppWebAutomator(headless=False)
        self.user_context = None  # Store user's intent/context
        
        # Initialize 3-stage pipeline
        self.intent_analyzer = IntentAnalyzer()
        self.context_validator = ContextValidator()
        self.reply_generator = ReplyGenerator()
        self.conversation_history = {}  # Track conversation per contact
        
    def read_recent_messages(self, count: int = 5) -> str:
        """
        Read last N INCOMING messages from current chat.
        
        Uses confirmed WhatsApp Web DOM structure (Feb 2026):
        - .message-in = incoming messages, .message-out = outgoing
        - [data-pre-plain-text] = message metadata (sender, time)
        - [data-id] starting with 'true_' = incoming, 'false_' = outgoing
        - span[dir] contains text but ALSO timestamps
        """
        try:
            if not self.automator.page:
                print("[ChatBot] No page available")
                return ""
            
            page = self.automator.page
            
            # Wait for messages to render - WhatsApp needs ~5-8s after URL nav
            time.sleep(3)
            
            # Strategy 1: Use data-pre-plain-text + message-in (BEST approach)
            # data-pre-plain-text contains "[time, date] Sender: " metadata
            # The element's textContent has the actual message text + timestamp
            js_code = """
                (count) => {
                    const messages = [];
                    
                    // Find incoming messages with data-pre-plain-text
                    const containers = document.querySelectorAll('.message-in [data-pre-plain-text], [class*="message-in"] [data-pre-plain-text]');
                    
                    containers.forEach(el => {
                        // Get all span[dir] children - these have the text
                        const spans = el.querySelectorAll('span[dir="ltr"], span[dir="rtl"]');
                        const textParts = [];
                        
                        spans.forEach(span => {
                            const text = span.textContent?.trim();
                            if (!text) return;
                            
                            // Filter out timestamps (e.g., "6:29 pm", "12:08 am")
                            if (/^\d{1,2}:\d{2}\s*(am|pm|AM|PM)?$/.test(text)) return;
                            // Filter out dates
                            if (/^\d{1,2}\/\d{1,2}\/\d{2,4}$/.test(text)) return;
                            // Filter out metadata words
                            if (['Forwarded', 'forwarded', 'Edited', 'Read', 'Delivered', 'You'].includes(text)) return;
                            // Filter out very short or very long
                            if (text.length < 1 || text.length > 500) return;
                            
                            textParts.push(text);
                        });
                        
                        if (textParts.length > 0) {
                            messages.push(textParts.join(' '));
                        }
                    });
                    
                    // Return last N messages
                    return messages.slice(-count);
                }
            """
            
            try:
                messages = page.evaluate(js_code, count)
                if messages and len(messages) > 0:
                    result = "\n".join(messages)
                    print(f"[ChatBot] Read {len(messages)} incoming messages")
                    return result
            except Exception as e:
                print(f"[ChatBot] Strategy 1 failed: {e}")
            
            # Strategy 2: Use data-id attribute (true_ = incoming)
            try:
                fallback_js = """
                    (count) => {
                        const messages = [];
                        
                        // data-id starting with 'true_' = incoming messages
                        const allMsgs = document.querySelectorAll('[data-id^="true_"]');
                        
                        allMsgs.forEach(el => {
                            const spans = el.querySelectorAll('span[dir="ltr"], span[dir="rtl"]');
                            const textParts = [];
                            
                            spans.forEach(span => {
                                const text = span.textContent?.trim();
                                if (!text) return;
                                if (/^\d{1,2}:\d{2}\s*(am|pm|AM|PM)?$/.test(text)) return;
                                if (/^\d{1,2}\/\d{1,2}\/\d{2,4}$/.test(text)) return;
                                if (['Forwarded', 'forwarded', 'Edited', 'You'].includes(text)) return;
                                if (text.length < 1 || text.length > 500) return;
                                textParts.push(text);
                            });
                            
                            if (textParts.length > 0) {
                                messages.push(textParts.join(' '));
                            }
                        });
                        
                        return messages.slice(-count);
                    }
                """
                fallback_messages = page.evaluate(fallback_js, count)
                if fallback_messages and len(fallback_messages) > 0:
                    result = "\n".join(fallback_messages)
                    print(f"[ChatBot] Strategy 2 read {len(fallback_messages)} incoming messages")
                    return result
            except Exception as e:
                print(f"[ChatBot] Strategy 2 failed: {e}")
            
            # Strategy 3: Broad message-in span extraction (last resort)
            try:
                broad_js = """
                    (count) => {
                        const messages = [];
                        const incoming = document.querySelectorAll('.message-in, [class*="message-in"]');
                        
                        incoming.forEach(row => {
                            const spans = row.querySelectorAll('span');
                            spans.forEach(span => {
                                const text = span.textContent?.trim();
                                if (text && text.length > 2 && text.length < 300 &&
                                    !/^\d{1,2}:\d{2}\s*(am|pm|AM|PM)?$/.test(text) &&
                                    span.children.length === 0) {
                                    messages.push(text);
                                }
                            });
                        });
                        
                        return [...new Set(messages)].slice(-count);
                    }
                """
                broad_messages = page.evaluate(broad_js, count)
                if broad_messages:
                    result = "\n".join(broad_messages)
                    print(f"[ChatBot] Strategy 3 read {len(broad_messages)} messages")
                    return result
            except:
                pass
            
            print("[ChatBot] No incoming messages found with any strategy")
            return ""
            
        except Exception as e:
            print(f"[ChatBot] Error reading messages: {e}")
            return ""
    
    def generate_reply(self, messages: str, contact_name: str, topic: Optional[str] = None) -> str:
        """
        Generate intelligent reply using 3-stage pipeline:
        1. Intent Analysis - What are they asking?
        2. Context Validation - Can we answer it?
        3. Reply Generation - Craft human-like response
        
        Returns:
            Generated reply, or "__BYE__" signal if conversation should end
        """
        try:
            # Get last message for analysis
            last_msg = ""
            if messages:
                lines = [l.strip() for l in messages.strip().split('\n') if l.strip()]
                if lines:
                    last_msg = lines[-1]
            
            if not last_msg:
                print("[ChatBot] No message to reply to")
                return "Hey"
            
            # Get conversation history for this contact
            chat_history = self.conversation_history.get(contact_name, "")
            
            # STAGE 1: Intent Analysis
            print(f"[ChatBot] Stage 1: Analyzing intent...")
            intent = self.intent_analyzer.analyze(last_msg, chat_history)
            print(f"[ChatBot] Intent: {intent.intent_type}, Farewell: {intent.is_farewell}")
            
            # Check for farewell - signal to end conversation
            if intent.is_farewell:
                print("[ChatBot] Farewell detected - ending conversation")
                self.conversation_history[contact_name] = chat_history + f"\nThem: {last_msg}\nYou: bye"
                return "__BYE__"
            
            # STAGE 2: Context Validation
            print(f"[ChatBot] Stage 2: Validating context coverage...")
            context_coverage = self.context_validator.validate(
                last_msg,
                self.user_context,
                intent.intent_type
            )
            print(f"[ChatBot] Coverage: {context_coverage.coverage}")
            
            # STAGE 3: Reply Generation
            print(f"[ChatBot] Stage 3: Generating reply...")
            reply = self.reply_generator.generate(
                intent,
                context_coverage,
                self.user_context,
                last_msg,
                contact_name
            )
            
            # Validate reply
            if not self.reply_generator.validate_reply(reply):
                print("[ChatBot] Reply validation failed, using fallback")
                reply = context_coverage.suggested_fallback or "I'll let you know"
            
            # Update conversation history
            self.conversation_history[contact_name] = chat_history + f"\nThem: {last_msg}\nYou: {reply}"
            
            # Trim history if too long (keep last 10 exchanges)
            history_lines = self.conversation_history[contact_name].split('\n')
            if len(history_lines) > 20:
                self.conversation_history[contact_name] = '\n'.join(history_lines[-20:])
            
            print(f"[ChatBot] Generated: {reply}")
            return reply
            
        except Exception as e:
            print(f"[ChatBot] Pipeline error: {e}")
            import traceback
            traceback.print_exc()
            return "Hey, just saw this"
    
    def type_message(self, message: str) -> bool:
        """Type message into chat input using the automator's smart finder."""
        try:
            page = self.automator.page
            if not page:
                return False
            
            # Use the automator's smart find to get the message input
            input_el = self.automator.get_message_input()
            
            if input_el:
                # Use the automator's robust typing method
                success = self.automator._type_into_element(input_el, message, clear_first=True)
                if success:
                    print(f"[ChatBot] Typed: {message[:50]}...")
                    return True
            
            # Ultimate fallback: Use keyboard-based approach
            print("[ChatBot] Smart find failed, trying keyboard approach...")
            try:
                # Click on the chat area first
                page.click('#main', timeout=3000)
                time.sleep(0.2)
                # Tab to reach the input field
                page.keyboard.press("Tab")
                time.sleep(0.1)
                page.keyboard.type(message, delay=15)
                print(f"[ChatBot] Keyboard typed: {message[:50]}...")
                return True
            except Exception as kb_err:
                print(f"[ChatBot] Keyboard approach failed: {kb_err}")
            
            return False
            
        except Exception as e:
            print(f"[ChatBot] Type error: {e}")
            return False
    
    def send_message(self) -> bool:
        """Press Enter or click Send button."""
        try:
            page = self.automator.page
            if not page:
                return False
            
            # Try pressing Enter first (most reliable)
            page.keyboard.press("Enter")
            time.sleep(0.3)
            print("[ChatBot] Message sent")
            return True
            
        except Exception as e:
            print(f"[ChatBot] Send error: {e}")
            return False
    
    def get_last_message_hash(self) -> str:
        """Get a hash of the last message for change detection."""
        messages = self.read_recent_messages(1)
        return hash(messages)
    
    def chat_session(
        self,
        contact: str,
        mode: ChatMode,
        topic: Optional[str] = None,
        timeout_seconds: int = LOOP_TIMEOUT_SECONDS
    ) -> Dict:
        """
        Main chat session handler.
        
        Args:
            contact: Contact name
            mode: ChatMode (DRAFT, SINGLE, or LOOP)
            topic: Optional conversation topic
            timeout_seconds: Timeout for LOOP mode (default 30s)
        """
        global _active_session, _stop_requested
        
        from Agents.WhatsApp_Agent.contact_manager import ContactManager
        from TextToSpeech.Fast_DF_TTS import speak
        
        print(f"[ChatBot] Starting {mode.value} session with {contact}")
        print(f"[ChatBot] Timeout: {timeout_seconds}s")
        
        # Resolve contact
        contact_manager = ContactManager()
        contact_result = contact_manager.resolve(contact)
        
        if not contact_result.get("found"):
            threading.Thread(target=speak, args=(f"Contact {contact} not found",), daemon=True).start()
            return {"success": False, "error": f"Contact '{contact}' not found"}
        
        phone = contact_result["contact"]["phone"]
        contact_name = contact_result["contact"]["name"]
        
        try:
            # Open chat using existing automator
            result = self.automator.open_chat(phone, contact_name=contact_name)
            if not result.get("success"):
                error = result.get('error', 'Unknown error')
                print(f"[ChatBot] [X] Failed to open chat: {error}")
                threading.Thread(target=speak, args=(f"Sorry, couldn't open chat with {contact_name}. {error}",), daemon=True).start()
                return {"success": False, "error": f"Failed to open chat: {error}"}
            
            time.sleep(6)  # Wait for chat to fully load (messages need ~5-8s)
            
            _active_session = True
            _stop_requested = False
            messages_sent = 0
            
            threading.Thread(target=speak, args=(f"Opened chat with {contact_name}",), daemon=True).start()
            
            if mode == ChatMode.LOOP:
                # Auto-reply loop
                last_hash = self.get_last_message_hash()
                last_activity = time.time()
                
                # First reply immediately
                messages = self.read_recent_messages(5)
                reply = self.generate_reply(messages, contact_name, topic)
                
                if self.type_message(reply):
                    self.send_message()
                    messages_sent += 1
                    threading.Thread(target=speak, args=(f"Sent",), daemon=True).start()
                    last_activity = time.time()
                
                # Then loop for new messages
                while not _stop_requested and (time.time() - last_activity < timeout_seconds):
                    time.sleep(2)  # Check every 2 seconds
                    
                    current_hash = self.get_last_message_hash()
                    if current_hash != last_hash:
                        # New message detected
                        time.sleep(1)  # Brief wait for message to fully load
                        messages = self.read_recent_messages(5)
                        reply = self.generate_reply(messages, contact_name, topic)
                        
                        # Check for bye signal
                        if reply == "__BYE__":
                            last_msg = messages.split('\n')[-1] if messages else ""
                            farewell = self.reply_generator._generate_farewell_reply(last_msg, None)
                            if self.type_message(farewell):
                                self.send_message()
                                messages_sent += 1
                            threading.Thread(target=speak, args=(f"Ended chat - they said {last_msg[:20]}",), daemon=True).start()
                            break
                        
                        if self.type_message(reply):
                            self.send_message()
                            messages_sent += 1
                            threading.Thread(target=speak, args=(f"Replied",), daemon=True).start()
                        
                        last_hash = self.get_last_message_hash()
                        last_activity = time.time()
                
                print(f"[ChatBot] Session ended. Sent {messages_sent} messages.")
                threading.Thread(target=speak, args=(f"Chat session ended. Sent {messages_sent} messages.",), daemon=True).start()
                
            else:
                # DRAFT or SINGLE mode - one reply
                messages = self.read_recent_messages(5)
                reply = self.generate_reply(messages, contact_name, topic)
                
                if self.type_message(reply):
                    if mode == ChatMode.SINGLE:
                        self.send_message()
                        messages_sent = 1
                        threading.Thread(target=speak, args=(f"Sent reply to {contact_name}",), daemon=True).start()
                    else:
                        # DRAFT mode
                        threading.Thread(target=speak, args=(f"Reply drafted. Send when ready.",), daemon=True).start()
                else:
                    return {"success": False, "error": "Failed to type message"}
            
            _active_session = False
            
            return {
                "success": True,
                "contact": contact_name,
                "mode": mode.value,
                "messages_sent": messages_sent
            }
            
        except Exception as e:
            _active_session = False
            print(f"[ChatBot] Error: {e}")
            return {"success": False, "error": str(e)}
    
    def close(self):
        """Close the browser."""
        if self.automator:
            self.automator.close()


def stop_chat() -> Dict:
    """Stop the current chat session."""
    global _stop_requested
    _stop_requested = True
    print("[ChatBot] Stop requested")
    return {"success": True, "message": "Chat session stopped"}


def is_session_active() -> bool:
    """Check if a chat session is currently active."""
    return _active_session


# Singleton instance
_bot_instance = None

def get_chat_bot() -> WhatsAppChatBot:
    """Get or create singleton chat bot instance."""
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = WhatsAppChatBot()
    return _bot_instance


def reply_to_chat_sync(contact: str, mode: str = "single", topic: str = None) -> Dict:
    """Sync wrapper for chat_session."""
    mode_map = {
        "draft": ChatMode.DRAFT,
        "single": ChatMode.SINGLE,
        "loop": ChatMode.LOOP,
        "manual": ChatMode.DRAFT,
        "auto": ChatMode.LOOP
    }
    chat_mode = mode_map.get(mode.lower(), ChatMode.SINGLE)
    
    bot = get_chat_bot()
    return bot.chat_session(contact, chat_mode, topic)
