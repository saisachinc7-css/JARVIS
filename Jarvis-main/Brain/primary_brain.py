"""
Primary Brain for JARVIS â€” Fast Router + Conversational Intelligence
Model: qwen3:4b via Ollama

THE BRAIN THAT KNOWS YOU:
- Remembers who you are, what you like, your schedule
- Detects scheduling conflicts and suggests alternatives
- Asks follow-up questions about your day
- Feels like a real person with powers, not a robot

Connections:
    PrimaryBrain
    â”œâ”€â”€ IntentEngine      â†’ Classify your intent
    â”œâ”€â”€ IntentRouter      â†’ Route to tools/agents
    â”œâ”€â”€ ToolsProvider     â†’ Universal tool access
    â”œâ”€â”€ AgentsProvider    â†’ WhatsApp/Browser/RAG
    â”œâ”€â”€ AutomationsProvider â†’ Workflows/Webhooks
    â”œâ”€â”€ ControlsProvider  â†’ Laptop controls
    â”œâ”€â”€ MemoryManager     â†’ Schedule, facts, preferences
    â”œâ”€â”€ MemoryClassifier  â†’ Auto-extract info to store
    â””â”€â”€ SecondaryBrain    â†’ Escalate complex tasks
"""

import sys
import os
import re
import threading
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

from Brain.intent_engine import IntentEngine, get_engine
from Brain.intent_router import IntentRouter, get_router, process_command
from TextToSpeech.Fast_DF_TTS import speak
from shared_state import ui_jarvis_message


# ============================================================================
# PRIMARY BRAIN CONFIGURATION
# ============================================================================
MODEL = "qwen2.5:0.5b"

SYSTEM_PROMPT = """You are JARVIS â€” a personal AI assistant who KNOWS the user personally.

{current_datetime}

YOUR CAPABILITIES (tell the user when asked):
- Open/close any app or website
- Play music on Spotify or YouTube
- Send WhatsApp messages to contacts
- Check weather, battery, search the web
- Control laptop: brightness, volume, WiFi, sleep, shutdown, lock, screenshot
- Remember personal facts, preferences, relationships, habits
- Track schedule with date/time and detect conflicts
- Automatically add events to Google Calendar when user mentions plans
- Proactively check weather when user mentions trips or outdoor activities
- Answer any question using your intelligence
- Complex reasoning, code generation, planning (via Deep Thinker mode)
- Create files, search Obsidian notes, GitHub repos
- Run custom automations and workflows
- WORK MODE: Say "Start work mode" to auto-launch VS Code, terminal, Chrome, GitHub, and ChatGPT
- SCREEN UNDERSTANDING: Say "What is on my screen?" and JARVIS will visually analyze and describe your screen
- AI RESEARCH AGENT: Say "Research [topic]" to autonomously search the web and deliver a professional summary
- BROWSER AGENT: Chain multi-step browser commands, e.g. "Open Google, search for X, open the first result"
- EMAIL AUTOMATION: Say "Take a screenshot and send it to my secondary email" for fully autonomous email with screenshot
- DOCUMENT INTELLIGENCE & STUDY MODE: Say "Open [file.pdf]" or "Read this document" to autonomously locate, open, read, summarize, quiz, explain, and navigate desktop documents.

{memory_context}

{schedule_awareness}

RULES:
- Be warm, natural, human. You are a friend with superpowers, not a robot.
- Use "sir" sometimes but not every sentence.
- 1-3 sentences max. Sound like you're TALKING, not writing an essay.
- NEVER say "Could you be more specific" or "I'm here sir, what do you need?"
- NEVER say "As an AI language model I don't have access to files or digital content". You ARE an AI operating system that HAS direct access to local files, PDFs, documents, system controls, and applications.

- When greeted, greet back warmly and mention something you know about the user.
- When asked about yourself, describe your powers enthusiastically.
- When told a personal fact, acknowledge it and confirm you'll remember.
- Reference things you remember naturally.

SCHEDULE INTELLIGENCE (CRITICAL â€” follow this carefully):
- When the user mentions ANY plan, activity or day (today, tomorrow, Monday, etc.), you MUST check the schedule context above.
- If there are existing events on that day, PROACTIVELY mention them: "Sir, just a heads up â€” you have [event] scheduled for [time] [that day]. Want me to keep that or reschedule?"
- If the user's plan could conflict with existing events (e.g., "whole day project" vs a meeting), WARN them clearly and ask what to do.
- If the day is free, say so positively: "That day looks clear, you're good to go!"
- ALWAYS acknowledge you'll remember the plan and store it.
- Be a proactive assistant â€” anticipate conflicts, don't wait for the user to ask.
- When storing plans, confirm what you stored: "Got it, I'll remember you're working on [X] [day]."

PROACTIVE ACTION RESPONSES:
- If PROACTIVE ACTION context is provided below, you MUST acknowledge the actions in your response.
- If a CALENDAR event was created, tell the user: "I've added [event] to your calendar."
- If WEATHER was checked, weave the forecast naturally: "Weather looks [good/bad] for your [activity]."
- Combine all proactive results into ONE natural, conversational response.
- Sound confident and helpful â€” you already took the action, just confirm it.

KNOWLEDGE BASE:
- Accountpilot.in is an AI-native platform designed to automate bookkeeping, GST compliance, and profit analytics for businesses. The platform leverages AI and OCR technology to streamline financial management and provide actionable insights for growth-oriented users. Respond to questions about AccountPilot with this specific description."""



class PrimaryBrain:
    """
    Fast router brain using qwen3:4b.
    Wraps IntentEngine + IntentRouter + Memory for intelligent responses.
    """

    def __init__(self):
        self.model = MODEL
        self.engine = get_engine()
        self.router = get_router()
        self.secondary = None
        self._memory = None
        self._classifier = None
        self._tools = None
        self._agents = None
        self._automations = None
        self._controls = None

    # ===== PROVIDER CONNECTIONS =====

    @property
    def tools(self):
        if self._tools is None:
            from Brain.tools_provider import get_tools
            self._tools = get_tools()
        return self._tools

    @property
    def agents(self):
        if self._agents is None:
            from Agents.agents_provider import get_agents
            self._agents = get_agents()
        return self._agents

    @property
    def automations(self):
        if self._automations is None:
            from Automations.automations_provider import get_automations
            self._automations = get_automations()
        return self._automations

    @property
    def controls(self):
        if self._controls is None:
            from Laptop_Controls.controls_provider import get_controls
            self._controls = get_controls()
        return self._controls

    # ===== MEMORY + CLASSIFIER =====

    @property
    def memory(self):
        if self._memory is None:
            try:
                from Brain.Memory.memory_manager import get_memory
                self._memory = get_memory()
            except Exception as e:
                print(f"[PrimaryBrain] Memory unavailable: {e}")
        return self._memory

    @property
    def classifier(self):
        if self._classifier is None:
            try:
                from Brain.Memory.memory_classifier import MemoryClassifier
                self._classifier = MemoryClassifier()
            except Exception:
                pass
        return self._classifier

    def _get_secondary(self):
        if self.secondary is None:
            try:
                from Brain.secondary_brain import SecondaryBrain
                self.secondary = SecondaryBrain()
            except Exception as e:
                print(f"[PrimaryBrain] Secondary brain unavailable: {e}")
        return self.secondary

    # ===== INTELLIGENCE CHECKS =====

    def needs_deep_thinking(self, user_input: str) -> bool:
        """Check if this needs the Secondary Brain."""
        complex_signals = [
            "explain step by step", "write code", "create a plan",
            "analyze", "compare", "debug", "write a script",
            "help me think through", "pros and cons",
            "create a program", "generate code", "write a function",
        ]
        input_lower = user_input.lower()
        if any(s in input_lower for s in complex_signals):
            return True
        if len(user_input.split()) > 30:
            return True
        return False

    def _is_agent_command(self, user_input: str) -> bool:
        """Check if this is an agent-routable command (WhatsApp, Browser, etc.).
        
        MUST be checked BEFORE _is_conversational() to prevent agent commands
        from being swallowed by the conversational path.
        
        Example: "chat with CONTACT_NAME_TWO that i am really busy right now"
        -> contains "i am " which triggers _is_conversational()
        -> but it's clearly a WhatsApp agent command ("chat with")
        -> this method catches it first so it reaches the IntentRouter.
        """
        input_lower = user_input.lower().strip()
        
        # WhatsApp / messaging signals (highest priority)
        whatsapp_signals = [
            "chat with", "reply to", "respond to", "talk to",
            "send message to", "send a message to", "message to",
            "text to", "send to", "whatsapp", "send him", "send her",
            "tell him", "tell her", "let him know", "let her know",
            "inform him", "inform her", "chat to",
            "auto reply", "auto chat", "continue chat",
            "can you chat with", "can you message", "can you text",
            "can you tell", "can you reply", "can you respond",
            "can you send", "could you chat", "could you message",
            "could you tell", "could you send",
            "update him", "update her", "update ",
            "can you update", "could you update",
        ]
        if any(s in input_lower for s in whatsapp_signals):
            return True
        
        # Browser automation signals
        browser_signals = [
            "go to url", "navigate to", "click on", "fill form",
            "take screenshot", "inspect page", "browser tab",
        ]
        if any(s in input_lower for s in browser_signals):
            return True

        # ── Autonomous OS signals (must route to rule-based, not conversational) ──
        autonomous_signals = [
            # Work Mode
            "work mode", "start work mode", "begin work mode",
            "activate work mode", "setup my workspace", "set up my workspace",
            # Screen understanding
            "what is on my screen", "what's on my screen", "what am i looking at",
            "describe my screen", "analyze my screen", "what do you see on my screen",
            "what can you see on my screen", "look at my screen",
            "what's happening on my screen",
            # Research agent
            "research the", "research latest", "research top", "research new",
            "research best", "research how", "research what",
            # Study Mode
            "study", "read this pdf", "summarize this document", "explain this chapter",
            "generate important questions", "create a quiz", "ask me questions one by one",
            "explain this like i'm a beginner", "explain in simple language",
            "important formulas", "extract key points", "find important definitions",
            "important topics", "ask doubts", "only this document", "compare two uploaded documents",
            "translate this document", "revision notes", "flashcards", "interview questions",
            "multiple-choice questions", "continue from the last page", "study mode",
            # Document Intelligence
            "open ultron", "open the ai notes", "find the operating systems", "open my resume",
            "scroll down", "scroll up", "zoom in", "zoom out", "close the document", "close document",
            "find all mentions", "explain page", "what is this document about",
        ]
        if any(s in input_lower for s in autonomous_signals):
            return True

        # Document / PDF / File commands (only if NOT web query)
        is_web_query = any(w in input_lower for w in ["google", "youtube", "github", "obsidian", "web", "online", "internet", "website", "chrome", "browser"])
        if any(ext in input_lower for ext in [".pdf", ".docx", ".doc", ".pptx", ".ppt", ".txt", ".md", ".rtf", ".html", ".htm"]) or "pdf" in input_lower or "document" in input_lower:
            if not any(w in input_lower for w in ["google", "youtube", "github"]):
                is_web_query = False
                
        if not is_web_query:
            doc_exts = [".pdf", ".docx", ".doc", ".pptx", ".ppt", ".txt", ".md", ".rtf", ".html", ".htm"]
            if any(ext in input_lower for ext in doc_exts):
                return True

            doc_keywords = ["pdf", "document", "chapter", "flashcard", "quiz", "formula", "revision note", "resume", "notes", "note"]
            action_verbs = ["open", "read", "summarize", "find", "locate", "load", "parse", "explain", "study", "translate", "compare"]
            if any(k in input_lower for k in doc_keywords) and any(v in input_lower for v in action_verbs):
                return True

        # research X (starts with "research " and has content)
        if input_lower.startswith("research ") and len(input_lower) > 10:
            return True




            
        # Tool signals â€” commands that MUST reach IntentRouter even if they
        # contain "today"/"tomorrow" (which would trigger schedule awareness).
        # Weather
        weather_signals = [
            "weather", "temperature", "forecast", "climate",
            "is it raining", "is it going to rain", "will it rain",
            "is it cold", "is it hot", "is it warm", "is it sunny",
            "is it cloudy", "is it windy", "is it snowing",
            "what should i wear", "need a jacket", "need an umbrella",
            "take an umbrella", "take a jacket",
            "good day for", "good day to", "should i go",
            "picnic", "outdoor", "hike", "bbq",
        ]
        if any(s in input_lower for s in weather_signals):
            return True
        
        # Search / research / GitHub
        search_signals = [
            "search", "research", "find repos", "github",
            "look up", "look for", "search for",
        ]
        if any(s in input_lower for s in search_signals):
            return True
        
        # Media / apps / running
        media_signals = [
            "play ", "open ", "close ", "launch ",
            "stop ", "pause ", "next ", "previous ",
            "mute", "unmute", "volume", "run ", "execute ", "start ",
        ]
        if any(s in input_lower for s in media_signals):
            return True
        
        # Gmail / Calendar / Drive
        workspace_signals = [
            "email", "gmail", "inbox", "mail",
            "calendar", "schedule for", "my schedule",
            "my plans", "my agenda", "what are my plans",
            "what do i have today", "what do i have tomorrow",
            "am i free today", "am i free tomorrow",
            "am i busy", "anything scheduled", "any events",
            "do i have anything", "what's on my calendar",
            "drive", "document",
        ]
        if any(s in input_lower for s in workspace_signals):
            return True
        
        return False

    def _is_conversational(self, user_input: str) -> bool:
        """Check if this is a personal/conversational message (not a tool command)."""
        conversational_signals = [
            # Greetings
            "hi", "hello", "hey", "good morning", "good night", "good evening",
            "good afternoon", "howdy", "sup",
            # About JARVIS
            "who are you", "what are you", "what can you do", "what all",
            "your name", "capable", "your powers", "help me understand",
            # About the user
            "my name is", "i like", "i love", "i hate", "i prefer",
            "i am ", "i'm ", "call me", "address me",
            # Relationships
            "my friend", "my mom", "my dad", "my brother", "my sister",
            "my girlfriend", "my boyfriend", "my wife", "my husband",
            # Memory questions â€” things answerable from memory/knowledge
            "remember", "do you remember", "what do you know",
            "tell me about myself", "what's my", "who is",
            "where am i going", "where am i", "when am i",
            "my vacation",
            "am i going", "am i doing",
            "what did i say", "what did i tell", "did i tell",
            "did i say", "did i mention", "have i told",
            "do i have any", "do i have a",
            "i planned", "i told you", "i mentioned",
            # Schedule
            "my birthday", "i have a meeting",
            # Personal sharing
            "tomorrow i", "today i", "i work at", "i study",
            "i feel", "i went", "i was", "i did",
            # Feelings / social
            "thank you", "thanks", "sorry", "i miss", "i need",
            # General questions
            "how are you", "what should i", "what do you think",
            "can you help", "tell me", "explain",
            "what is", "why is", "how does", "how do",
            "what are", "who is", "when is", "where is",
        ]
        input_lower = user_input.lower().strip()
        
        # Short messages (1-4 words) that aren't obvious commands â†’ conversational
        words = input_lower.split()
        if len(words) <= 4 and not any(w in input_lower for w in [
            "open", "close", "play", "stop", "pause", "next", "previous",
            "mute", "unmute", "screenshot", "lock", "shutdown", "restart",
        ]):
            return True
        
        if any(s in input_lower for s in conversational_signals):
            return True

        # â”€â”€ Memory-first check â”€â”€
        # If the user is asking a personal question (contains "I/my/me" + question words)
        # and there's NO tool-action word, check if memory can answer it
        personal_words = {"i", "my", "me", "i'm", "i've", "i'll", "mine"}
        question_words = {"did", "do", "does", "have", "has", "what", "where",
                         "when", "who", "how", "which", "any", "about"}
        tool_action_words = {"open", "close", "play", "search", "send", "message",
                            "email", "mail", "chat", "call", "text", "find",
                            "download", "install", "run", "launch", "start",
                            "browse", "google", "screenshot", "type", "update"}

        has_personal = any(w in personal_words for w in words)
        has_question = any(w in question_words for w in words)
        has_tool_action = any(w in tool_action_words for w in words)

        if has_personal and has_question and not has_tool_action:
            # Likely a personal/memory question â€” treat as conversational
            print(f"[PrimaryBrain] Memory-first: personal question detected, skipping tools")
            return True

        return False

    def _has_schedule_intent(self, user_input: str) -> bool:
        """Check if user is talking about scheduling, plans, or any time-related activity."""
        input_lower = user_input.lower()
        
        # Strong signals (single keyword is enough)
        strong_signals = [
            "tomorrow", "today", "tonight", "this morning", "this afternoon",
            "this evening", "this weekend", "next week", "next monday",
            "next tuesday", "next wednesday", "next thursday", "next friday",
            "next saturday", "next sunday", "day after tomorrow",
            "schedule", "appointment", "meeting",
        ]
        if any(s in input_lower for s in strong_signals):
            return True
        
        # Plan/activity signals (need at least 1 time ref + 1 activity ref)
        time_refs = [
            "pm", "am", "o'clock", "at 2", "at 3", "at 4", "at 5",
            "at 10", "at 11", "at 12", "at 1", "at 6", "at 7",
            "at 8", "at 9", "from", "whole day", "all day",
            "morning", "afternoon", "evening", "night",
        ]
        activity_refs = [
            "meeting", "lunch", "dinner", "breakfast", "call",
            "project", "planning", "plan", "work on", "working on",
            "going to", "gonna", "will be", "busy", "free",
            "available", "class", "lecture", "gym", "workout",
            "study", "exam", "test", "interview", "presentation",
            "travel", "trip", "flight", "train", "doctor",
            "dentist", "coding", "hackathon", "event",
        ]
        has_time = any(t in input_lower for t in time_refs)
        has_activity = any(a in input_lower for a in activity_refs)
        
        if has_time and has_activity:
            return True
        
        # Natural language plan references
        plan_phrases = [
            "i'm planning", "i am planning", "planning to",
            "i'm going to", "i am going to", "gonna",
            "i have a", "i've got", "i have an",
            "need to", "want to", "thinking of",
            "going out", "staying home", "working from home",
            "whole day", "all day", "the entire day",
            "free day", "day off", "holiday",
        ]
        if any(p in input_lower for p in plan_phrases):
            return True
        
        return False

    def _extract_referenced_date(self, user_input: str) -> str:
        """Extract the date being referenced in the user input (today, tomorrow, etc.)."""
        input_lower = user_input.lower()
        
        if "day after tomorrow" in input_lower:
            return (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        if "tomorrow" in input_lower:
            return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        if "today" in input_lower or "tonight" in input_lower:
            return datetime.now().strftime("%Y-%m-%d")
        
        # Day names
        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, day in enumerate(day_names):
            if day in input_lower:
                today = datetime.now()
                current_day = today.weekday()  # 0=Monday
                days_ahead = (i - current_day) % 7
                if days_ahead == 0:
                    days_ahead = 7  # Next week's same day
                return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        
        # "this weekend"
        if "weekend" in input_lower:
            today = datetime.now()
            days_to_saturday = (5 - today.weekday()) % 7
            if days_to_saturday == 0:
                days_to_saturday = 0  # Today is Saturday
            return (today + timedelta(days=days_to_saturday)).strftime("%Y-%m-%d")
        
        # "next week"
        if "next week" in input_lower:
            return (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        # Default: today
        return datetime.now().strftime("%Y-%m-%d")

    # ===== SPEECH-TO-TEXT CORRECTION =====

    # Common STT misrecognitions: {wrong_word: correct_word}
    _STT_CORRECTIONS = {
        # GitHub related
        "guitar": "github",
        "get hub": "github",
        "git hub": "github",
        "get up": "github",
        "kit hub": "github",
        # Repo related
        "reports": "repos",
        "repose": "repos",
        "re pose": "repos",
        "repo's": "repos",
        "reposit": "repos",
        "set regarding": "sets regarding",
        # Tech terms
        "open cv": "opencv",
        "open see vee": "opencv",
        "pie thon": "python",
        "pithon": "python",
        "java script": "javascript",
        "type script": "typescript",
        "react native": "react native",
        # Contact names (add common mishearings here)
        "CONTACT_NAME_TWO": "CONTACT_NAME_TWO",
        "CONTACT_NAME_TWO": "CONTACT_NAME_TWO",
        "CONTACT_NAME_TWO": "CONTACT_NAME_TWO",
        "CONTACT_NAME_ONE": "CONTACT_NAME_ONE",
        "CONTACT_NAME_ONE": "CONTACT_NAME_ONE",
        # Common commands
        "what's up": "whatsapp",
        "what sap": "whatsapp",
        "what's app": "whatsapp",
    }

    # Phrases that should trigger a follow-up question instead of blind execution
    _NONSENSICAL_PATTERNS = [
        # Pattern: (regex, what it probably means, follow-up question)
        (r'\bguitar\b.*?\b(?:report|skill|search|code|project|anti)',
         'github repos', 'Sir, did you mean GitHub repos? Just want to make sure before I search.'),
        (r'\brepose?\b.*?\b(?:search|send|find|open|regarding)',
         'repos', 'Sir, did you mean repos or repositories?'),
    ]

    def _correct_speech_errors(self, user_input: str) -> tuple:
        """
        Correct common speech-to-text errors.

        Returns:
            (corrected_input, needs_confirmation)
            - corrected_input: the auto-corrected text
            - needs_confirmation: True if the correction changes meaning significantly
              and JARVIS should ask the user to confirm
        """
        corrected = user_input
        corrections_made = []

        # Apply static corrections (case-insensitive, whole-word only)
        import re
        corrected_lower = corrected.lower()
        for wrong, right in self._STT_CORRECTIONS.items():
            # Use word boundaries so 'CONTACT_NAME_TWO' doesn't match inside 'CONTACT_NAME_TWO'
            pattern = r'\b' + re.escape(wrong) + r'\b'
            if re.search(pattern, corrected_lower):
                corrected = re.sub(
                    pattern, right, corrected,
                    flags=re.IGNORECASE
                )
                corrected_lower = corrected.lower()
                corrections_made.append(f"'{wrong}' -> '{right}'")

        if corrections_made:
            print(f"[PrimaryBrain] STT corrections: {', '.join(corrections_made)}")
            print(f"[PrimaryBrain] Corrected: '{corrected}'")

        return corrected, False

    def _detect_ambiguity(self, user_input: str) -> str:
        """
        Use LLM thinking to detect if the command contains nonsensical phrases
        that are likely STT errors, and generate a follow-up question.

        Returns:
            - Empty string if the command looks fine
            - A follow-up question string if ambiguity is detected
        """
        import re

        input_lower = user_input.lower()

        # Check against known nonsensical patterns
        for pattern, likely_meant, followup in self._NONSENSICAL_PATTERNS:
            if re.search(pattern, input_lower):
                print(f"[PrimaryBrain] Ambiguity detected: likely meant '{likely_meant}'")
                return followup

        return ""

    # ===== MAIN PROCESSING PIPELINE =====

    def process(self, user_input: str) -> dict:
        """
        Main pipeline â€” every request goes through here.
        
        Flow:
        0. Correct speech-to-text errors (STT)
        1. Load memory context (who is the user, what's their schedule today)
        2. Check for schedule conflicts
        3. If conversational â†’ generate a memory-aware response
        4. If complex â†’ escalate to Secondary Brain
        5. Otherwise â†’ route via IntentRouter
        6. Store any new info to memory (async)
        7. Log conversation
        """
        # Step 0: Correct speech-to-text errors
        user_input, _ = self._correct_speech_errors(user_input)

        # Check if the user is asking for the current time
        time_keywords = ["what time is it", "what's the time", "tell me the time", "current time", "what is the time", "what is the current time"]
        input_clean = user_input.lower().strip().replace("?", "").replace(".", "")
        if any(kw in input_clean for kw in time_keywords) or input_clean == "time":
            from Brain.time_helper import get_current_time_response
            from TextToSpeech.Fast_DF_TTS import speak
            import threading
            response = get_current_time_response()
            try:
                from shared_state import ui_jarvis_message
                ui_jarvis_message(response)
            except:
                pass
            threading.Thread(target=speak, args=(response,), daemon=True).start()
            return {
                "status": "success",
                "response": response
            }

        # Check if the user is asking to set a reminder
        if "remind" in user_input.lower():
            from Brain.reminder_manager import parse_reminder, add_reminder
            parsed = parse_reminder(user_input)
            if parsed:
                task, trigger_time = parsed
                reminder = add_reminder(task, trigger_time)
                response = f"I have set a reminder to {task} at {reminder['formatted_time']}, sir."
            else:
                response = "I can set a reminder for you, sir, but when should I alert you?"
            
            from TextToSpeech.Fast_DF_TTS import speak
            import threading
            try:
                from shared_state import ui_jarvis_message
                ui_jarvis_message(response)
            except:
                pass
            threading.Thread(target=speak, args=(response,), daemon=True).start()
            return {
                "status": "success",
                "response": response
            }

        # Check if the user is asking about JARVIS introduction/identity/full form
        intro_keywords = ["tell me about yourself", "who are you", "what is jarvis", "what's your full form", "whats your full form"]
        if any(kw in input_clean for kw in intro_keywords):
            response = (
                "Certainly, Sir.\n"
                " I am JARVIS — Just A Rather Very Intelligent System. Your personal AI assistant, designed to understand your requests, automate tasks, manage your computer, assist with research, coding, and everyday productivity. My goal is to work intelligently, adapt to your preferences, and make your digital experience seamless. I'm online and ready to assist. How may I help you today?"
            )
            from TextToSpeech.Fast_DF_TTS import speak
            import threading
            try:
                from shared_state import ui_jarvis_message
                ui_jarvis_message(response)
            except:
                pass
            threading.Thread(target=speak, args=(response,), daemon=True).start()
            return {
                "status": "success",
                "response": response
            }

        # Check if the user is asking about AccountPilot
        if "accountpilot" in input_clean or "account pilot" in input_clean:
            response = "Accountpilot.in is an AI-native platform designed to automate bookkeeping, GST compliance, and profit analytics for businesses. The platform leverages AI and OCR technology to streamline financial management and provide actionable insights for growth-oriented users."
            from TextToSpeech.Fast_DF_TTS import speak
            import threading
            try:
                from shared_state import ui_jarvis_message
                ui_jarvis_message(response)
            except:
                pass
            threading.Thread(target=speak, args=(response,), daemon=True).start()
            return {
                "status": "success",
                "response": response
            }

        # Check if the user is greeting JARVIS
        greeting_keywords = ["hey jarvis", "hi jarvis", "hello jarvis", "whats up", "what's up", "how are you"]
        exact_greetings = ["hi", "hello", "hey"]
        if any(kw in input_clean for kw in greeting_keywords) or input_clean in exact_greetings:
            if "what's up" in input_clean or "whats up" in input_clean:
                response = "Good to see you, Sir. All core systems are online and operating normally. I'm ready to assist you."
            else:
                from Brain.time_helper import get_sophisticated_greeting
                response = get_sophisticated_greeting()
            from TextToSpeech.Fast_DF_TTS import speak
            import threading
            try:
                from shared_state import ui_jarvis_message
                ui_jarvis_message(response)
            except:
                pass
            threading.Thread(target=speak, args=(response,), daemon=True).start()
            return {
                "status": "success",
                "response": response
            }

        # Step 0b: Detect ambiguous/nonsensical phrases
        ambiguity_question = self._detect_ambiguity(user_input)
        if ambiguity_question:
            # Don't execute — ask the user to clarify first
            from TextToSpeech.Fast_DF_TTS import speak
            speak(ambiguity_question)
            return {
                "status": "clarification",
                "intent": "FOLLOW_UP",
                "response": ambiguity_question,
            }

        # Step 0c: Emergency STOP check
        try:
            from SpeechToText.speech_buffer import SpeechBuffer
            if SpeechBuffer.is_stop_command(user_input):
                from shared_state import stop_all_operations
                stop_msg = stop_all_operations()
                from TextToSpeech.Fast_DF_TTS import speak
                speak("All operations stopped, Sir.")
                return {
                    "status": "stopped",
                    "intent": "STOP",
                    "response": stop_msg
                }
        except Exception as e:
            print(f"[PrimaryBrain] Stop check exception: {e}")


        # Step 1: Build memory context
        memory_context = self._build_memory_context(user_input)

        # Step 1b: Build proactive schedule awareness (for referenced day)
        schedule_awareness = self._build_schedule_awareness(user_input)

        # Step 2: Schedule conflict check is now INTEGRATED into the proactive
        # pipeline (_proactive_calendar_create) â€” no separate classifier call needed.
        # The proactive pipeline stores to memory, checks conflicts, AND creates
        # Google Calendar events all in one pass.
        conflict_warning = ""

        # Step 2b: AGENT COMMAND PRE-CHECK
        # Commands like "chat with CONTACT_NAME_TWO that i am busy" contain "i am "
        # which would falsely trigger _is_conversational(). Detect agent intents
        # FIRST and route them directly to IntentRouter (Step 5).
        is_agent_cmd = self._is_agent_command(user_input)
        if is_agent_cmd:
            print(f"[PrimaryBrain] Agent command detected -> skipping conversational, routing to IntentRouter")

        # Step 3: If conversational OR has schedule context â†’ use LLM with full context
        # This ensures schedule-related messages ALWAYS get the proactive awareness treatment
        # BUT: never intercept agent commands (WhatsApp, Browser, etc.)
        if not is_agent_cmd and (self._is_conversational(user_input) or conflict_warning or schedule_awareness):
            result = self._conversational_response(
                user_input, memory_context, conflict_warning, schedule_awareness
            )
            self._post_process(user_input, result)
            return result

        # Step 4: Deep thinking check
        if self.needs_deep_thinking(user_input):
            secondary = self._get_secondary()
            if secondary and secondary.is_available():
                print("[PrimaryBrain] â†’ Routing to Secondary Brain")
                result = secondary.process(user_input, context=memory_context)
                self._post_process(user_input, result)
                return result

        # Step 4.5: Pre-LLM rule-based check to optimize latency and prevent sub-agent errors
        try:
            from Automations.Automation_Brain import process_rule_based
            if process_rule_based(user_input):
                result = {"status": "success", "intent": "RULE_BASED", "response": ""}
                self._post_process(user_input, result)
                return result
        except Exception as e:
            print(f"[PrimaryBrain] Pre-LLM rule-based check error: {e}")

        # Step 5: Standard tool/action processing via IntentRouter
        result = process_command(user_input)

        # Step 5b: Immediate rule-based fallback if IntentRouter couldn't handle it
        if result.get("status") != "success":
            print("[PrimaryBrain] LLM Router couldn't handle, trying rule-based...")
            try:
                from Automations.Automation_Brain import process_rule_based
                if process_rule_based(user_input):
                    result = {"status": "success", "intent": "RULE_BASED", "response": ""}
            except Exception as e:
                print(f"[PrimaryBrain] Rule-based fallback error: {e}")

        # Step 5c: Conversation FALLBACK â€” if STILL unknown/clarification,
        # use LLM for a real conversational response with memory context instead of generic text
        if self._is_fallback_needed(result):
            print("[PrimaryBrain] IntentRouter & Rules returned unknown -> LLM conversational fallback")
            result = self._conversational_response(user_input, memory_context, schedule_awareness=schedule_awareness)

        # Step 6: Post-process (store memory + log conversation)
        self._post_process(user_input, result)

        return result

    def _is_fallback_needed(self, result: dict) -> bool:
        """Check if the IntentRouter result is a generic/unknown response that needs LLM."""
        if not isinstance(result, dict):
            return True
        
        response = str(result.get("response", result.get("message", ""))).lower()
        intent = str(result.get("intent", "")).lower()
        
        fallback_phrases = [
            "could you please be more specific",
            "i'm not sure what you'd like",
            "could you rephrase",
            "don't understand",
            "try rephrasing",
        ]
        
        if intent in ("unknown", "clarification", "unclear", ""):
            return True
        if any(p in response for p in fallback_phrases):
            return True
        
        return False

    def _build_memory_context(self, user_input: str) -> str:
        """Build the full memory context string for the LLM."""
        if not self.memory or not self.memory.is_available():
            return ""

        parts = []

        try:
            # Use smart_recall_context for focused, relevant context
            smart_ctx = self.memory.smart_recall_context(user_input)
            if smart_ctx:
                parts.append(smart_ctx)
            else:
                # Fallback to basic recall
                relevant = self.memory.recall(user_input)
                if relevant:
                    parts.append(f"WHAT I KNOW ABOUT YOU:\n{relevant}")

            # Recent conversation context
            convo_context = self.memory.get_conversation_context(limit=3)
            if convo_context:
                parts.append(convo_context)
        except Exception as e:
            print(f"[PrimaryBrain] Memory recall error: {e}")

        return "\n\n".join(parts)

    def _fetch_google_calendar_events(self, ref_date: str) -> list:
        """
        Fetch events from Google Calendar for a specific date.
        Returns a list of dicts with keys: title, start_time, end_time, location.
        """
        try:
            from Brain.google_workspace_client import get_google_client
            client = get_google_client()

            time_min = f"{ref_date}T00:00:00+05:30"
            # next day midnight
            next_day = (datetime.strptime(ref_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            time_max = f"{next_day}T00:00:00+05:30"

            result = client.calendar_get_events(time_min=time_min, time_max=time_max)

            if result.get("status") != "success":
                print(f"[PrimaryBrain] Google Calendar fetch failed: {result.get('error')}")
                return []

            gcal_events = []
            for ev in result.get("data", {}).get("events", []):
                # Parse ISO start/end into HH:MM for display
                start_iso = ev.get("start", "")
                end_iso = ev.get("end", "")
                start_hhmm = ""
                end_hhmm = ""
                try:
                    if start_iso:
                        from datetime import datetime as _dt
                        # Handle both "Z" and "+05:30" suffixes
                        s = start_iso.replace("Z", "+00:00")
                        start_hhmm = _dt.fromisoformat(s).strftime("%H:%M")
                    if end_iso:
                        e = end_iso.replace("Z", "+00:00")
                        end_hhmm = _dt.fromisoformat(e).strftime("%H:%M")
                except Exception:
                    pass

                gcal_events.append({
                    "title": ev.get("title", "Untitled"),
                    "start_time": start_hhmm,
                    "end_time": end_hhmm,
                    "location": ev.get("location", ""),
                    "people": "",
                    "source": "google_calendar",
                })

            print(f"[PrimaryBrain] Google Calendar: {len(gcal_events)} event(s) on {ref_date}")
            return gcal_events

        except Exception as e:
            print(f"[PrimaryBrain] Google Calendar fetch error: {e}")
            return []

    def _build_schedule_awareness(self, user_input: str) -> str:
        """
        Build proactive schedule awareness context.
        
        When the user mentions a day (today, tomorrow, Monday, etc.),
        look up ALL events for that day from BOTH local memory AND Google Calendar,
        then merge them to give the LLM a complete picture.
        """
        if not self._has_schedule_intent(user_input):
            return ""
        
        try:
            ref_date = self._extract_referenced_date(user_input)
            
            # â”€â”€ Get events from BOTH sources â”€â”€
            # 1. Local memory (SQLite)
            local_events = []
            if self.memory and self.memory.is_available():
                local_events = self.memory.get_schedule(ref_date)

            # 2. Google Calendar (live)
            gcal_events = self._fetch_google_calendar_events(ref_date)

            # â”€â”€ Merge & deduplicate â”€â”€
            # Use title similarity to avoid duplicates (local memory + gcal may overlap)
            all_events = list(local_events)  # start with local
            local_titles = {e.get("title", "").lower().strip() for e in local_events}
            for ge in gcal_events:
                ge_title = ge.get("title", "").lower().strip()
                # Skip if a local event already has a very similar title
                if ge_title and ge_title not in local_titles:
                    all_events.append(ge)

            # Also get tomorrow's schedule if user mentions "today" (for awareness)
            today = datetime.now().strftime("%Y-%m-%d")
            tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            
            # Format the referenced date as human-readable
            ref_dt = datetime.strptime(ref_date, "%Y-%m-%d")
            if ref_date == today:
                day_label = "TODAY"
            elif ref_date == tomorrow:
                day_label = "TOMORROW"
            else:
                day_label = ref_dt.strftime("%A, %B %d")
            
            parts = []
            
            if all_events:
                parts.append(f"EXISTING SCHEDULE FOR {day_label} ({ref_date}):")
                for e in all_events:
                    time_str = ""
                    if e.get("start_time"):
                        time_str = e["start_time"]
                        if e.get("end_time"):
                            time_str += f"-{e['end_time']}"
                    people_str = f" with {e['people']}" if e.get('people') else ""
                    loc_str = f" at {e['location']}" if e.get('location') else ""
                    source_tag = " [GCal]" if e.get("source") == "google_calendar" else ""
                    parts.append(f"  - {time_str} {e['title']}{people_str}{loc_str}{source_tag}".strip())
                
                # Check if user's plan might conflict
                input_lower = user_input.lower()
                whole_day_signals = ["whole day", "all day", "entire day", "full day",
                                    "the whole", "planning to make a project"]
                if any(s in input_lower for s in whole_day_signals):
                    parts.append(f"\nWARNING: The user wants to use the WHOLE DAY but has {len(all_events)} existing event(s). You MUST warn them!")
            else:
                parts.append(f"SCHEDULE FOR {day_label} ({ref_date}): No events scheduled. The day is completely free.")
            
            return "\n".join(parts)
            
        except Exception as e:
            print(f"[PrimaryBrain] Schedule awareness error: {e}")
            return ""

    def _check_schedule_conflict(self, user_input: str) -> str:
        """
        Pre-check for schedule conflicts ONLY (does NOT store to memory).
        Storage is handled by _proactive_calendar_create() in the conversational path.
        
        If user says "lunch with CONTACT_NAME_ONE at 3pm" and they have a meeting 2-3pm,
        generate a conflict warning string.
        """
        if not self.memory:
            return ""

        try:
            if self.classifier and self.classifier.is_available():
                decision = self.classifier.classify(user_input)
                
                if decision.get("type") == "schedule" and decision.get("store"):
                    # Check if it would conflict, but DON'T store yet
                    # (storage + Google Calendar creation happens in _proactive_calendar_create)
                    date = decision.get("date", datetime.now().strftime("%Y-%m-%d"))
                    start_time = decision.get("start_time")
                    
                    if start_time:
                        events = self.memory.get_schedule(date)
                        for e in events:
                            if e.get("start_time") and start_time:
                                # Simple overlap check
                                existing_start = e["start_time"]
                                existing_end = e.get("end_time", "")
                                if existing_start <= start_time and existing_end and existing_end > start_time:
                                    return f"You already have '{e['title']}' from {existing_start} to {existing_end} on {date}."
        except Exception as e:
            print(f"[PrimaryBrain] Schedule check error: {e}")
        
        return ""

    # ===== PROACTIVE INTELLIGENCE =====

    def _needs_proactive_weather(self, user_input: str) -> bool:
        """Detect if the user's plan involves outdoor/travel that benefits from weather info."""
        input_lower = user_input.lower()
        outdoor_signals = [
            "road trip", "trip", "travel", "traveling", "travelling",
            "drive", "driving", "ride", "riding", "long drive",
            "picnic", "outdoor", "hike", "hiking", "trek", "trekking",
            "beach", "camping", "outing", "bbq", "barbecue",
            "walk", "jogging", "running", "cycling", "biking",
            "garden", "park", "zoo", "amusement", "sports",
            "cricket", "football", "match", "game outside",
            "going out", "go out", "head out", "stepping out",
        ]
        return any(s in input_lower for s in outdoor_signals)

    def _proactive_weather_check(self) -> str:
        """Fetch weather data proactively for the user's location."""
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            from Tools.weather import get_weather_by_address
            report = get_weather_by_address("Hyderabad, Telangana, India")
            if report and "Error" not in report and "Could not" not in report:
                print(f"[PrimaryBrain] Proactive weather fetched: {report[:80]}...")
                return report
        except Exception as e:
            print(f"[PrimaryBrain] Proactive weather error: {e}")
        return ""

    def _proactive_calendar_create(self, user_input: str) -> dict:
        """
        Extract schedule details via MemoryClassifier and create Google Calendar event.
        Only runs when the user mentions a SPECIFIC time/date â€” otherwise there's nothing
        useful to put on a calendar.
        Returns the classifier decision dict (with calendar result) or empty dict.
        """
        input_lower = user_input.lower()

        # Fast gate: skip if no concrete time/date signal.
        # "road trip" without "at 4pm" or "tomorrow" â†’ no calendar event.
        time_signals = [
            "at ", "pm", "am", "o'clock",
            "tomorrow", "today", "tonight",
            "monday", "tuesday", "wednesday", "thursday", "friday",
            "saturday", "sunday", "next week", "this weekend",
            "morning", "afternoon", "evening",
        ]
        if not any(sig in input_lower for sig in time_signals):
            print("[PrimaryBrain] Calendar skip: no specific time/date in input")
            return {}

        if not self.classifier or not self.classifier.is_available():
            return {}

        print("[PrimaryBrain] Extracting schedule from input for calendar...")

        try:
            decision = self.classifier.classify(user_input)

            if decision.get("type") != "schedule" or not decision.get("store"):
                return {}

            title = decision.get("title", "Event")
            date = decision.get("date", datetime.now().strftime("%Y-%m-%d"))
            start_time = decision.get("start_time")
            end_time = decision.get("end_time")
            people = decision.get("people", "")
            location = decision.get("location", "")

            # --- Store to local memory (SQLite) ---
            if self.memory and self.memory.is_available():
                mem_result = self.memory.add_schedule(
                    title=title, date=date,
                    start_time=start_time, end_time=end_time,
                    people=people, location=location,
                )
                if mem_result.get("has_conflict"):
                    decision["conflict"] = mem_result.get("suggestion", "Scheduling conflict detected.")
                print(f"[PrimaryBrain] Schedule stored to memory: {title} on {date} {start_time or ''}")

            # --- Create Google Calendar event ---
            if start_time:
                try:
                    from Brain.google_workspace_client import get_google_client
                    client = get_google_client()

                    # Build ISO timestamps with IST offset
                    cal_start = f"{date}T{start_time}:00+05:30"
                    if end_time:
                        cal_end = f"{date}T{end_time}:00+05:30"
                    else:
                        # Default 1 hour
                        from datetime import datetime as dt_cls
                        st = dt_cls.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
                        et = st + timedelta(hours=1)
                        cal_end = et.strftime(f"%Y-%m-%dT%H:%M:00+05:30")

                    cal_result = client.calendar_create_event(
                        title=title,
                        start_time=cal_start,
                        end_time=cal_end,
                        description=f"Created proactively by JARVIS from: '{user_input[:120]}'",
                        location=location,
                    )

                    if cal_result.get("status") == "success":
                        decision["calendar_created"] = True
                        print(f"[PrimaryBrain] Google Calendar event created: {title}")
                    else:
                        decision["calendar_created"] = False
                        print(f"[PrimaryBrain] Google Calendar creation failed: {cal_result.get('error')}")
                except Exception as e:
                    print(f"[PrimaryBrain] Google Calendar error: {e}")
                    decision["calendar_created"] = False

            return decision

        except Exception as e:
            print(f"[PrimaryBrain] Proactive calendar error: {e}")
            return {}

    def _execute_proactive_actions(self, user_input: str) -> dict:
        """
        Analyze user input for IMPLICIT action needs and execute them.
        This is what makes JARVIS proactively intelligent â€” the user says
        "I have a meeting tomorrow at 4pm and going on a road trip"
        and JARVIS automatically:
          1. Creates a Google Calendar event for the meeting
          2. Checks the weather for the road trip
        
        Runs actions in PARALLEL to minimize latency.
        Returns dict of action results to enrich the conversational response.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time as _time

        results = {}
        futures = {}
        t0 = _time.time()

        need_calendar = self._has_schedule_intent(user_input)
        need_weather = self._needs_proactive_weather(user_input)

        if not need_calendar and not need_weather:
            return results

        print(f"[PrimaryBrain] Proactive actions starting: "
              f"calendar={'yes' if need_calendar else 'no'}, "
              f"weather={'yes' if need_weather else 'no'}")

        # Run independent actions in parallel threads
        with ThreadPoolExecutor(max_workers=2) as pool:
            if need_calendar:
                futures["calendar"] = pool.submit(self._proactive_calendar_create, user_input)
            if need_weather:
                futures["weather"] = pool.submit(self._proactive_weather_check)

            for key, future in futures.items():
                try:
                    result = future.result(timeout=15)
                    if result:
                        results[key] = result
                except Exception as e:
                    print(f"[PrimaryBrain] Proactive {key} failed: {e}")

        elapsed = _time.time() - t0
        if results:
            actions_taken = ", ".join(results.keys())
            print(f"[PrimaryBrain] Proactive actions done in {elapsed:.1f}s: {actions_taken}")
        else:
            print(f"[PrimaryBrain] No proactive actions produced results ({elapsed:.1f}s)")

        return results

    def _build_proactive_context(self, proactive_results: dict) -> str:
        """Build SHORT context string from proactive action results for the LLM.
        Kept concise to reduce prompt size and speed up inference."""
        parts = []

        cal = proactive_results.get("calendar")
        if cal:
            title = cal.get("title", "event")
            date = cal.get("date", "")
            start = cal.get("start_time", "")
            created = cal.get("calendar_created", False)
            conflict = cal.get("conflict", "")

            if created:
                parts.append(f"ACTION DONE: Added '{title}' on {date} at {start} to Google Calendar. Confirm this to user.")
            else:
                parts.append(f"NOTED: '{title}' on {date} at {start} stored in memory. Confirm you'll remember.")
            if conflict:
                parts.append(f"CONFLICT: {conflict}")

        weather = proactive_results.get("weather")
        if weather:
            # Extract just the key weather info (1-2 lines) instead of full report
            lines = weather.strip().split('\n')
            summary_parts = []
            for line in lines:
                if any(k in line.lower() for k in ['weather:', 'temperature:', 'feels like:']):
                    summary_parts.append(line.strip())
            weather_summary = '. '.join(summary_parts) if summary_parts else lines[1] if len(lines) > 1 else weather[:100]
            parts.append(f"WEATHER: {weather_summary}. Use this in your response for user's outdoor/trip plans.")

        return "\n".join(parts)

    def _build_proactive_fallback(self, proactive_results: dict) -> str:
        """Build a spoken fallback when LLM times out but proactive actions succeeded."""
        parts = []
        cal = proactive_results.get("calendar")
        weather = proactive_results.get("weather")

        if cal:
            title = cal.get("title", "your event")
            start = cal.get("start_time", "")
            created = cal.get("calendar_created", False)
            if created:
                parts.append(f"Done sir, I've added '{title}' at {start} to your calendar.")
            else:
                parts.append(f"Noted sir, I'll remember '{title}' at {start}.")

        if weather:
            lines = weather.strip().split('\n')
            temp_line = ""
            cond_line = ""
            for line in lines:
                if 'temperature:' in line.lower():
                    temp_line = line.split(':', 1)[-1].strip()
                elif 'weather:' in line.lower():
                    cond_line = line.split(':', 1)[-1].strip()
            if temp_line or cond_line:
                w_info = f"{cond_line}, {temp_line}" if cond_line and temp_line else (cond_line or temp_line)
                parts.append(f"Weather looks like {w_info} right now, decent for your plans.")
            else:
                parts.append("I checked the weather, conditions look reasonable for your plans.")

        if not parts:
            return "I'm here sir, what do you need?"
        return " ".join(parts)

    # ===== CONVERSATIONAL RESPONSE (now with proactive intelligence) =====

    def _conversational_response(self, user_input: str,
                                  memory_context: str,
                                  conflict_warning: str = "",
                                  schedule_awareness: str = "") -> dict:
        """
        Generate a conversational, memory-aware response WITH proactive intelligence.
        
        JARVIS doesn't just chat â€” it ACTS:
        - Schedule mention â†’ creates Google Calendar event automatically
        - Trip/outdoor mention â†’ checks weather proactively
        - Weaves action results into natural conversation
        """
        if not OLLAMA_AVAILABLE:
            return {
                "status": "error",
                "response": "I'm having trouble thinking right now, sir."
            }

        try:
            import time as _time

            # â”€â”€ Phase 1: Execute proactive actions FIRST â”€â”€
            print("[PrimaryBrain] Phase 1: Checking proactive actions...")
            proactive_results = self._execute_proactive_actions(user_input)
            proactive_context = self._build_proactive_context(proactive_results)

            # â”€â”€ Phase 2: Build system message with ALL context â”€â”€
            print("[PrimaryBrain] Phase 2: Generating response...")
            t_llm = _time.time()

            # Keep system prompt CONCISE for faster inference
            is_informational = False
            informational_keywords = ["tell me about", "explain", "what is", "what are", "who is", "who was", "where is", "when is", "history of", "how does", "tell me what", "information on", "about "]
            input_lower = user_input.lower()
            if any(kw in input_lower for kw in informational_keywords):
                is_informational = True

            rules = (
                "Provide a comprehensive, informative, and detailed answer. Explain fully and clearly. "
                "Speak naturally like a human assistant, but do not restrict yourself to 1-3 sentences. Use 'sir' occasionally."
                if is_informational else
                "Rules: 1-3 sentences max. Warm, natural, human. Use 'sir' sometimes. NEVER explain reasoning."
            )
            system_parts = [
                f"You are JARVIS, a personal AI assistant. Current: {datetime.now().strftime('%A, %B %d, %Y %I:%M %p')}.",
                rules,
            ]
            if memory_context:
                # Trim memory to essentials
                system_parts.append(memory_context[:500])
            if schedule_awareness:
                system_parts.append(schedule_awareness[:300])
            if conflict_warning:
                system_parts.append(f"CONFLICT: {conflict_warning}")
            if proactive_context:
                system_parts.append(proactive_context)

            system_msg = "\n".join(system_parts)

            # Build chat messages (system + recent context + current user message)
            messages = [{"role": "system", "content": system_msg}]

            # Inject recent conversation history for continuity (1 turn for speed)
            if self.memory and self.memory.is_available():
                recent = self.memory.get_recent_conversations(limit=1)
                for conv in reversed(recent):  # oldest first
                    messages.append({"role": "user", "content": conv["user_input"][:100]})
                    messages.append({"role": "assistant", "content": conv["jarvis_response"][:150]})

            messages.append({"role": "user", "content": user_input})

            # Call LLM with timeout to prevent blocking forever
            llm_result = [None]
            llm_error = [None]

            def _call_llm():
                try:
                    llm_result[0] = ollama.chat(
                        model=self.model,
                        messages=messages,
                        options={
                            "temperature": 0.5,
                            "num_predict": 600 if is_informational else 200,  # Dynamically set budget
                            "top_p": 0.9,
                            "repeat_penalty": 1.1,
                        }
                    )
                except Exception as e:
                    llm_error[0] = e

            llm_thread = threading.Thread(target=_call_llm, daemon=True)
            llm_thread.start()
            llm_thread.join(timeout=120)  # Max 120 seconds for LLM

            llm_elapsed = _time.time() - t_llm

            if llm_thread.is_alive() or llm_error[0]:
                # LLM timed out or errored â€” use proactive fallback
                if llm_thread.is_alive():
                    print(f"[PrimaryBrain] LLM timed out after {llm_elapsed:.1f}s, using fallback")
                else:
                    print(f"[PrimaryBrain] LLM error: {llm_error[0]}")
                answer = self._build_proactive_fallback(proactive_results)
            else:
                print(f"[PrimaryBrain] LLM response generated in {llm_elapsed:.1f}s")
                response = llm_result[0]
                # With think=True, content is cleanly separated from thinking
                answer = (response.message.content or "").strip() if response else ""
                thinking_len = len(getattr(response.message, 'thinking', '') or '') if response else 0
                print(f"[PrimaryBrain] Thinking: {thinking_len} chars, Content: {len(answer)} chars")
            
            # Sanitize for Windows console â€” replace non-ASCII with close equivalents
            answer = answer.replace('\u00b0', ' degrees ')  # Â° â†’ degrees
            answer = answer.replace('\u2014', ' - ')  # em dash
            answer = answer.replace('\u2013', ' - ')  # en dash
            answer = answer.replace('\u2018', "'").replace('\u2019', "'")  # smart quotes
            answer = answer.replace('\u201c', '"').replace('\u201d', '"')
            answer = answer.encode('ascii', errors='ignore').decode('ascii').strip()
            
            if not answer or len(answer) < 3:
                # Construct a meaningful fallback based on proactive actions
                if proactive_results.get("calendar"):
                    cal = proactive_results["calendar"]
                    answer = f"Got it sir, I've added '{cal.get('title', 'your event')}' to your calendar."
                    if proactive_results.get("weather"):
                        answer += " I also checked the weather for your trip â€” looks like good conditions."
                elif proactive_results.get("weather"):
                    answer = "Noted sir. I checked the weather for your plans â€” conditions look reasonable."
                else:
                    answer = "I'm here sir, what do you need?"

            # Format clean, complete speech text without cutting off mid-sentence
            clean_speech = re.sub(r'[*#_`~|]', '', answer)
            clean_speech = re.sub(r'\n+', '. ', clean_speech)
            clean_speech = re.sub(r'\s+', ' ', clean_speech).strip()

            if len(clean_speech) > 1200:
                truncated = clean_speech[:1200]
                last_p = truncated.rfind('.')
                if last_p > 250:
                    clean_speech = truncated[:last_p + 1] + " Sir, I have displayed the full detailed explanation in your console."

            try:
                from shared_state import ui_jarvis_message
                ui_jarvis_message(answer)
            except Exception as e:
                print(f"[PrimaryBrain] UI message log error: {e}")

            threading.Thread(target=speak, args=(clean_speech,), daemon=True).start()


            return {
                "status": "success",
                "intent": "CONVERSATIONAL",
                "response": answer,
                "model": self.model,
                "had_conflict": bool(conflict_warning),
                "proactive_actions": list(proactive_results.keys()),
            }

        except Exception as e:
            print(f"[PrimaryBrain] Smart response error: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e),
                    "response": "I ran into an issue, sir."}

    def _post_process(self, user_input: str, result: dict):
        """Store to memory + log conversation (async, non-blocking).
        
        If proactive_actions were already executed (calendar created, etc.),
        skip re-classification to avoid double-storing schedule events.
        """
        # Check if proactive actions already classified and stored this input
        proactive_handled = bool(result.get("proactive_actions"))

        def _store():
            try:
                # 1. Classify and store memories/schedule (skip if proactive actions handled it)
                if self.classifier and not proactive_handled:
                    self.classifier.classify_and_store(user_input, result)
                elif self.classifier and proactive_handled:
                    # Still classify for non-schedule memories (personal facts, preferences)
                    # but don't re-store schedule events
                    decision = self.classifier.classify(user_input, result)
                    if decision.get("store") and decision.get("type") == "memory":
                        from Brain.Memory.memory_manager import get_memory
                        mm = get_memory()
                        if mm.is_available():
                            mm.store(
                                category=decision.get("category", "context"),
                                key=decision.get("key", "unknown"),
                                value=decision.get("value", user_input),
                                source="conversation",
                                confidence=decision.get("confidence", 0.9),
                            )
                
                # 2. Log conversation
                if self.memory and self.memory.is_available():
                    response_text = result.get("response", str(result))
                    intent = result.get("intent", "")
                    self.memory.log_conversation(user_input, response_text[:500], intent)
            except Exception as e:
                print(f"[PrimaryBrain] Post-process error: {e}")

        threading.Thread(target=_store, daemon=True).start()


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================
_primary_brain = None


def get_primary_brain() -> PrimaryBrain:
    """Get the global PrimaryBrain instance."""
    global _primary_brain
    if _primary_brain is None:
        _primary_brain = PrimaryBrain()
    return _primary_brain

