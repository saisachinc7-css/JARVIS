"""
Intent Parser for WhatsApp Commands
Uses local Ollama LLM for natural language understanding with regex fallback.
"""

import json
import re
import requests
from typing import Optional, Dict, Any


class IntentParser:
    """
    Parse natural language commands into structured WhatsApp intents.
    Supports both Ollama LLM parsing and regex fallback.
    """
    
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.ollama_url = ollama_url
        self.model = model
        self.ollama_available = self._check_ollama()
        
    def _check_ollama(self) -> bool:
        """Check if Ollama is running and accessible."""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def parse(self, command: str) -> Dict[str, Any]:
        """
        Parse a natural language command into structured intent.
        
        Args:
            command: Natural language command like "Send a message to Ravi saying I'll be late"
            
        Returns:
            Dict with keys:
                - success: bool
                - contact: str (name or number)
                - message: str (message content)
                - error: str (if failed)
        """
        # Try LLM parsing first if available
        if self.ollama_available:
            result = self._parse_with_llm(command)
            if result.get("success"):
                return result
        
        # Fallback to regex parsing
        return self._parse_with_regex(command)
    
    def _parse_with_llm(self, command: str) -> Dict[str, Any]:
        """Parse using Ollama LLM."""
        prompt = f"""Extract WhatsApp message intent from this command. 
Return ONLY a JSON object with no additional text.

Command: "{command}"

If this is a WhatsApp/messaging command, return:
{{"contact": "<recipient name or number>", "message": "<message to send>"}}

If this is NOT a messaging command, return:
{{"error": "not_whatsapp_command"}}

JSON response:"""

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temperature for consistent parsing
                        "num_predict": 150
                    }
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result_text = response.json().get("response", "")
                # Extract JSON from response
                json_match = re.search(r'\{[^{}]*\}', result_text)
                if json_match:
                    parsed = json.loads(json_match.group())
                    if "error" in parsed:
                        return {"success": False, "error": parsed["error"]}
                    if "contact" in parsed and "message" in parsed:
                        return {
                            "success": True,
                            "contact": parsed["contact"].strip(),
                            "message": parsed["message"].strip()
                        }
        except Exception as e:
            print(f"[IntentParser] LLM parsing failed: {e}")
        
        return {"success": False, "error": "llm_parse_failed"}
    
    def _parse_with_regex(self, command: str) -> Dict[str, Any]:
        """
        Fallback regex parsing for common patterns.
        
        Supported patterns:
        - "send a message to <contact> saying <message>"
        - "message <contact> <message>"
        - "text <contact> <message>"
        - "whatsapp <contact> <message>"
        - "tell <contact> <message>"
        """
        command_lower = command.lower().strip()
        
        # Pattern 1: "send (a) message to <contact> saying/that <message>"
        pattern1 = r'send\s+(?:a\s+)?message\s+to\s+([a-zA-Z0-9\s]+?)\s+(?:saying|that|with|:)\s+(.+)'
        match = re.search(pattern1, command_lower)
        if match:
            return {
                "success": True,
                "contact": match.group(1).strip(),
                "message": match.group(2).strip()
            }
        
        # Pattern 2: "message/text/whatsapp <contact> saying/that <message>"
        pattern2 = r'(?:message|text|whatsapp|tell)\s+([a-zA-Z0-9\s]+?)\s+(?:saying|that|:)\s+(.+)'
        match = re.search(pattern2, command_lower)
        if match:
            return {
                "success": True,
                "contact": match.group(1).strip(),
                "message": match.group(2).strip()
            }
        
        # Pattern 3: "send to <contact> <message>" (simpler)
        pattern3 = r'send\s+to\s+([a-zA-Z0-9\s]+?)\s+(?:saying|that|:)?\s*(.+)'
        match = re.search(pattern3, command_lower)
        if match and len(match.group(2).strip()) > 0:
            return {
                "success": True,
                "contact": match.group(1).strip(),
                "message": match.group(2).strip()
            }
        
        # Pattern 4: "tell <contact> that/to <message>"
        pattern4 = r'tell\s+([a-zA-Z0-9\s]+?)\s+(?:that|to)\s+(.+)'
        match = re.search(pattern4, command_lower)
        if match:
            return {
                "success": True,
                "contact": match.group(1).strip(),
                "message": match.group(2).strip()
            }
        
        return {"success": False, "error": "no_pattern_matched"}
    
    def is_whatsapp_command(self, command: str) -> bool:
        """Check if a command is likely a WhatsApp/messaging command based on context."""
        command_lower = command.lower().strip()
        
        # If "whatsapp" is present, use context to decide
        has_whatsapp = "whatsapp" in command_lower or "whats app" in command_lower
        
        if has_whatsapp:
            # Action verbs that indicate application-related intent
            action_verbs = [
                "open", "send", "call", "message", "launch", "install", 
                "search", "tell", "text", "saying", "that", "to", "write", "draft"
            ]
            # If there's an action verb or indicator, it's a genuine WhatsApp command
            if any(verb in command_lower for verb in action_verbs):
                return True
            # Otherwise, it's treated as a conversational greeting "what's up"
            return False
            
        # Standard keywords that indicate messaging intent
        keywords = [
            "send message", "send a message", "message to", "text to",
            "tell", "send to"
        ]
        return any(kw in command_lower for kw in keywords)


# Convenience function for direct use
def parse_intent(command: str) -> Dict[str, Any]:
    """Parse a WhatsApp command. Returns dict with contact and message."""
    parser = IntentParser()
    return parser.parse(command)


if __name__ == "__main__":
    # Test the parser
    parser = IntentParser()
    
    test_commands = [
        "Send a message to Ravi saying I'll be late by 10 minutes",
        "Message mom that I'm on my way",
        "Tell dad to pick up groceries",
        "WhatsApp John saying meeting postponed to 3pm",
        "Send to priya saying happy birthday!",
        "Open YouTube",  # Should fail - not a WhatsApp command
    ]
    
    print("Intent Parser Test Results:")
    print("-" * 50)
    for cmd in test_commands:
        result = parser.parse(cmd)
        print(f"Command: {cmd}")
        print(f"Result: {result}")
        print("-" * 50)
