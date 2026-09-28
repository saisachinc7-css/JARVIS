"""
Intent Analyzer for WhatsApp Chat Bot
Analyzes incoming messages to understand recipient's intent, including farewell detection.
"""

import json
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class IntentAnalysis:
    """Result of intent analysis."""
    intent_type: str  # QUESTION_SPECIFIC, QUESTION_GENERAL, CONFIRMATION, GREETING, FAREWELL, STATEMENT, CASUAL_CHAT
    tone: str  # casual, formal, urgent, friendly, neutral
    message_length: str  # short, medium, long
    expects_response: bool
    is_farewell: bool  # True if message is a goodbye/farewell
    summary: str


class IntentAnalyzer:
    """Analyzes message intent using LLM with chain-of-thought reasoning."""
    
    # Farewell keywords for quick detection
    FAREWELL_KEYWORDS = [
        'bye', 'goodbye', 'see you', 'talk later', 'gtg', 'gotta go',
        'catch you later', 'later', 'peace', 'cya', 'see ya', 'ttyl'
    ]
    
    def __init__(self):
        """Initialize the intent analyzer."""
        pass
    
    def _quick_farewell_check(self, message: str) -> bool:
        """Quick keyword-based farewell detection."""
        msg_lower = message.lower().strip()
        
        # Direct matches
        if msg_lower in ['bye', 'goodbye', 'later', 'peace', 'cya', 'ttyl']:
            return True
        
        # Keyword search
        for keyword in self.FAREWELL_KEYWORDS:
            if keyword in msg_lower:
                return True
        
        return False
    
    def analyze(self, message: str, chat_history: Optional[str] = None) -> IntentAnalysis:
        """
        Analyze message intent using LLM.
        
        Args:
            message: The incoming message to analyze
            chat_history: Optional conversation history for context
            
        Returns:
            IntentAnalysis object with classification results
        """
        try:
            # Quick farewell check first
            quick_farewell = self._quick_farewell_check(message)
            
            # If it's clearly a farewell, return immediately
            if quick_farewell:
                return IntentAnalysis(
                    intent_type="FAREWELL",
                    tone="casual",
                    message_length="short",
                    expects_response=True,  # We should say bye back
                    is_farewell=True,
                    summary="Saying goodbye"
                )
            
            import ollama
            
            history_context = f"\nCONVERSATION HISTORY: {chat_history}" if chat_history else ""
            
            prompt = f"""Analyze this WhatsApp message and determine the sender's intent.

MESSAGE: "{message}"{history_context}

Classify the message into ONE of these types:
- QUESTION_SPECIFIC: Asking about specific information (time, place, details)
- QUESTION_GENERAL: General inquiry or checking in
- CONFIRMATION: Agreeing or confirming (ok, sure, yeah)
- GREETING: Hi, hello, hey
- FAREWELL: Bye, later, talk to you soon, see you
- STATEMENT: Sharing information or an update
- CASUAL_CHAT: Small talk or light conversation

Also determine:
- Tone: [casual/formal/urgent/friendly/neutral]
- Length: [short/medium/long] (short=1-5 words, medium=6-15, long=16+)
- Expects response: [yes/no]
- Is farewell: [true/false] - True if message indicates ending conversation

Output ONLY valid JSON:
{{
  "intent_type": "...",
  "tone": "...",
  "message_length": "...",
  "expects_response": true/false,
  "is_farewell": true/false,
  "summary": "brief one-line summary"
}}"""

            response = ollama.generate(
                model="llama3.1:8b",
                prompt=prompt,
                options={
                    "temperature": 0.3,  # Lower temp for more consistent classification
                    "num_predict": 150,
                }
            )
            
            result_text = response.get("response", "").strip()
            
            # Extract JSON from response
            # Sometimes LLM adds extra text, so we extract the JSON block
            if '{' in result_text and '}' in result_text:
                json_start = result_text.find('{')
                json_end = result_text.rfind('}') + 1
                result_text = result_text[json_start:json_end]
            
            result = json.loads(result_text)
            
            return IntentAnalysis(
                intent_type=result.get("intent_type", "CASUAL_CHAT"),
                tone=result.get("tone", "casual"),
                message_length=result.get("message_length", "short"),
                expects_response=result.get("expects_response", True),
                is_farewell=result.get("is_farewell", False) or result.get("intent_type") == "FAREWELL",
                summary=result.get("summary", "")
            )
            
        except json.JSONDecodeError as e:
            print(f"[IntentAnalyzer] JSON parse error: {e}")
            print(f"[IntentAnalyzer] Response was: {result_text}")
            # Fallback to basic analysis
            return self._fallback_analysis(message)
        except Exception as e:
            print(f"[IntentAnalyzer] Error: {e}")
            return self._fallback_analysis(message)
    
    def _fallback_analysis(self, message: str) -> IntentAnalysis:
        """Fallback analysis when LLM fails."""
        msg_lower = message.lower().strip()
        
        # Check for farewell
        is_farewell = self._quick_farewell_check(message)
        
        # Simple length check
        word_count = len(message.split())
        if word_count <= 5:
            length = "short"
        elif word_count <= 15:
            length = "medium"
        else:
            length = "long"
        
        # Simple intent
        if is_farewell:
            intent = "FAREWELL"
        elif '?' in message:
            intent = "QUESTION_GENERAL"
        elif msg_lower in ['ok', 'okay', 'sure', 'yeah', 'yep', 'alright', 'cool']:
            intent = "CONFIRMATION"
        elif msg_lower in ['hi', 'hello', 'hey', 'yo']:
            intent = "GREETING"
        else:
            intent = "CASUAL_CHAT"
        
        return IntentAnalysis(
            intent_type=intent,
            tone="casual",
            message_length=length,
            expects_response=not is_farewell,
            is_farewell=is_farewell,
            summary=f"Basic analysis: {intent}"
        )


# Test function
if __name__ == "__main__":
    analyzer = IntentAnalyzer()
    
    test_messages = [
        "Are you coming to the party?",
        "ok cool",
        "bye",
        "see you later bro",
        "gtg talk later",
        "hey what's up",
        "I'm heading out in 5 mins",
        "???"
    ]
    
    print("Intent Analysis Test")
    print("=" * 60)
    
    for msg in test_messages:
        result = analyzer.analyze(msg)
        print(f"\nMessage: '{msg}'")
        print(f"Intent: {result.intent_type}")
        print(f"Tone: {result.tone}")
        print(f"Length: {result.message_length}")
        print(f"Is Farewell: {result.is_farewell}")
        print(f"Expects Response: {result.expects_response}")
