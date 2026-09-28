"""
Context Validator for WhatsApp Chat Bot
Validates if user's provided context can answer the recipient's question.
"""

import json
from typing import Optional
from dataclasses import dataclass


@dataclass
class ContextCoverage:
    """Result of context validation."""
    coverage: str  # FULL, PARTIAL, NONE
    reasoning: str
    missing_info: Optional[str]
    suggested_fallback: Optional[str]


class ContextValidator:
    """Validates context coverage using LLM reasoning."""
    
    # Standard fallback responses for when context doesn't cover the question
    FALLBACK_RESPONSES = [
        "I'll let you know",
        "Not sure yet",
        "Let me check and get back to you",
        "I don't have that info right now",
        "I'll find out and tell you",
        "Still figuring that out"
    ]
    
    def __init__(self):
        """Initialize the context validator."""
        pass
    
    def validate(
        self, 
        recipient_message: str, 
        user_context: Optional[str], 
        intent_type: str
    ) -> ContextCoverage:
        """
        Validate if user's context can answer the recipient's question.
        
        Args:
            recipient_message: The message from the recipient
            user_context: Context provided by the user
            intent_type: Intent type from IntentAnalyzer
            
        Returns:
            ContextCoverage object with validation results
        """
        try:
            # If no context provided, or it's just a greeting/confirmation/farewell
            if not user_context or intent_type in ["GREETING", "CONFIRMATION", "FAREWELL", "CASUAL_CHAT"]:
                return ContextCoverage(
                    coverage="FULL",  # These don't need specific context
                    reasoning="Simple social interaction, no specific context needed",
                    missing_info=None,
                    suggested_fallback=None
                )
            
            # If it's not a question, context is sufficient
            if intent_type not in ["QUESTION_SPECIFIC", "QUESTION_GENERAL"]:
                return ContextCoverage(
                    coverage="FULL",
                    reasoning="Not a question requiring specific information",
                    missing_info=None,
                    suggested_fallback=None
                )
            
            import ollama
            
            prompt = f"""Check if the user's context can answer the recipient's question.

RECIPIENT'S MESSAGE: "{recipient_message}"
USER'S CONTEXT: "{user_context}"

Determine coverage level:
- FULL: Context completely answers the question or provides all needed information
- PARTIAL: Context gives some info but not complete
- NONE: Context doesn't cover this question at all

Be generous with FULL - if context is reasonably related and helpful, mark as FULL.
Only mark NONE if context is completely unrelated or missing critical information.

If NONE or PARTIAL, suggest an appropriate fallback response like:
- "I'll let you know"
- "Not sure yet"  
- "Let me check and get back to you"

Output ONLY valid JSON:
{{
  "coverage": "FULL/PARTIAL/NONE",
  "reasoning": "brief explanation why",
  "missing_info": "what info is needed" or null,
  "suggested_fallback": "appropriate fallback response" or null
}}"""

            response = ollama.generate(
                model="llama3.1:8b",
                prompt=prompt,
                options={
                    "temperature": 0.3,  # Lower temp for consistent validation
                    "num_predict": 150,
                }
            )
            
            result_text = response.get("response", "").strip()
            
            # Extract JSON
            if '{' in result_text and '}' in result_text:
                json_start = result_text.find('{')
                json_end = result_text.rfind('}') + 1
                result_text = result_text[json_start:json_end]
            
            result = json.loads(result_text)
            
            return ContextCoverage(
                coverage=result.get("coverage", "PARTIAL"),
                reasoning=result.get("reasoning", ""),
                missing_info=result.get("missing_info"),
                suggested_fallback=result.get("suggested_fallback")
            )
            
        except json.JSONDecodeError as e:
            print(f"[ContextValidator] JSON parse error: {e}")
            print(f"[ContextValidator] Response was: {result_text}")
            return self._fallback_validation(recipient_message, user_context)
        except Exception as e:
            print(f"[ContextValidator] Error: {e}")
            return self._fallback_validation(recipient_message, user_context)
    
    def _fallback_validation(self, message: str, context: Optional[str]) -> ContextCoverage:
        """Fallback validation when LLM fails."""
        if not context:
            return ContextCoverage(
                coverage="NONE",
                reasoning="No context provided",
                missing_info="All information",
                suggested_fallback="I'll let you know"
            )
        
        # Simple keyword matching
        msg_lower = message.lower()
        ctx_lower = context.lower()
        
        # Check for question words
        question_words = ['when', 'where', 'why', 'how', 'what', 'who']
        has_question = any(word in msg_lower for word in question_words)
        
        if not has_question:
            # Not a question, context is fine
            return ContextCoverage(
                coverage="FULL",
                reasoning="Not a question",
                missing_info=None,
                suggested_fallback=None
            )
        
        # Check if any words from message appear in context
        msg_words = set(msg_lower.split())
        ctx_words = set(ctx_lower.split())
        overlap = msg_words & ctx_words
        
        if len(overlap) > 2:
            coverage = "PARTIAL"
        else:
            coverage = "NONE"
        
        return ContextCoverage(
            coverage=coverage,
            reasoning=f"Simple keyword matching: {len(overlap)} words overlap",
            missing_info="Specific details" if coverage != "FULL" else None,
            suggested_fallback="Not sure yet, I'll let you know" if coverage != "FULL" else None
        )


# Test function
if __name__ == "__main__":
    validator = ContextValidator()
    
    test_cases = [
        {
            "message": "Are you coming?",
            "context": "I'm busy with work",
            "intent": "QUESTION_SPECIFIC"
        },
        {
            "message": "When will you be there?",
            "context": "I'm busy with work",
            "intent": "QUESTION_SPECIFIC"
        },
        {
            "message": "ok cool",
            "context": "I'm busy with work",
            "intent": "CONFIRMATION"
        },
        {
            "message": "What time does it start?",
            "context": None,
            "intent": "QUESTION_SPECIFIC"
        },
        {
            "message": "Why not?",
            "context": "I have a meeting at 3pm",
            "intent": "QUESTION_GENERAL"
        }
    ]
    
    print("Context Validation Test")
    print("=" * 60)
    
    for test in test_cases:
        result = validator.validate(
            test["message"], 
            test["context"], 
            test["intent"]
        )
        print(f"\nMessage: '{test['message']}'")
        print(f"Context: '{test['context']}'")
        print(f"Coverage: {result.coverage}")
        print(f"Reasoning: {result.reasoning}")
        if result.suggested_fallback:
            print(f"Fallback: {result.suggested_fallback}")
