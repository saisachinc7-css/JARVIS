"""
WhatsApp Agent â€” Standard Agent Implementation
Receives requests from the Brain, uses its own LLM config, and accesses main memory.

Two modes:
    SEND MODE:  "send hi to CONTACT_NAME_THREE"  â†’ draft message via whatsapp_skill
    CHAT MODE:  "chat with CONTACT_NAME_ONE"  â†’ open chat, read messages, auto-reply via wa_chat_bot
"""

import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Agents.base_agent import BaseAgent
from Agents.WhatsApp_Agent import config


class WhatsAppAgent(BaseAgent):
    """
    WhatsApp Agent â€” handles all WhatsApp messaging requests.
    Uses its own LLM config from config.py for message generation.
    """

    AGENT_NAME = config.AGENT_NAME

    def _load_config(self):
        """Load WhatsApp-specific LLM config."""
        self.model = config.MODEL_NAME
        self.system_prompt = config.SYSTEM_PROMPT
        self.ollama_options = config.OLLAMA_OPTIONS.copy()

    def process(self, request: str, pre_parsed: dict = None) -> dict:
        """
        Process a WhatsApp request. Routes to correct handler:
        
        CHAT MODE (auto-reply):
            - "chat with CONTACT_NAME_ONE that I'll be available after 3 days"
            - "reply to mom"
            â†’ Opens chat, reads messages, generates reply with LLM, sends it
            
        SEND MODE (draft message):
            - "send hi to CONTACT_NAME_THREE on whatsapp"
            - "message CONTACT_NAME_ONE about lunch"
            â†’ Drafts message without sending, waits for human review
        
        Args:
            request: Raw user request text
            pre_parsed: Optional dict of params already extracted by IntentEngine
                        (e.g., {"contact": "CONTACT_NAME_TWO", "mode": "single", "user_context": "..."}).
                        Used as ground truth to avoid pronoun resolution failures.
        """
        self.log(f"Processing: {request}")
        self._pre_parsed = pre_parsed or {}
        if self._pre_parsed:
            self.log(f"Pre-parsed params available: contact={self._pre_parsed.get('contact', '?')}")

        # Get memory context for personalization
        memory_context = self.recall_memory(request)
        if memory_context:
            self.log("Memory loaded for personalization")

        # Detect mode: CHAT vs SEND
        request_lower = request.lower()
        is_chat = self._is_chat_mode(request_lower)

        if is_chat:
            return self._handle_chat(request, request_lower, memory_context)
        else:
            return self._handle_send(request, memory_context)

    def _is_chat_mode(self, text: str) -> bool:
        """Detect if the request is a chat/reply command vs a send command."""
        chat_signals = [
            "chat with", "reply to", "respond to", "talk to",
            "chat to", "reply on", "auto reply", "auto chat",
            "continue chat", "open chat",
        ]
        return any(signal in text for signal in chat_signals)

    def _handle_chat(self, request: str, request_lower: str, memory: str) -> dict:
        """
        Handle CHAT mode â€” open WhatsApp chat, read messages, auto-reply.
        Uses wa_chat_bot.reply_to_chat_sync() for the actual automation.
        """
        self.log("CHAT MODE detected")

        # Extract contact and topic from the request using this agent's LLM
        parsed = self._parse_chat_request(request)
        contact = parsed.get("contact", "")
        topic = parsed.get("topic", "")
        mode = parsed.get("mode", "single")  # single or loop

        if not contact:
            return {
                "success": False,
                "agent": self.AGENT_NAME,
                "response": "Sorry sir, I couldn't figure out who to chat with. Could you specify the contact?",
            }

        self.log(f"Chat target: {contact}, mode: {mode}, topic: {topic}")

        try:
            from Agents.WhatsApp_Agent.wa_chat_bot import reply_to_chat_sync

            result = reply_to_chat_sync(
                contact=contact,
                mode=mode,
                topic=topic if topic else None,
            )

            if result.get("success"):
                msgs_sent = result.get("messages_sent", 0)
                contact_name = result.get("contact", contact)
                self.log(f"Chat session complete: {msgs_sent} messages sent to {contact_name}")

                return {
                    "success": True,
                    "agent": self.AGENT_NAME,
                    "response": f"Done sir, replied to {contact_name}.",
                    "data": result,
                }
            else:
                error = result.get("error", "unknown error")
                self.log(f"Chat failed: {error}")
                return {
                    "success": False,
                    "agent": self.AGENT_NAME,
                    "response": f"Sorry sir, couldn't complete the chat. {error}",
                    "data": result,
                }

        except Exception as e:
            safe_err = str(e).encode('ascii', errors='replace').decode()
            self.log(f"Chat error: {safe_err}")
            return {
                "success": False,
                "agent": self.AGENT_NAME,
                "response": f"WhatsApp chat error: {safe_err[:100]}",
            }

    def _handle_send(self, request: str, memory: str) -> dict:
        """
        Handle SEND mode â€” draft a message via WhatsApp.
        Does NOT auto-send; waits for human review.

        SMART PATH (pre_parsed available):
            IntentEngine already extracted contact + message intent.
            If message is abstract ("my vacation", "about that project"),
            we use LLM + memory to compose a concrete message.
            Then send directly via automator â€” no WhatsAppSkill pattern matching.

        FALLBACK PATH (no pre_parsed):
            Use WhatsAppSkill's pattern parser for explicit commands like
            "send hi to CONTACT_NAME_THREE saying I'll be late".
        """
        self.log("SEND MODE detected")

        contact_name = self._pre_parsed.get("contact", "")
        raw_message = self._pre_parsed.get("message", "")

        # â”€â”€ SMART PATH: IntentEngine already parsed contact + message â”€â”€
        if contact_name and raw_message:
            self.log(f"Smart path: contact='{contact_name}', raw_message='{raw_message}'")
            try:
                return self._smart_send(contact_name, raw_message, request, memory)
            except Exception as e:
                safe_err = str(e).encode('ascii', errors='replace').decode()
                self.log(f"Smart send error: {safe_err}")
                return {
                    "success": False,
                    "agent": self.AGENT_NAME,
                    "response": f"Sorry sir, couldn't send the message. {safe_err[:100]}",
                }

        # â”€â”€ FALLBACK: use WhatsAppSkill pattern parser â”€â”€
        self.log("Fallback path: using WhatsAppSkill pattern parser")
        try:
            from Agents.WhatsApp_Agent.whatsapp_skill import handle_whatsapp_command

            result = handle_whatsapp_command(request)

            if result.get("success"):
                contact = result.get("contact", "unknown")
                message = result.get("message", "")
                self.log(f"Message drafted for: {contact}")

                confirmation = self._generate_confirmation(contact, message, memory)

                return {
                    "success": True,
                    "agent": self.AGENT_NAME,
                    "response": confirmation,
                    "data": result,
                }
            else:
                error = result.get("error", "unknown error")
                self.log(f"Send failed: {error}")
                return {
                    "success": False,
                    "agent": self.AGENT_NAME,
                    "response": f"Sorry sir, couldn't send the message. {error}",
                    "data": result,
                }

        except Exception as e:
            safe_err = str(e).encode('ascii', errors='replace').decode()
            self.log(f"Send error: {safe_err}")
            return {
                "success": False,
                "agent": self.AGENT_NAME,
                "response": f"WhatsApp send error: {safe_err[:100]}",
            }

    def _smart_send(self, contact_name: str, raw_message: str, request: str, memory: str) -> dict:
        """
        Smart send: compose a real message from abstract intent + memory, then draft.

        If raw_message is abstract like 'my vacation and the duration',
        we recall relevant memory and use LLM to compose a natural WhatsApp message.
        If raw_message is already concrete, we use it as-is.
        """
        from Agents.WhatsApp_Agent.contact_manager import ContactManager
        from Agents.WhatsApp_Agent.wa_web_automator import WhatsAppWebAutomator
        from TextToSpeech.Fast_DF_TTS import speak
        import threading

        # Step 1: Resolve contact
        contact_manager = ContactManager()
        contact_result = contact_manager.resolve(contact_name)

        if not contact_result.get("found"):
            error_msg = f"Contact '{contact_name}' not found"
            self.log(error_msg)
            threading.Thread(target=speak, args=(error_msg,), daemon=True).start()
            return {"success": False, "agent": self.AGENT_NAME, "response": error_msg}

        contact = contact_result["contact"]
        phone = contact["phone"]
        resolved_name = contact["name"]
        self.log(f"Resolved contact: {resolved_name} ({phone})")

        # Step 2: Compose the message
        # Check if raw_message is abstract (references memory/context)
        # BUT: if the message is already concrete data (search results, errors, etc.),
        # always treat it as concrete â€” don't compose from memory!
        msg_lower = raw_message.lower()

        # Concrete signals: the message IS the actual content to send
        concrete_signals = [
            "found", "no ", "results for", "error:", "http", "github",
            "repositories", "emails", "weather", "schedule:", "events",
            "stars", "unread", "summary:", "here are", "here's",
        ]
        is_concrete = any(sig in msg_lower for sig in concrete_signals) or len(raw_message) > 100

        if not is_concrete:
            abstract_signals = [
                "my ", "about my", "the duration", "about that", "about this",
                "about it", "regarding my", "update about", "inform about",
                "the plan", "the trip", "the vacation", "the meeting",
            ]
            is_abstract = any(sig in msg_lower for sig in abstract_signals)
        else:
            is_abstract = False

        if is_abstract:
            self.log(f"Abstract message detected, composing from memory...")
            # Recall everything relevant from memory
            memory_context = self.recall_memory(request) or ""

            message = self._compose_message_from_memory(
                contact_name=resolved_name,
                raw_intent=raw_message,
                user_request=request,
                memory=memory_context,
            )
            self.log(f"Composed message: {message[:80]}...")
        else:
            # Concrete message â€” use as-is
            message = raw_message
            self.log(f"Concrete message, using as-is: {message[:80]}...")

        # Step 3: Speak confirmation before opening WhatsApp
        threading.Thread(
            target=speak,
            args=(f"Sure sir, sending message to {resolved_name}.",),
            daemon=True,
        ).start()

        # Step 4: Draft via automator
        automator = WhatsAppWebAutomator(headless=False)
        result = automator.draft_message(phone, message)

        if result.get("success"):
            self.log(f"Message drafted for {resolved_name}")
            confirmation = self._generate_confirmation(resolved_name, message, memory)
            return {
                "success": True,
                "agent": self.AGENT_NAME,
                "response": confirmation,
                "data": {"contact": resolved_name, "message": message},
            }
        else:
            error_msg = result.get("error", "Failed to draft message")
            self.log(f"Draft failed: {error_msg}")
            return {
                "success": False,
                "agent": self.AGENT_NAME,
                "response": f"Sorry sir, couldn't prepare the message. {error_msg}",
            }

    def _compose_message_from_memory(self, contact_name: str, raw_intent: str,
                                      user_request: str, memory: str) -> str:
        """
        Use LLM + memory to compose a concrete WhatsApp message from an abstract intent.

        Strategy:
          1. Directly query the memory DB for ALL relevant context (vacation, trips, plans)
          2. Also check the schedule table for upcoming events
          3. Build a rich context string
          4. Feed to LLM with a concise prompt
          5. If LLM fails, construct message directly from DB data (no LLM needed)
        """
        # â”€â”€ Step 1: Gather ALL relevant context from centralized memory â”€â”€
        context_parts = []

        try:
            from Brain.Memory.memory_manager import get_memory
            mem = get_memory()
            if mem and mem.is_available():
                # Use smart_recall_context for focused, relevant context
                smart_ctx = mem.smart_recall_context(raw_intent)
                if smart_ctx:
                    context_parts.append(smart_ctx)

                # Also try with the full user request for broader context
                if user_request and user_request != raw_intent:
                    extra_ctx = mem.smart_recall_context(user_request)
                    if extra_ctx and extra_ctx != smart_ctx:
                        context_parts.append(extra_ctx)
        except Exception as e:
            self.log(f"DB context query failed: {e}")

        # Add the recall_memory result too (catches identity, today's schedule, etc.)
        if memory:
            context_parts.append(memory)

        full_context = "\n".join(context_parts) if context_parts else ""
        self.log(f"Memory context ({len(context_parts)} items): {full_context[:200]}...")

        # â”€â”€ Step 2: Compose via LLM (direct call with FAST settings) â”€â”€
        if full_context:
            prompt = f"""Compose a WhatsApp message from YOUR_NAME to {contact_name} about: {raw_intent}

Context from YOUR_NAME's memory:
{full_context}

Rules: casual friendly tone, include specific details (dates, places, duration) from the context above, 2-3 sentences max, no "Dear"/"Regards".
Output ONLY the message text, nothing else.
/nothink"""

            # Call ollama DIRECTLY with fast, creative settings
            # (the agent's default is temp=0.15/seed=42/num_predict=1500 â€” too slow & rigid)
            try:
                import ollama as _ollama
                import threading

                result_box = [""]
                def _fast_compose():
                    try:
                        resp = _ollama.chat(
                            model="qwen3:4b",
                            messages=[
                                {"role": "system", "content": "You compose short WhatsApp messages. Output ONLY the message text."},
                                {"role": "user", "content": prompt},
                            ],
                            options={
                                "temperature": 0.7,
                                "num_predict": 200,   # Short message, fast!
                                "num_ctx": 2048,
                                "num_batch": 512,
                            },
                        )
                        answer = resp.get("message", {}).get("content", "").strip()
                        # Clean thinking tags
                        import re as _re
                        answer = _re.sub(r'<think>.*?</think>', '', answer, flags=_re.DOTALL).strip()
                        answer = _re.sub(r'<think>.*$', '', answer, flags=_re.DOTALL).strip()
                        answer = _re.sub(r'</think>', '', answer).strip()
                        result_box[0] = answer
                    except Exception as e:
                        self.log(f"Fast compose LLM error: {e}")

                t = threading.Thread(target=_fast_compose, daemon=True)
                t.start()
                t.join(timeout=20)  # 20s should be plenty for 200 tokens

                result = result_box[0]
                if result and len(result) > 10:
                    # Sanity: don't send LLM errors/instructions as messages
                    bad_signals = ["sorry", "i can't", "i don't", "as an ai", "i'm unable",
                                   "i cannot", "compose", "here is", "here's a"]
                    first_50 = result.lower()[:50]
                    if not any(sig in first_50 for sig in bad_signals):
                        self.log(f"LLM composed: {result[:120]}...")
                        return result
                    else:
                        # Strip meta-prefix and use the rest
                        for prefix in ["Here is the message:", "Here's the message:", 
                                      "Here is a message:", "Here's a WhatsApp message:"]:
                            if result.lower().startswith(prefix.lower()):
                                result = result[len(prefix):].strip()
                                if len(result) > 10:
                                    self.log(f"LLM composed (prefix stripped): {result[:120]}...")
                                    return result
                else:
                    self.log(f"LLM returned empty or too short: '{result}'")
            except Exception as e:
                self.log(f"Fast compose failed: {e}")

        # â”€â”€ Step 3: Fallback â€” construct message from whatever context we have â”€â”€
        self.log("LLM failed or no context, building message from raw data")

        # Dynamically extract key facts from context_parts (not hardcoded!)
        location = ""
        date_info = ""
        duration = ""
        import re as _re
        for part in context_parts:
            lower = part.lower()
            # Extract ANY location: look for "to <Place>"
            loc_match = _re.search(r'\bto\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', part)
            if loc_match and not location:
                location = loc_match.group(1)
            # Extract date references
            date_match = _re.search(r'(\d{4}-\d{2}-\d{2})', part)
            if date_match and not date_info:
                date_info = date_match.group(1)
            # Extract human-readable time refs
            for time_phrase in ["next week", "this week", "next month", "tomorrow",
                                "next 2 days", "next two days", "next 3 days", "next three days",
                                "for a week", "for 2 weeks", "whole week"]:
                if time_phrase in lower:
                    if not duration:
                        duration = time_phrase
                    if not date_info:
                        date_info = time_phrase

        # Build a reasonable message from extracted parts
        if location or date_info or duration:
            msg = f"Hey {contact_name}!"
            if location:
                msg += f" Just wanted to let you know I'm heading to {location}"
            else:
                msg += f" Just a quick update"
            if date_info:
                msg += f" starting {date_info}"
            if duration and duration != date_info:
                msg += f" for {duration}"
            msg += ". Will keep you posted!"
            return msg

        # Last resort â€” use the raw intent as-is
        return f"Hey {contact_name}! Wanted to update you â€” {raw_intent}. Will share more details soon!"

    # Pronouns that should NEVER be used as a contact name
    _PRONOUNS = {
        "him", "her", "them", "he", "she", "they", "his", "hers", "their",
        "it", "this", "that", "person", "someone", "guy", "dude", "bro",
    }

    def _resolve_pronouns(self, contact: str, request: str) -> str:
        """
        Resolve pronouns (him, her, them, etc.) to the actual person's name.
        
        Strategy:
        1. If pre-parsed params from IntentEngine have a real contact â†’ use it
        2. Extract all proper-name-looking words from the request that aren't pronouns/commands
        3. Return the first real name found, or the original contact if nothing better
        
        Examples:
            "CONTACT_NAME_TWO is annoying me can you chat with him" â†’ "CONTACT_NAME_TWO"
            "tell mom that he is annoying, chat with her"   â†’ "mom"
        """
        if contact.lower() not in self._PRONOUNS:
            return contact  # Already a real name
        
        self.log(f"Pronoun '{contact}' detected, resolving...")
        
        # Layer 1: IntentEngine already resolved the contact correctly
        pre_contact = self._pre_parsed.get("contact", "")
        if pre_contact and pre_contact.lower() not in self._PRONOUNS:
            self.log(f"Resolved '{contact}' -> '{pre_contact}' (from IntentEngine)")
            return pre_contact
        
        # Layer 2: Extract candidate names from the request
        # Look for words that appear BEFORE the chat/reply/tell command
        # e.g., "CONTACT_NAME_TWO is annoying me can you chat with him" -> "CONTACT_NAME_TWO"
        request_lower = request.lower()
        
        # Words to exclude (commands, filler, pronouns)
        exclude = {
            "i", "me", "my", "you", "your", "we", "us", "our", "am", "is", "are",
            "was", "were", "be", "been", "do", "does", "did", "have", "has", "had",
            "will", "would", "could", "should", "can", "may", "might", "shall",
            "not", "no", "yes", "ok", "okay", "please", "the", "a", "an",
            "and", "or", "but", "so", "if", "that", "this", "with", "to",
            "for", "from", "in", "on", "at", "by", "of", "about", "after",
            "before", "now", "just", "really", "very", "too", "also",
            "chat", "reply", "respond", "talk", "send", "message", "tell",
            "say", "saying", "whatsapp", "text", "inform", "let", "know",
            "available", "busy", "free", "annoying", "annoyed", "mood",
            "hours", "hour", "minutes", "minute", "days", "day", "right",
            "work", "working", "other", "doing", "going", "want",
        } | self._PRONOUNS
        
        # Get all words, find candidate names (capitalized in original, or unique nouns)
        words = request.split()
        candidates = []
        for word in words:
            clean = re.sub(r'[^a-zA-Z]', '', word)
            if not clean or len(clean) < 2:
                continue
            if clean.lower() in exclude:
                continue
            candidates.append(clean)
        
        if candidates:
            chosen = candidates[0]  # First non-filler word is usually the person's name
            self.log(f"Resolved '{contact}' -> '{chosen}' (from sentence analysis)")
            return chosen
        
        self.log(f"Could not resolve pronoun '{contact}', keeping as-is")
        return contact

    def _parse_chat_request(self, request: str) -> dict:
        """Parse contact, topic, and mode from a chat request using this agent's LLM."""
        prompt = f"""Extract the contact name, conversation topic, and mode from this WhatsApp chat request.

Request: "{request}"

Rules:
- contact: The ACTUAL person's name mentioned in the request (e.g., "CONTACT_NAME_ONE", "mom", "CONTACT_NAME_THREE")
  CRITICAL: If the user says "chat with him/her/them", resolve the pronoun to the person's REAL NAME
  mentioned earlier in the sentence. Example: "CONTACT_NAME_TWO is annoying me can you chat with him" -> contact is "CONTACT_NAME_TWO", NOT "him".
  NEVER return a pronoun (him, her, them, he, she, they) as the contact.
- topic: What the user wants to say or discuss (the full context/message)
- mode: ALWAYS "loop" for continuous chat/auto-reply (UNLESS the user explicitly says "just send one reply", then "single")

Reply with ONLY this format (no other text):
contact: <name>
topic: <topic or empty>
mode: <single or loop>
/nothink"""

        result = self.llm_generate(prompt)

        parsed = {"contact": "", "topic": "", "mode": "loop"}
        if result:
            for line in result.strip().split("\n"):
                line = line.strip()
                if line.lower().startswith("contact:"):
                    parsed["contact"] = line.split(":", 1)[1].strip()
                elif line.lower().startswith("topic:"):
                    val = line.split(":", 1)[1].strip()
                    if val.lower() not in ("empty", "none", "n/a", ""):
                        parsed["topic"] = val
                elif line.lower().startswith("mode:"):
                    val = line.split(":", 1)[1].strip().lower()
                    if val in ("single", "loop"):
                        parsed["mode"] = val

        if not parsed["mode"]:
            parsed["mode"] = "loop"

        # Fallback: regex extraction if LLM failed
        if not parsed["contact"]:
            request_lower = request.lower()
            for pattern in [
                r'(?:chat|reply|respond|talk)\s+(?:with|to)\s+(\w+)',
            ]:
                match = re.search(pattern, request_lower)
                if match:
                    parsed["contact"] = match.group(1)
                    break

            # Extract topic (everything after "that" or "saying" or "about")
            for sep in ["that ", "saying ", "about "]:
                if sep in request_lower:
                    parsed["topic"] = request[request_lower.index(sep) + len(sep):].strip()
                    break

        # PRONOUN RESOLUTION: If LLM or regex returned a pronoun, resolve it
        if parsed["contact"]:
            parsed["contact"] = self._resolve_pronouns(parsed["contact"], request)

        self.log(f"Parsed chat: contact={parsed['contact']}, mode={parsed['mode']}, topic={parsed['topic'][:50]}")
        return parsed

    def _generate_confirmation(self, contact: str, message: str, memory: str) -> str:
        """Generate a natural confirmation using this agent's LLM."""
        # Truncate message to avoid sending 2000-char payloads (GitHub results
        # etc.) to the LLM â€” the confirmation only needs contact + brief summary.
        msg_preview = message[:100] + "..." if len(message) > 100 else message
        prompt = f"""The user asked to send a WhatsApp message.
Contact: {contact}
Message preview: {msg_preview}

Generate a SHORT, natural confirmation (1 sentence).
Example: "Done sir, sent your message to CONTACT_NAME_THREE."
Do NOT repeat the full message content.
/nothink"""

        result = self.llm_generate(prompt)
        if result and len(result) > 5:
            return result
        return f"Done sir, sent your message to {contact}."

    def generate_reply(self, contact: str, their_message: str, user_context: str = "") -> str:
        """
        Generate a reply to a received WhatsApp message.
        Uses this agent's LLM with memory for personalization.
        """
        memory = self.recall_memory(f"relationship with {contact}")

        prompt = f"""You are composing a WhatsApp reply on behalf of the user.

{memory}

Contact: {contact}
Their message: {their_message}
User's instruction: {user_context if user_context else "Reply naturally"}

Write ONLY the reply message. Keep it natural and conversational.
Match the tone (casual if they're casual, formal if formal).
/nothink"""

        result = self.llm_generate(prompt)
        if result and len(result) > 2:
            return result
        return "Got it!"


# Singleton
_agent = None


def get_whatsapp_agent() -> WhatsAppAgent:
    global _agent
    if _agent is None:
        _agent = WhatsAppAgent()
    return _agent

