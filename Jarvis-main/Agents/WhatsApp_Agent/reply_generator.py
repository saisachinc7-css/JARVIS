"""
Reply Generator for WhatsApp Chat Bot
Generates human-like responses with dynamic length control and no AI language.
"""

from typing import Optional
from Agents.WhatsApp_Agent.intent_analyzer import IntentAnalysis
from Agents.WhatsApp_Agent.context_validator import ContextCoverage


class ReplyGenerator:
    """Generates human-like WhatsApp replies with strict context adherence."""
    
    # Banned AI-like phrases that should never appear in responses
    BANNED_PHRASES = [
        "as an ai",
        "i'm an ai",
        "i don't have the ability",
        "i cannot",
        "i apologize for the confusion",
        "certainly",
        "i'd be happy to",
        "my apologies",
        "unfortunately, i",
        "as a language model",
        "i'm not able to"
    ]
    
    # Natural casual responses for common situations
    CASUAL_CONFIRMATIONS = ["yep", "yeah", "sure", "okay", "alright", "cool", "👍"]
    CASUAL_FAREWELLS = ["bye", "later", "talk later", "ttyl", "see ya", "peace"]
    
    def __init__(self):
        """Initialize the reply generator."""
        pass
    
    def generate(
        self,
        intent: IntentAnalysis,
        context_coverage: ContextCoverage,
        user_context: Optional[str],
        recipient_message: str,
        contact_name: str
    ) -> str:
        """
        Generate human-like reply based on all analysis.
        
        Args:
            intent: Intent analysis result
            context_coverage: Context validation result
            user_context: User's provided context
            recipient_message: The recipient's message
            contact_name: Name of the contact
            
        Returns:
            Generated reply text
        """
        try:
            # FORCE LLM for everything - User requested NO static replies
            # if intent.is_farewell: ... (REMOVED)
            # if intent.intent_type == "CONFIRMATION": ... (REMOVED)
            # if intent.intent_type == "GREETING": ... (REMOVED)
            
            # If context doesn't cover the question, use fallback
            if context_coverage.coverage == "NONE":
                # Even for fallback, try to be dynamic if possible, but safely
                return context_coverage.suggested_fallback or "I'll let you know"
            
            # Generate full reply using LLM
            return self._generate_llm_reply(
                intent, 
                context_coverage, 
                user_context, 
                recipient_message,
                contact_name
            )
            
        except Exception as e:
            print(f"[ReplyGenerator] Error: {e}")
            return "Hey, just saw this"
    
    def _generate_farewell_reply(self, message: str, intent: IntentAnalysis) -> str:
        """Generate simple farewell response."""
        msg_lower = message.lower().strip()
        
        # Match their style
        if 'later' in msg_lower:
            return "later"
        elif 'see you' in msg_lower or 'see ya' in msg_lower:
            return "see ya"
        elif 'peace' in msg_lower:
            return "peace"
        elif 'ttyl' in msg_lower:
            return "ttyl"
        else:
            return "bye"
    
    def _generate_confirmation_reply(self, message: str, intent: IntentAnalysis) -> str:
        """Generate simple confirmation response."""
        msg_lower = message.lower().strip()
        
        # Match their style
        if msg_lower in ['ok', 'okay']:
            return "okay"
        elif msg_lower in ['cool', 'nice']:
            return "cool"
        elif msg_lower in ['sure']:
            return "sure"
        elif msg_lower in ['alright', 'aight']:
            return "alright"
        else:
            return "👍"
    
    def _generate_greeting_reply(self, message: str, intent: IntentAnalysis) -> str:
        """Generate greeting response."""
        msg_lower = message.lower().strip()
        
        # Match their style
        if 'hey' in msg_lower:
            return "hey"
        elif 'yo' in msg_lower:
            return "yo"
        elif 'hi' in msg_lower:
            return "hi"
        else:
            return "hey"
    
    def _generate_llm_reply(
        self,
        intent: IntentAnalysis,
        context_coverage: ContextCoverage,
        user_context: Optional[str],
        recipient_message: str,
        contact_name: str
    ) -> str:
        """Generate full reply using LLM with strict controls."""
        try:
            import ollama
            
            # Build context string
            context_str = user_context if user_context else "general conversation"
            
            # Calculate target response length based on their message
            message_words = len(recipient_message.split())
            if message_words <= 3:
                length_instruction = "Reply with 1-5 words maximum"
            elif message_words <= 10:
                length_instruction = "Reply with 1 sentence maximum (around 8-12 words)"
            else:
                length_instruction = "Reply with 1-2 sentences maximum (around 15-25 words total)"
            
            # Coverage instruction
            if context_coverage.coverage == "PARTIAL":
                coverage_note = "The context only partially covers this. Answer what you can, and say 'I'll let you know' for the rest."
            else:
                coverage_note = "The context covers this question."
            
            # Build the prompt
            prompt = f"""You are texting {contact_name} on WhatsApp. Reply naturally like a human.

YOUR CONTEXT: {context_str}
THEIR MESSAGE: "{recipient_message}"

INTENT: {intent.summary}
THEIR TONE: {intent.tone}
CONTEXT COVERAGE: {coverage_note}

CRITICAL RULES:
1. STRICT CONTEXT: Only use information from YOUR CONTEXT. NEVER make up details.
2. OUT-OF-CONTEXT: If asked about something not in context, say "I'll let you know", "not sure yet", or "let me check"
3. LENGTH: {length_instruction}
4. BE HUMAN:
   - Use contractions (I'm, can't, don't, won't)
   - Match their casualness/formality
   - NO robotic language
   - NO AI phrases like "certainly", "I apologize", "as an AI"
5. NATURAL TEXTING:
   - Short and casual like real texting
   - Can use lowercase if appropriate
   - Can use emojis sparingly if it fits

TONE EXAMPLES:
- Them casual → You casual: "nah got work" not "No, I have work obligations"
- Them formal → You formal: "I can't make it" not "cant make it"

DO NOT:
- Start with "Hey" unless greeting
- Be overly polite/formal unless they are
- Use corporate language
- Explain too much

Generate ONLY the reply text:"""

            response = ollama.generate(
                model="llama3.1:8b",
                prompt=prompt,
                options={
                    "temperature": 0.7,  # Moderate creativity
                    "num_predict": 80,  # Limit tokens for shorter responses
                }
            )
            
            reply = response.get("response", "").strip()
            
            # Clean up
            reply = reply.strip('"\'')
            
            # Validate no banned phrases
            reply_lower = reply.lower()
            for banned in self.BANNED_PHRASES:
                if banned in reply_lower:
                    print(f"[ReplyGenerator] Banned phrase detected: {banned}")
                    return context_coverage.suggested_fallback or "I'll let you know"
            
            # Validate length (max 50 words as safety check)
            word_count = len(reply.split())
            if word_count > 50:
                print(f"[ReplyGenerator] Reply too long ({word_count} words), truncating")
                # Take first 2 sentences max
                sentences = reply.split('.')
                reply = '. '.join(sentences[:2]).strip()
                if not reply.endswith('.'):
                    reply += '.'
            
            return reply
            
        except Exception as e:
            print(f"[ReplyGenerator] LLM error: {e}")
            # Use fallback based on context coverage
            if context_coverage.suggested_fallback:
                return context_coverage.suggested_fallback
            return "Hey, just saw this"
    
    def validate_reply(self, reply: str) -> bool:
        """
        Validate that reply meets quality standards.
        
        Returns:
            True if valid, False if needs regeneration
        """
        reply_lower = reply.lower()
        
        # Check for banned phrases
        for banned in self.BANNED_PHRASES:
            if banned in reply_lower:
                return False
        
        # Check length (shouldn't be empty or too long)
        word_count = len(reply.split())
        if word_count == 0 or word_count > 60:
            return False
        
        return True


# Test function
if __name__ == "__main__":
    from Agents.WhatsApp_Agent.intent_analyzer import IntentAnalyzer, IntentAnalysis
    from Agents.WhatsApp_Agent.context_validator import ContextValidator, ContextCoverage
    
    generator = ReplyGenerator()
    
    test_cases = [
        {
            "message": "bye",
            "intent": IntentAnalysis("FAREWELL", "casual", "short", True, True, "Saying bye"),
            "coverage": ContextCoverage("FULL", "", None, None),
            "context": "I'm busy",
            "contact": "Test"
        },
        {
            "message": "ok cool",
            "intent": IntentAnalysis("CONFIRMATION", "casual", "short", False, False, "Confirming"),
            "coverage": ContextCoverage("FULL", "", None, None),
            "context": "I'm busy",
            "contact": "Test"
        },
        {
            "message": "Are you coming to the party?",
            "intent": IntentAnalysis("QUESTION_SPECIFIC", "casual", "short", True, False, "Asking about attendance"),
            "coverage": ContextCoverage("FULL", "Context covers this", None, None),
            "context": "I'm busy with work",
            "contact": "Test"
        }
    ]
    
    print("Reply Generation Test")
    print("=" * 60)
    
    for test in test_cases:
        reply = generator.generate(
            test["intent"],
            test["coverage"],
            test["context"],
            test["message"],
            test["contact"]
        )
        print(f"\nMessage: '{test['message']}'")
        print(f"Context: '{test['context']}'")
        print(f"Generated Reply: '{reply}'")
