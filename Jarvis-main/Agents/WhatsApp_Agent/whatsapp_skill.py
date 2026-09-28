"""
WhatsApp Skill for JARVIS Assistant
Main orchestrator that ties together intent parsing, contact resolution, and automation.

This is an ASSISTIVE automation - it prepares messages but NEVER sends them automatically.
"""

import threading
from typing import Dict, Any, Optional
from pathlib import Path

# Import components
from Agents.WhatsApp_Agent.intent_parser import IntentParser
from Agents.WhatsApp_Agent.contact_manager import ContactManager
from Agents.WhatsApp_Agent.wa_web_automator import WhatsAppWebAutomator

# Try to import notification and TTS
try:
    from notification import Alert
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False

try:
    from TextToSpeech.Fast_DF_TTS import speak
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    def speak(text): print(f"[TTS] {text}")


class WhatsAppSkill:
    """
    WhatsApp Skill for JARVIS AI Assistant.
    
    Handles natural language commands like:
    - "Send a message to Ravi saying I'll be late"
    - "WhatsApp mom that I'm on my way"
    - "Tell Dad to pick up groceries"
    
    SAFETY: Messages are DRAFTED only - human must manually send.
    """
    
    def __init__(self):
        self.intent_parser = IntentParser()
        self.contact_manager = ContactManager()
        self.automator: Optional[WhatsAppWebAutomator] = None
        
    def can_handle(self, command: str) -> bool:
        """Check if this skill can handle the given command."""
        return self.intent_parser.is_whatsapp_command(command)
    
    def execute(self, command: str) -> Dict[str, Any]:
        """
        Execute a WhatsApp command.
        
        Args:
            command: Natural language command like "Send message to Ravi saying hello"
            
        Returns:
            Dict with execution result
        """
        print(f"[WhatsAppSkill] Processing: {command}")
        
        # Step 1: Parse intent
        intent = self.intent_parser.parse(command)
        
        if not intent.get("success"):
            # Don't speak technical error codes like "no_pattern_matched"
            error_code = intent.get('error', '')
            log_msg = f"Couldn't understand the message. ({error_code})"
            print(f"[WhatsAppSkill] {log_msg}")
            
            # User facing message
            user_msg = "Sorry, I couldn't understand the command."
            self._speak(user_msg)
            
            return {"success": False, "error": log_msg}
        
        contact_query = intent["contact"]
        message = intent["message"]
        
        print(f"[WhatsAppSkill] Parsed - Contact: '{contact_query}', Message: '{message}'")
        
        # Step 2: Resolve contact
        contact_result = self.contact_manager.resolve(contact_query)
        
        if not contact_result.get("found"):
            # Handle ambiguous matches
            if contact_result.get("ambiguous"):
                matches = contact_result.get("matches", [])
                names = [m["name"] for m in matches[:3]]
                error_msg = f"Multiple contacts found: {', '.join(names)}. Please be more specific."
                self._speak(error_msg)
                return {"success": False, "error": error_msg, "suggestions": names}
            
            # No match at all
            suggestions = contact_result.get("suggestions", [])
            if suggestions:
                error_msg = f"Contact '{contact_query}' not found. Did you mean: {', '.join(suggestions)}?"
            else:
                error_msg = f"Contact '{contact_query}' not found. Please add them to contacts.json."
            
            self._speak(error_msg)
            return {"success": False, "error": error_msg}
        
        # Got the contact
        contact = contact_result["contact"]
        phone = contact["phone"]
        contact_name = contact["name"]
        
        print(f"[WhatsAppSkill] Resolved to: {contact_name} ({phone})")
        
        # Step 3: Confirm with user (via TTS)
        confirm_msg = f"Preparing message for {contact_name}"
        self._speak(confirm_msg)
        
        # Step 4: Draft the message (DOES NOT SEND)
        # Step 4: Draft the message
        try:
            # Reuse existing automator if active, or create new one
            if not self.automator:
                self.automator = WhatsAppWebAutomator(headless=False)
            
            # This uses the optimized logic (checks if browser is already open)
            result = self.automator.draft_message(phone, message)
            
            if result.get("success"):
                # Show desktop notification
                self._notify(f"WhatsApp message ready for {contact_name}. Review and press Enter to send.")
                self._speak(f"Message ready for {contact_name}. Please review and send manually.")
                
                return {
                    "success": True,
                    "status": "Message drafted - awaiting human review",
                    "contact": contact_name,
                    "phone": phone,
                    "message": message
                }
            else:
                error_msg = result.get("error", "Failed to draft message")
                self._speak(f"Sorry, couldn't prepare the message. {error_msg}")
                return {"success": False, "error": error_msg}
                
        except Exception as e:
            error_msg = f"WhatsApp automation error: {str(e)}"
            self._speak(error_msg)
            # Reset automator on critical error
            self.automator = None
            return {"success": False, "error": error_msg}
    
    def _speak(self, text: str):
        """Speak text using TTS (non-blocking)."""
        if TTS_AVAILABLE:
            thread = threading.Thread(target=speak, args=(text,))
            thread.start()
        else:
            print(f"[WhatsAppSkill] {text}")
    
    def _notify(self, message: str):
        """Show desktop notification."""
        if NOTIFICATIONS_AVAILABLE:
            try:
                Alert(message)
            except:
                pass
        print(f"[WhatsAppSkill] NOTIFICATION: {message}")
    
    def cleanup(self):
        """Clean up resources."""
        if self.automator:
            # Don't close browser - leave it open for human to send
            pass


# Singleton instance for integration
_skill_instance: Optional[WhatsAppSkill] = None

def get_skill() -> WhatsAppSkill:
    """Get or create the WhatsApp skill instance."""
    global _skill_instance
    if _skill_instance is None:
        _skill_instance = WhatsAppSkill()
    return _skill_instance


def handle_whatsapp_command(command: str) -> Dict[str, Any]:
    """
    Main entry point for WhatsApp automation.
    Called by Automation_Brain when a WhatsApp command is detected.
    
    Args:
        command: Natural language command
        
    Returns:
        Execution result dictionary
    """
    skill = get_skill()
    return skill.execute(command)


def is_whatsapp_command(command: str) -> bool:
    """Check if a command is a WhatsApp command."""
    skill = get_skill()
    return skill.can_handle(command)


# For direct testing
if __name__ == "__main__":
    print("WhatsApp Skill Test")
    print("=" * 50)
    
    test_commands = [
        "Send a message to example saying hello world",
        "Tell test that I'll be late by 10 minutes",
        "WhatsApp demo saying meeting at 3pm",
    ]
    
    skill = WhatsAppSkill()
    
    for cmd in test_commands:
        print(f"\nCommand: {cmd}")
        print("-" * 40)
        
        # Just test parsing, not actual automation
        if skill.can_handle(cmd):
            intent = skill.intent_parser.parse(cmd)
            print(f"Intent: {intent}")
            
            if intent.get("success"):
                contact_result = skill.contact_manager.resolve(intent["contact"])
                print(f"Contact resolution: {contact_result}")
        else:
            print("Not a WhatsApp command")
        
        print("-" * 40)
