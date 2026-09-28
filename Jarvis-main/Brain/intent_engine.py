"""
Intent Engine for JARVIS Voice Assistant.
Uses Ollama llama3.1:8b for local LLM-powered intent classification.
"""

import json
import re
import sys
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fix: OLLAMA_HOST=0.0.0.0 is valid for server binding but NOT for client connections.
# Override to 127.0.0.1 so the Python ollama client can actually connect.
if os.environ.get("OLLAMA_HOST", "").strip() in ("0.0.0.0", "0.0.0.0:11434"):
    os.environ["OLLAMA_HOST"] = "127.0.0.1:11434"

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("[IntentEngine] Warning: ollama package not installed. Run: pip install ollama")

from Brain.prompts import get_intent_prompt, get_query_prompt, get_clarification_prompt


@dataclass
class IntentResult:
    """Result of intent classification."""
    intent: str
    confidence: float
    tool: Optional[str]
    params: Dict[str, Any]
    response: Optional[str]
    raw_output: str
    
    def is_action(self) -> bool:
        """Check if this intent requires executing a tool."""
        # QUERY_WEATHER uses a real tool (get_weather), so it's an action
        # MCP intents also execute real tools
        action_intents = ["PLAY_MEDIA", "OPEN_APP", "CLOSE_APP", "OPEN_WEB", "SYSTEM_CONTROL", 
                          "AUTOMATION_WHATSAPP", "AUTOMATION_WHATSAPP_CHAT", "AUTOMATION_FILE", 
                          "AUTOMATION_OBSIDIAN", "QUERY_WEATHER", "RESEARCH", "FIND_CLAUDE",
                          "QUERY_YOUTUBE", "GOOGLE_WORKSPACE", "GOOGLE_GMAIL", 
                          "GOOGLE_CALENDAR", "GOOGLE_DRIVE", "GOOGLE_SHEETS",
                          "WEB_SEARCH", "IMAGE_SEARCH", "GITHUB_SEARCH", "BROWSER_AUTOMATION"]
        return self.intent in action_intents and self.tool is not None

    
    
    def is_query(self) -> bool:
        """Check if this is a query that needs a response from LLM (not a tool)."""
        query_intents = ["QUERY_GENERAL", "GENERAL_INFORMATION", "CONVERSATION_ASSISTANT", "GENERAL_QUERY"]
        return self.intent in query_intents
    
    def is_unknown(self) -> bool:
        """Check if intent couldn't be determined."""
        return self.intent == "UNKNOWN" or self.confidence < 0.7
    
    def needs_clarification(self) -> bool:
        """Check if we need to ask user for clarification."""
        return self.is_unknown() and self.confidence < 0.5


class IntentEngine:
    """
    LLM-powered intent classification engine using Ollama.
    
    Uses qwen3:4b for everything:
    - Intent classification via generate() with format=json + thinking
    - Natural responses via 3-stage _generate_natural():
      1. generate() with 2000 token budget (response field)
      2. Extract quoted answer from thinking field
      3. chat() fallback with _clean_response()
    """
    
    MODEL = "qwen2.5:0.5b"  # Single model for everything
    TEMPERATURE = 0.2    # Low temperature for deterministic classification
    CONFIDENCE_THRESHOLD = 0.7
    
    @staticmethod
    def _strip_think_tags(text: str) -> str:
        """Strip <think>...</think> tags from qwen3 responses (safety net)."""
        import re
        return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    
    @staticmethod
    def _clean_response(text: str) -> str:
        """Strip reasoning/thinking boilerplate from qwen3 responses."""
        import re
        
        if not text:
            return text
        
        # Strip think tags
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        
        # Reasoning indicators
        reasoning_words = [
            'we are given', "let's", 'okay,', 'hmm', 'i should',
            'approach:', 'brainstorm', 'key point', 'strategy:', 'option:',
            'draft:', 'based on the data', 'the user asked', 'the user said',
            'the user is', 'we need to', 'to be precise', 'craft a',
        ]
        
        text_lower = text.lower()
        has_reasoning = any(w in text_lower for w in reasoning_words)
        
        if not has_reasoning and len(text) < 500:
            return text
        
        # Look for quoted final response
        quoted = re.findall(r'["\u201c]([^"\u201d]{15,})["\u201d]', text)
        if quoted:
            for candidate in reversed(quoted):
                candidate = candidate.strip()
                if len(candidate) > 20 and not any(w in candidate.lower() for w in ['we are', 'the user']):
                    return candidate
        
        # Split by reasoning markers
        markers = [
            r'\*?\*?Draft\*?\*?:', r'\*?\*?Final\*?\*?:', r'\*?\*?Response\*?\*?:',
            r'\*?\*?Answer\*?\*?:', r'\*?\*?Option\*?\*?:', r'Alternative\s*\d*:',
            r"Let'?s craft.*?:", r"(?:Here'?s|My|The)\s+(?:reply|response|answer):",
        ]
        
        for marker in markers:
            parts = re.split(marker, text, flags=re.IGNORECASE)
            if len(parts) > 1:
                candidate = parts[-1].strip().strip('"\u201c\u201d').strip()
                if len(candidate) > 10:
                    return candidate
        
        # Line-by-line cleanup
        lines = text.split('\n')
        clean_lines = []
        for line in lines:
            s = line.strip()
            if not s:
                continue
            sl = s.lower()
            if re.match(r'^[-*\u2022]\s', s) or re.match(r'^\d+\.\s', s):
                continue
            if any(w in sl for w in reasoning_words):
                continue
            if re.match(r'^(?:We |The user|I should|I need|Looking)', s, re.IGNORECASE):
                continue
            clean_lines.append(s)
        
        result = ' '.join(clean_lines).strip()
        return result if len(result) >= 10 else text
    
    @staticmethod
    def _is_good_answer(text: str) -> bool:
        """Check if text looks like a real answer vs reasoning overflow."""
        if not text or len(text.strip()) < 15:
            return False
        t = text.strip().lower()
        # Reasoning overflow patterns
        junk = ['i think', 'however', "so i'll", 'the problem', 'i need to',
                'so, the final', 'wait,', 'actually,', 'i should',
                "let me", "let's", 'output:', 'the user', 'but ', 'note:',
                'after thinking', "that's", 'never ', 'we are', 'we want']
        if any(t.startswith(w) or t.startswith('. ' + w) for w in junk):
            return False
        # Too short AND starts with period/comma = fragment
        if len(text.strip()) < 30 and text.strip()[0] in '.,:;':
            return False
        return True
    
    @staticmethod
    def _extract_from_thinking(thinking: str) -> str:
        """Extract the final answer from qwen3's thinking/reasoning chain.
        
        qwen3 wraps candidate answers in quotes during its reasoning, e.g.:
        'I choose: "Sir, the weather is perfect for a long ride!"'
        The last such quoted text is typically the final answer.
        """
        import re
        if not thinking:
            return ""
        
        # Find ALL quoted strings in the thinking (both "" and "")
        quoted = re.findall(r'["\u201c]([^"\u201d]{15,})["\u201d]', thinking)
        
        if quoted:
            # Return the LAST quoted string that looks like a conversational answer
            for candidate in reversed(quoted):
                candidate = candidate.strip()
                if len(candidate) < 15:
                    continue
                cl = candidate.lower()
                # Skip quotes that are clearly reasoning/meta
                if any(w in cl for w in ['the user', 'we are', 'the instruction',
                                          'reasoning', 'i think', 'note:']):
                    continue
                return candidate
        
        # Fallback: look for text after final-answer markers
        markers = [
            r'Final reply:\s*', r'I choose:\s*', r'Final decision:\s*',
            r'My reply:\s*', r'My response:\s*', r'Final answer:\s*',
        ]
        for marker in markers:
            match = re.search(marker + r'(.+?)(?:\n\n|\Z)', thinking, re.DOTALL | re.IGNORECASE)
            if match:
                candidate = match.group(1).strip().strip('""\u201c\u201d').strip()
                if len(candidate) > 15:
                    return candidate
        
        return ""
    
    def _generate_natural(self, prompt: str, temperature: float = 0.5, max_tokens: int = 200) -> str:
        """Generate a natural response from qwen3.
        
        3-stage strategy:
        1. ollama.generate() with 2000 token budget — response field is cleanest
        2. Extract quoted final answer from thinking field
        3. ollama.chat() fallback with _clean_response()
        """
        # Stage 1: generate() — thinking goes to thinking field, answer to response
        try:
            resp = ollama.generate(
                model=self.model,
                prompt=prompt,
                options={"temperature": temperature, "num_predict": max_tokens}
            )
            
            if isinstance(resp, dict):
                response_text = resp.get('response', '').strip()
                thinking_text = resp.get('thinking', '').strip()
            else:
                response_text = (resp.response or '').strip()
                thinking_text = (getattr(resp, 'thinking', '') or '').strip()
            
            # Use response field if it's a valid answer
            if response_text and self._is_good_answer(response_text):
                cleaned = self._clean_response(response_text)
                if self._is_good_answer(cleaned):
                    return cleaned
            
            # Stage 2: Extract from thinking field
            if thinking_text:
                extracted = self._extract_from_thinking(thinking_text)
                if extracted and self._is_good_answer(extracted):
                    return extracted
                    
        except Exception as e:
            print(f"[IntentEngine] Generate error: {e}")
        
        # Stage 3: chat() fallback — reasoning leaks but _clean_response handles it
        try:
            # Split prompt into system + user for chat format
            parts = prompt.split('\n\n', 1)
            system_msg = parts[0] if len(parts) > 1 else "You are JARVIS, a loyal and humble assistant."
            user_msg = parts[1] if len(parts) > 1 else prompt
            
            resp = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                think=False,
                options={"temperature": temperature, "num_predict": max_tokens}
            )
            
            content = resp.get("message", {}).get("content", "") if isinstance(resp, dict) else resp.message.content
            cleaned = self._clean_response(content.strip())
            if self._is_good_answer(cleaned):
                return cleaned
                
        except Exception as e:
            print(f"[IntentEngine] Chat fallback error: {e}")
        
        return ""
    
    @staticmethod
    def _extract_response(resp) -> str:
        """Extract response text from ollama generate result.
        
        With qwen3 thinking mode, ollama v0.6.1 puts reasoning in a separate
        'thinking' field while 'response' may be empty. This handles both cases.
        """
        # Try response field first (works for non-thinking models)
        if isinstance(resp, dict):
            text = resp.get("response", "")
        elif hasattr(resp, 'response'):
            text = resp.response or ""
        else:
            text = ""
        
        # If response is empty, check thinking field (qwen3 thinking mode)
        if not text.strip():
            if isinstance(resp, dict):
                text = resp.get("thinking", "")
            elif hasattr(resp, 'thinking'):
                text = resp.thinking or ""
        
        # Strip any <think> tags as safety net
        import re
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        return text
    
    def __init__(self, model: str = None):
        """
        Initialize the intent engine.
        
        Args:
            model: Optional override for the Ollama model name
        """
        self.model = model or self.MODEL
        self._ollama_available = OLLAMA_AVAILABLE
        self._connection_tested = False
        self._connection_ok = False
    
    def is_available(self) -> bool:
        """Check if Ollama is available and the model is loaded."""
        if not self._ollama_available:
            return False
        
        if not self._connection_tested:
            self._connection_ok = self._test_connection()
            self._connection_tested = True
        
        return self._connection_ok
    
    def _test_connection(self) -> bool:
        """Test connection to Ollama server."""
        try:
            result = ollama.list()
            
            # Handle both old dict-style and new object-style API (ollama>=0.4)
            if hasattr(result, 'models'):
                model_list = result.models  # New object-style
            elif isinstance(result, dict):
                model_list = result.get('models', [])  # Old dict-style
            else:
                model_list = []
            
            # Get model names - handle both object attrs and dict keys
            model_names = []
            for m in model_list:
                if hasattr(m, 'model'):
                    name = m.model  # New: object attribute
                elif isinstance(m, dict):
                    name = m.get('model') or m.get('name', '')
                else:
                    name = str(m)
                if name:
                    model_names.append(name)
            
            # Check if our EXACT model is available (strict matching)
            target = self.model.lower()
            for name in model_names:
                name_lower = name.lower()
                # Exact match: "qwen3:4b" == "qwen3:4b" or "qwen3:4b:latest"
                if name_lower == target or name_lower.startswith(target + ":") or name_lower == target + ":latest":
                    print(f"[IntentEngine] [OK] Found model: {name}")
                    self.model = name  # Use the exact found name
                    return True
            
            print(f"[IntentEngine] Model {self.model} not found. Available: {model_names}")
            print(f"[IntentEngine] Pull it with: ollama pull {self.model}")
            return False
            
        except Exception as e:
            print(f"[IntentEngine] Ollama connection failed: {e}")
            print("[IntentEngine] Make sure Ollama is running: ollama serve")
            return False
    
    def classify(self, user_input: str) -> IntentResult:
        """
        Classify user input into an intent.
        
        Args:
            user_input: Transcribed user speech
            
        Returns:
            IntentResult with classified intent, tool, params, and confidence
        """
        if not user_input or not user_input.strip():
            return IntentResult(
                intent="UNKNOWN",
                confidence=0.0,
                tool=None,
                params={},
                response="I didn't hear anything. Could you please repeat?",
                raw_output=""
            )
        
        if not self.is_available():
            # Fallback to a basic unknown result
            return IntentResult(
                intent="UNKNOWN",
                confidence=0.0,
                tool=None,
                params={},
                response="LLM not available. Please check Ollama is running.",
                raw_output=""
            )
        
        try:
            # Build the prompt
            prompt = get_intent_prompt(user_input)
            
            # Call Ollama with JSON format enforcement
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                format="json",  # FORCE JSON OUTPUT - critical for parsing!
                options={
                    "temperature": self.TEMPERATURE,
                    "num_predict": 150,  # Fast JSON output
                }
            )
            
            raw_output = self._extract_response(response)
            
            # Parse the JSON response
            return self._parse_response(raw_output, user_input)
            
        except Exception as e:
            print(f"[IntentEngine] Classification error: {e}")
            return IntentResult(
                intent="UNKNOWN",
                confidence=0.0,
                tool=None,
                params={},
                response=f"Error processing your request: {str(e)}",
                raw_output=""
            )
    
    def _parse_response(self, raw_output: str, original_input: str) -> IntentResult:
        """Parse the LLM JSON response into an IntentResult."""
        try:
            # Clean up the output - remove any text before/after JSON
            raw_output = raw_output.strip()
            
            # Try multiple patterns to extract JSON
            json_str = None
            
            # Pattern 1: Find complete JSON object with balanced braces
            brace_count = 0
            start_idx = -1
            for i, char in enumerate(raw_output):
                if char == '{':
                    if start_idx == -1:
                        start_idx = i
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and start_idx != -1:
                        json_str = raw_output[start_idx:i+1]
                        break
            
            # Pattern 2: Simple regex if pattern 1 failed
            if not json_str:
                json_match = re.search(r'\{[^{}]*"intent"[^{}]*\}', raw_output, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
            
            # Pattern 3: Try to find JSON with nested params object
            if not json_str:
                json_match = re.search(r'\{.*?"intent".*?"params"\s*:\s*\{[^}]*\}.*?\}', raw_output, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
            
            if json_str:
                # Fix common JSON issues
                json_str = json_str.replace('\n', ' ').replace('\r', '')
                
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError:
                    # Try to fix common issues
                    # Remove trailing commas
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    data = json.loads(json_str)
                
                intent = data.get("intent", "UNKNOWN")
                confidence = float(data.get("confidence", 0.85))
                tool = data.get("tool")
                params = data.get("params", {})
                response = data.get("response")
                
                print(f"[IntentEngine] Parsed: {intent} -> {tool} ({confidence:.2f})")
                
                return IntentResult(
                    intent=intent,
                    confidence=confidence,
                    tool=tool,
                    params=params if isinstance(params, dict) else {},
                    response=response,
                    raw_output=raw_output
                )
            else:
                # Pattern 4: TRUNCATED JSON recovery
                # LLM hit token limit mid-JSON. Extract fields directly via regex.
                if '"intent"' in raw_output and start_idx != -1:
                    print(f"[IntentEngine] Truncated JSON detected, recovering...")
                    truncated = raw_output[start_idx:]
                    
                    # Extract key fields directly
                    intent_match = re.search(r'"intent"\s*:\s*"([^"]+)"', truncated)
                    conf_match = re.search(r'"confidence"\s*:\s*([0-9.]+)', truncated)
                    tool_match = re.search(r'"tool"\s*:\s*"([^"]+)"', truncated)
                    contact_match = re.search(r'"contact"\s*:\s*"([^"]+)"', truncated)
                    mode_match = re.search(r'"mode"\s*:\s*"([^"]+)"', truncated)
                    topic_match = re.search(r'"topic"\s*:\s*"([^"]+)"', truncated)
                    response_match = re.search(r'"response"\s*:\s*"([^"]+)"', truncated)
                    
                    if intent_match:
                        intent = intent_match.group(1)
                        confidence = float(conf_match.group(1)) if conf_match else 0.85
                        tool = tool_match.group(1) if tool_match else None
                        params = {}
                        if contact_match:
                            params["contact"] = contact_match.group(1)
                        if mode_match:
                            params["mode"] = mode_match.group(1)
                        if topic_match:
                            params["topic"] = topic_match.group(1)
                        response = response_match.group(1) if response_match else None
                        
                        print(f"[IntentEngine] Recovered: {intent} -> {tool} ({confidence:.2f})")
                        
                        return IntentResult(
                            intent=intent,
                            confidence=confidence,
                            tool=tool,
                            params=params,
                            response=response,
                            raw_output=raw_output
                        )
                
                print(f"[IntentEngine] No JSON found in response: {raw_output[:200]}")
                return IntentResult(
                    intent="UNKNOWN",
                    confidence=0.3,
                    tool=None,
                    params={},
                    response="I couldn't understand that. Could you rephrase?",
                    raw_output=raw_output
                )
                
        except json.JSONDecodeError as e:
            print(f"[IntentEngine] JSON parse error: {e}")
            print(f"[IntentEngine] Raw output: {raw_output[:300]}")
            return IntentResult(
                intent="UNKNOWN",
                confidence=0.3,
                tool=None,
                params={},
                response="I had trouble processing that. Could you try again?",
                raw_output=raw_output
            )
    
    def generate_answer(self, query: str) -> str:
        """
        Generate an answer for a general query.
        
        Args:
            query: The user's question
            
        Returns:
            Generated answer string
        """
        if not self.is_available():
            return "I'm sorry, I can't answer that right now. The AI service is unavailable."
        
        # Detect if this is an informational query
        is_informational = False
        informational_keywords = ["tell me about", "explain", "what is", "what are", "who is", "who was", "where is", "when is", "history of", "how does", "tell me what", "information on", "about "]
        query_lower = query.lower()
        if any(kw in query_lower for kw in informational_keywords):
            is_informational = True
            
        if is_informational:
            prompt = (
                "You are JARVIS, a loyal and humble personal assistant. "
                "Provide a comprehensive, informative, and detailed answer. Explain fully and clearly. "
                "Speak naturally like a human assistant, but do not restrict yourself to 1-3 sentences. "
                "Use 'sir' occasionally.\n\n"
                f"User: {query}\nYour reply:"
            )
        else:
            prompt = (
                "You are JARVIS, a loyal and humble personal assistant. "
                "Reply naturally in 1-3 sentences like a real person talking. "
                "Use 'sir' occasionally. NEVER explain your reasoning. Just answer directly.\n\n"
                f"User: {query}\nYour reply:"
            )
        
        max_tokens = 600 if is_informational else 200
        result = self._generate_natural(prompt, temperature=0.6, max_tokens=max_tokens)
        return result if result else "I'm sorry, I couldn't generate an answer right now."
    
    def generate_clarification(self, user_input: str) -> str:
        """
        Generate a clarification question for ambiguous input.
        
        Args:
            user_input: The ambiguous user input
            
        Returns:
            Clarification question string
        """
        if not self.is_available():
            return "Could you please be more specific about what you'd like me to do?"
        
        prompt = (
            "You are JARVIS, a friendly assistant. The user said something unclear. "
            "Ask ONE short clarification question in a warm, natural tone. "
            "NEVER repeat their words back. Just ask what they need.\n\n"
            f"User said: {user_input}\nYour clarification question:"
        )
        result = self._generate_natural(prompt, temperature=0.7, max_tokens=100)
        return result if result else "I'm not sure what you mean. Could you please rephrase?"
    
    def generate_tool_response(self, user_question: str, tool_data: str) -> str:
        """
        Generate a conversational response based on tool data.
        
        Args:
            user_question: The user's original question
            tool_data: Data returned by the tool
            
        Returns:
            Conversational response string
        """
        if not self.is_available():
            return tool_data
        
        prompt = (
            "You are JARVIS, a loyal, humble, and caring personal assistant. "
            "Reply naturally in 1-2 sentences like a real person talking. "
            "Use 'sir' occasionally. You MUST use the provided Tool data to answer their question. "
            "Do NOT say you don't have access to live data, because the Tool data IS the live data. "
            "NEVER repeat the question. NEVER say 'based on the data' or explain reasoning.\n\n"
            f"Tool data: {tool_data}\n\nUser's question: {user_question}\nYour reply:"
        )
        result = self._generate_natural(prompt, temperature=0.6)
        if result:
            # Guard: if the LLM echoed back its own system prompt / instructions,
            # discard it and fall back to the raw tool data.
            leaked_fragments = ["MUST use", "provided Tool data", "NEVER repeat",
                                "Tool data:", "explain reasoning", "loyal and humble"]
            if any(frag.lower() in result.lower() for frag in leaked_fragments):
                print(f"[IntentEngine] Discarded leaked prompt from response")
                return tool_data
            print(f"[IntentEngine] Conversational response: {result[:100]}...")
            return result
        return tool_data


# Global engine instance
_engine: Optional[IntentEngine] = None


def get_engine() -> IntentEngine:
    """Get the global intent engine instance."""
    global _engine
    if _engine is None:
        _engine = IntentEngine()
    return _engine


if __name__ == "__main__":
    # Test the intent engine
    import argparse
    
    parser = argparse.ArgumentParser(description="Test JARVIS Intent Engine")
    parser.add_argument("--test", type=str, help="Test input to classify")
    args = parser.parse_args()
    
    engine = get_engine()
    
    if args.test:
        print(f"\nClassifying: '{args.test}'")
        result = engine.classify(args.test)
        print(f"\nResult:")
        print(f"  Intent: {result.intent}")
        print(f"  Confidence: {result.confidence}")
        print(f"  Tool: {result.tool}")
        print(f"  Params: {result.params}")
        print(f"  Response: {result.response}")
    else:
        # Interactive mode
        print("\nJARVIS Intent Engine Test")
        print("=" * 40)
        
        if not engine.is_available():
            print("[X] Ollama not available!")
            sys.exit(1)
        
        print("[OK] Ollama connected")
        print("\nEnter commands to test (Ctrl+C to exit):\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                if not user_input:
                    continue
                
                result = engine.classify(user_input)
                
                print(f"\nIntent: {result.intent} (confidence: {result.confidence:.2f})")
                print(f"Tool: {result.tool}")
                print(f"Params: {json.dumps(result.params, indent=2)}")
                
                if result.response:
                    print(f"Response: {result.response}")
                
                print()
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
