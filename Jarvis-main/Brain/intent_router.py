"""
Intent Router for JARVIS Voice Assistant.
Routes classified intents to appropriate tool handlers or response generators.

CONNECTIONS:
    IntentRouter
    â”œâ”€â”€ ToolsRegistry         â€” 30+ registered tools
    â”œâ”€â”€ Agents/               â€” WhatsApp, Browser, RAG agents
    â”œâ”€â”€ Automations/          â€” Custom workflows, Webhooks
    â”œâ”€â”€ Laptop_Controls/      â€” System controls (brightness, volume, etc.)
    â””â”€â”€ Tools/ (via ToolsProvider) â€” universally accessible utilities
"""

import sys
import os
import re as _re
from typing import Optional, Dict, Any
import threading

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Brain.intent_engine import IntentEngine, IntentResult, get_engine
from Brain.tools_registry import ToolsRegistry, get_registry
from TextToSpeech.Fast_DF_TTS import speak

# JARVIS UI integration
from shared_state import ui_jarvis_message, ui_tool_message, show_results_in_popup


def _safe_print(msg: str):
    """Print safely â€” replaces unencodable characters instead of crashing."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', errors='replace').decode('ascii'))


class IntentRouter:
    """
    Routes intents to appropriate handlers.
    
    Connections:
    1. ToolsRegistry    â†’ Registered tool functions (30+)
    2. Agents/          â†’ WhatsApp Agent, Browser Agent, RAG Agent
    3. Automations/     â†’ Custom workflows, Webhooks (n8n)
    4. Laptop_Controls/ â†’ System-level controls
    5. Tools/           â†’ Universal tools (weather, MCP, file, etc.)
    
    Flow:
    1. Receive IntentResult from IntentEngine
    2. Validate confidence and parameters
    3. Route to:
       - Tool Executor (for ACTION intents)
       - Agents (for agent-specific tasks)
       - Automations (for workflow/webhook triggers)
       - Laptop Controls (for system actions)
       - Response Generator (for QUERY intents)
       - Clarification Handler (for UNKNOWN intents)
    """
    
    CONFIDENCE_THRESHOLD = 0.7

    # â”€â”€ WhatsApp fast-path â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Matches the canonical form produced by TaskExecutor._build_chained_task_text():
    #   "whatsapp <contact> saying <message content>"
    # This bypasses LLM classification entirely â€” important when <message content>
    # contains hundreds of characters (e.g. GitHub search results with pipes).
    _WA_FAST_RE = _re.compile(
        r'^whatsapp\s+(\w+)\s+saying\s+(.+)$',
        _re.IGNORECASE | _re.DOTALL
    )

    def _try_whatsapp_fast_path(self, user_input: str):
        """
        Regex-only shortcut for chained WhatsApp send commands.

        Detects: "whatsapp <contact> saying <message>"
        Returns an IntentResult if matched, or None to fall through to LLM.

        Why this exists:
          When a chained task produces search results and rewrites the task as
          "whatsapp CONTACT_NAME_TWO saying Found 5 GitHub repos...", the 1100-char
          pipe-heavy payload confuses the LLM JSON generator, producing
          UNKNOWN intent and wasting 100+ seconds.  This pure-regex path is
          O(1) and never fails.
        """
        m = self._WA_FAST_RE.match(user_input.strip())
        if not m:
            return None
        contact = m.group(1).strip()
        message = m.group(2).strip()
        _safe_print(f"[Router] WhatsApp fast-path matched: contact={contact}, msg_len={len(message)}")
        from Brain.intent_engine import IntentResult
        return IntentResult(
            intent="AUTOMATION_WHATSAPP",
            confidence=0.99,
            tool="send_whatsapp",
            params={"contact": contact, "message": message, "mode": "single"},
            response=None,
            raw_output="fast_path",
        )
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def __init__(self, engine: IntentEngine = None, registry: ToolsRegistry = None):
        """
        Initialize the router with connections to all subsystems.
        
        Args:
            engine: IntentEngine instance (uses global if not provided)
            registry: ToolsRegistry instance (uses global if not provided)
        """
        self.engine = engine or get_engine()
        self.registry = registry or get_registry()
        
        # Direct connections â€” lazy-loaded for fast startup
        self._tools_provider = None
        self._agents_provider = None
        self._automations_provider = None
        self._controls_provider = None
    
    @property
    def tools(self):
        """Universal tools provider â€” weather, MCP, files, simple automations."""
        if self._tools_provider is None:
            from Brain.tools_provider import get_tools
            self._tools_provider = get_tools()
        return self._tools_provider
    
    @property
    def agents(self):
        """Agents provider â€” routes to WhatsApp, Browser, RAG."""
        if self._agents_provider is None:
            from Agents.agents_provider import get_agents
            self._agents_provider = get_agents()
        return self._agents_provider
    
    @property
    def automations(self):
        """Automations provider â€” routes to workflows, webhooks."""
        if self._automations_provider is None:
            from Automations.automations_provider import get_automations
            self._automations_provider = get_automations()
        return self._automations_provider
    
    @property
    def controls(self):
        """Laptop controls provider â€” brightness, volume, WiFi, power."""
        if self._controls_provider is None:
            from Laptop_Controls.controls_provider import get_controls
            self._controls_provider = get_controls()
        return self._controls_provider
    
    def process(self, user_input: str) -> Dict[str, Any]:
        """
        Process user input end-to-end.

        Args:
            user_input: Transcribed user speech

        Returns:
            Dict with status, intent, and any results/responses
        """
        _safe_print(f"[Router] Processing: '{user_input[:100]}'")

        # â”€â”€ FAST PATH 1: WhatsApp chained send â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # Must be checked FIRST â€” before any LLM call â€” so that large chained
        # payloads (GitHub results, email summaries, etc.) are dispatched to
        # the WhatsApp agent directly without confusing the JSON classifier.
        fast_wa = self._try_whatsapp_fast_path(user_input)
        if fast_wa:
            return self._handle_action(fast_wa, user_input)
        # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

        # HARDCODED RESEARCH TRIGGER (User Request: "paste teh promtp")
        if "research" in user_input.lower():
            print(f"[Router] Hardcoded keyword 'research' detected -> Forcing ChatGPT")
            # Create a synthetic result to bypass LLM classification
            from Brain.intent_engine import IntentResult
            # We use the raw input as the query since we are bypassing the LLM's query improvement
            result = IntentResult(
                intent="RESEARCH",
                confidence=1.0,
                tool="research_chatgpt",
                params={
                    "original_query": user_input, 
                    "improved_query": user_input # Pass through raw query
                },
                response=None,
                raw_output="hardcoded_research"
            )
        else:
            # Step 1: Classify intent via LLM
            result = self.engine.classify(user_input)
        
        # Normalize result for small models (semantic search intent correction)
        if result:
            intent_lower = str(result.intent).lower()
            tool_lower = str(result.tool).lower() if result.tool else ""
            
            if "search" in intent_lower or "search" in tool_lower:
                query = result.params.get("query") or result.params.get("search_query") or result.params.get("q")
                if not query:
                    import re
                    query = user_input
                    query = re.sub(r'^(?:open\s+)?(?:google|youtube)\s+(?:and\s+)?search\s+(?:for\s+)?', '', query, flags=re.IGNORECASE)
                    query = re.sub(r'^search\s+(?:for\s+)?', '', query, flags=re.IGNORECASE)
                    query = re.sub(r'\s+in\s+google$', '', query, flags=re.IGNORECASE)
                    query = re.sub(r'\s+on\s+google$', '', query, flags=re.IGNORECASE)
                    query = re.sub(r'\s+in\s+youtube$', '', query, flags=re.IGNORECASE)
                    query = re.sub(r'\s+on\s+youtube$', '', query, flags=re.IGNORECASE)
                    query = query.strip()
                
                site = "google"
                if "youtube" in user_input.lower() or "youtube" in intent_lower or "youtube" in tool_lower:
                    site = "youtube"
                
                result.intent = "OPEN_WEB"
                result.tool = "open_web"
                result.params = {"site_name": site, "search_query": query}
                print(f"[Router] Normalized search hallucination to OPEN_WEB (site: {site}, query: '{query}')")
        
        print(f"[Router] Intent: {result.intent} (confidence: {result.confidence:.2f})")
        
        # Step 2: Route based on intent type
        if result.needs_clarification():
            return self._handle_clarification(result, user_input)
        
        if result.is_unknown():
            return self._handle_unknown(result)
        
        # Check actions FIRST (includes QUERY_WEATHER which uses real tools)
        if result.is_action():
            return self._handle_action(result, user_input)
        
        # Then handle general queries (LLM-answered)
        if result.is_query():
            return self._handle_query(result, user_input)
        
        # Fallback
        return self._handle_unknown(result)
    
    # Intent-to-Agent routing map
    AGENT_INTENTS = {
        "AUTOMATION_WHATSAPP": "whatsapp",
        "AUTOMATION_WHATSAPP_CHAT": "whatsapp",
        "BROWSER_AUTOMATION": "browser",
        "RESEARCH": "rag",
    }

    def _handle_action(self, result: IntentResult, user_input: str) -> Dict[str, Any]:
        """Execute a tool based on the intent. Routes to agents when appropriate."""
        tool_name = result.tool
        params = result.params
        
        print(f"[Router] Executing tool: {tool_name} with params: {params}")
        
        # ===== AGENT ROUTING =====
        # Check if this intent should be handled by a dedicated agent
        agent_type = self.AGENT_INTENTS.get(result.intent)
        if agent_type:
            print(f"[Router] Routing to {agent_type} agent...")
            return self._route_to_agent(agent_type, user_input, result)
        
        spoken = False
        # Check for conversational prefix/response (Emotional Intelligence)
        if result.response:
            _safe_print(f"[Router] Conversational response: {result.response}")
            speak_async(result.response)
            spoken = True
        
        try:
            # Execute the tool (non-agent tools: weather, spotify, system, etc.)
            tool_result = self.registry.execute(tool_name, params)
            
            # Check if this tool already handled its own speaking response
            tool_spoken = tool_name in [
                "get_weather", "gmail_check_unread", "gmail_summarize", 
                "gmail_search", "calendar_today", "calendar_create_event", 
                "drive_list"
            ]
            
            if not spoken and not tool_spoken:
                # Generate natural speaking confirmation for the user
                confirm_msg = "Okay sir, executing that action."
                if tool_name == "open_app":
                    confirm_msg = f"Okay sir, opening {params.get('app_name', 'application')}."
                elif tool_name == "open_web":
                    confirm_msg = f"Okay sir, opening {params.get('site_name', 'website')}."
                elif tool_name == "close_app":
                    confirm_msg = f"Okay sir, closing {params.get('app_name', 'application')}."
                elif tool_name == "close_window":
                    confirm_msg = "Okay sir, closing the window."
                elif tool_name == "volume_control":
                    confirm_msg = f"Okay sir, turning volume {params.get('action', 'adjustment')}."
                elif tool_name == "send_whatsapp":
                    confirm_msg = f"Okay sir, sending WhatsApp message to {params.get('contact', 'contact')}."
                elif tool_name == "whatsapp_chat":
                    confirm_msg = f"Okay sir, opening WhatsApp chat with {params.get('contact', 'contact')}."
                elif tool_name == "create_file":
                    confirm_msg = f"Okay sir, creating the file."
                elif tool_name == "create_obsidian_note":
                    confirm_msg = f"Okay sir, creating the Obsidian note: {params.get('title', 'note')}."
                elif tool_name == "mcp_github_search":
                    confirm_msg = f"Okay sir, searching GitHub for {params.get('query', '')}."
                elif tool_name == "mcp_web_search":
                    confirm_msg = f"Okay sir, searching the web for {params.get('query', '')}."
                elif tool_name == "play_music_spotify":
                    confirm_msg = f"Okay sir, playing {params.get('title', 'music')} on Spotify."
                    confirm_msg = f"Okay sir, playing {params.get('query', 'music')} on YouTube."
                elif tool_name == "system_screenshot":
                    confirm_msg = "Okay sir, capturing screen screenshot."
                
                speak_async(confirm_msg)
            
            # Special handling for tools that need conversational response (like weather)
            if tool_name == "get_weather" and isinstance(tool_result, str):
                # Generate conversational response using LLM
                response = self.engine.generate_tool_response(user_input, tool_result)
                speak_async(response)
                
                return {
                    "status": "success",
                    "intent": result.intent,
                    "tool": tool_name,
                    "params": params,
                    "result": tool_result,
                    "response": response
                }
            
            # Google Workspace tools â€” speak + show in popup UI
            elif tool_name in ["gmail_check_unread", "gmail_summarize", "gmail_search"]:
                import json
                data = json.loads(tool_result)
                response = self._format_gmail_response(tool_name, data, user_input)
                speak_async(response)
                
                # Show detailed results in popup (like GitHub results)
                popup_text = self._format_gmail_popup(tool_name, data)
                if popup_text:
                    title_map = {
                        "gmail_check_unread": "ðŸ“§ Unread Emails",
                        "gmail_summarize": "ðŸ“§ Inbox Summary",
                        "gmail_search": "ðŸ“§ Email Search Results"
                    }
                    show_results_in_popup(title_map.get(tool_name, "Email"), popup_text)
                
                return {
                    "status": "success",
                    "intent": result.intent,
                    "tool": tool_name,
                    "data": data,
                    "response": response
                }
            
            elif tool_name == "calendar_today":
                import json
                data = json.loads(tool_result)
                response = self._format_calendar_response(data)
                speak_async(response)
                
                # Show calendar in popup
                popup_text = self._format_calendar_popup(data)
                if popup_text:
                    show_results_in_popup("ðŸ“… Today's Schedule", popup_text)
                
                return {
                    "status": "success",
                    "intent": result.intent,
                    "tool": tool_name,
                    "data": data,
                    "response": response
                }
            
            elif tool_name == "calendar_create_event":
                import json
                data = json.loads(tool_result) if isinstance(tool_result, str) else tool_result
                title = params.get("title", "your event")
                response = f"Done! I've added '{title}' to your calendar."
                speak_async(response)
                
                return {
                    "status": "success",
                    "intent": result.intent,
                    "tool": tool_name,
                    "data": data,
                    "response": response
                }
            
            elif tool_name == "drive_list":
                import json
                data = json.loads(tool_result)
                response = self._format_drive_response(data)
                speak_async(response)
                
                return {
                    "status": "success",
                    "intent": result.intent,
                    "tool": tool_name,
                    "data": data,
                    "response": response
                }
            
            # MCP Tools - Display results in expandable popup
            elif tool_name in ["mcp_github_search", "mcp_web_search", "mcp_image_search"]:
                # Show results in the expandable panel
                title_map = {
                    "mcp_github_search": "GitHub Results",
                    "mcp_web_search": "Web Search Results",
                    "mcp_image_search": "Image Search"
                }
                title = title_map.get(tool_name, "Search Results")
                
                # Display in expandable popup
                if isinstance(tool_result, str) and len(tool_result) > 10:
                    show_results_in_popup(title, tool_result)
                    print(f"[Router] Displaying {title} in popup")
                
                return {
                    "status": "success",
                    "intent": result.intent,
                    "tool": tool_name,
                    "params": params,
                    "result": tool_result,
                    "response": tool_result,  # For chained task output extraction
                }

            
            return {
                "status": "success",
                "intent": result.intent,
                "tool": tool_name,
                "params": params,
                "result": tool_result
            }
            
        except ValueError as e:
            error_msg = str(e)
            _safe_print(f"[Router] Tool error: {error_msg}")
            
            # Speak the error
            speak_async(f"Sorry, I couldn't complete that action. {error_msg}")
            
            return {
                "status": "error",
                "intent": result.intent,
                "tool": tool_name,
                "error": error_msg
            }
        except Exception as e:
            error_msg = str(e)
            _safe_print(f"[Router] Unexpected error: {error_msg}")
            
            speak_async("Sorry, something went wrong while executing that action.")
            
            return {
                "status": "error",
                "intent": result.intent,
                "tool": tool_name,
                "error": error_msg
            }
    
    def _route_to_agent(self, agent_type: str, user_input: str, result: IntentResult) -> Dict[str, Any]:
        """
        Route request to the appropriate agent.
        Each agent has its own LLM config and memory access.
        """
        try:
            if agent_type == "whatsapp":
                from Agents.WhatsApp_Agent.agent import get_whatsapp_agent
                agent = get_whatsapp_agent()
            elif agent_type == "browser":
                from Agents.Browser_Agent.agent import get_browser_agent
                agent = get_browser_agent()
            elif agent_type == "rag":
                from Agents.RAG_Agent.agent import get_rag_agent
                agent = get_rag_agent()
            else:
                return {"status": "error", "intent": result.intent, "error": f"Unknown agent: {agent_type}"}

            print(f"[Router] [{agent.AGENT_NAME}] Processing request...")
            
            # Pass pre-parsed params from IntentEngine so agents don't have to
            # re-parse (avoids pronoun resolution failures like "him" vs "CONTACT_NAME_TWO")
            pre_parsed = result.params if result.params else {}
            agent_result = agent.process(user_input, pre_parsed=pre_parsed)

            response = agent_result.get("response", "Done.")
            success = agent_result.get("success", False)

            # Speak the response
            speak_async(response)

            return {
                "status": "success" if success else "error",
                "intent": result.intent,
                "agent": agent.AGENT_NAME,
                "response": response,
                "data": agent_result.get("data"),
            }

        except Exception as e:
            safe_err = str(e).encode('ascii', errors='replace').decode()
            print(f"[Router] Agent error: {safe_err}")
            speak_async("Sorry, the agent encountered an error.")
            return {"status": "error", "intent": result.intent, "error": safe_err}

    def _handle_query(self, result: IntentResult, user_input: str = "") -> Dict[str, Any]:
        """Handle a query that needs an answer."""
        # Check if LLM already provided a response
        if result.response:
            response = result.response
        else:
            # Generate answer using LLM - use original user input as fallback
            query = result.params.get("query", "") or user_input
            response = self.engine.generate_answer(query)
        
        _safe_print(f"[Router] Query response: {response[:100]}...")
        
        # Speak the response asynchronously
        speak_async(response)
        
        # Display in expandable popup for longer responses
        if len(response) > 100:
            query = result.params.get("query", "Answer")
            show_results_in_popup(f"Answer: {query[:30]}...", response)
        
        return {
            "status": "success",
            "intent": result.intent,
            "response": response
        }
    
    def _handle_unknown(self, result: IntentResult) -> Dict[str, Any]:
        """Handle unknown or low-confidence intents."""
        response = result.response or "I'm not sure what you'd like me to do. Could you please be more specific?"
        
        _safe_print(f"[Router] Unknown intent, responding: {response}")
        
        return {
            "status": "clarification_needed",
            "intent": result.intent,
            "confidence": result.confidence,
            "response": response
        }
    
    def _handle_clarification(self, result: IntentResult, original_input: str) -> Dict[str, Any]:
        """Generate and speak a clarification question."""
        clarification = self.engine.generate_clarification(original_input)
        
        _safe_print(f"[Router] Asking clarification: {clarification}")
        
        return {
            "status": "clarification_needed",
            "intent": "UNKNOWN",
            "confidence": result.confidence,
            "response": clarification
        }
    
    def _format_gmail_response(self, tool_name: str, data: Dict, user_input: str) -> str:
        """Format Gmail data into conversational response"""
        if tool_name == "gmail_check_unread":
            count = data.get("count", 0)
            total = data.get("totalUnread", 0)
            
            if count == 0:
                return "You have no unread emails. Your inbox is clear!"
            
            emails = data.get("emails", [])
            if count == 1:
                email = emails[0]
                return f"You have 1 unread email from {email['from'].split('<')[0].strip()}, subject: {email['subject']}"
            else:
                response = f"You have {total} unread emails. "
                if count >= 3:
                    response += f"Your most recent ones are from {emails[0]['from'].split('<')[0].strip()}, {emails[1]['from'].split('<')[0].strip()}, and {emails[2]['from'].split('<')[0].strip()}."
                else:
                    senders = [e['from'].split('<')[0].strip() for e in emails]
                    response += f"They're from {', '.join(senders)}."
                return response
        
        elif tool_name == "gmail_summarize":
            # New format: local LLM summary + email data
            summary = data.get("summary", "")
            if summary:
                return summary
            
            # Fallback if no summary field
            total = data.get("totalUnread", 0)
            if total == 0:
                return "Your inbox is clean! No unread emails."
            return f"You have {total} unread emails."
        
        elif tool_name == "gmail_search":
            count = data.get("count", 0)
            query = data.get("query", "that")
            
            if count == 0:
                return f"I didn't find any emails matching {query}."
            
            emails = data.get("emails", [])
            if count == 1:
                return f"I found 1 email: {emails[0]['subject']}"
            else:
                return f"I found {count} emails about that. The most recent is: {emails[0]['subject']}"
        
        return "Email check complete."
    
    def _format_calendar_response(self, data: Dict) -> str:
        """Format Calendar data into conversational response"""
        count = data.get("count", 0)
        
        if count == 0:
            return "You have no events today. Your calendar is clear!"
        
        events = data.get("events", [])
        if count == 1:
            event = events[0]
            from datetime import datetime
            start_time = datetime.fromisoformat(event['start'].replace('Z', '+00:00'))
            return f"You have 1 event today: {event['title']} at {start_time.strftime('%I:%M %p')}."
        else:
            response = f"You have {count} events today. "
            event_list = ", ".join([e['title'] for e in events[:3]])
            response += f"They include: {event_list}"
            if count > 3:
                response += f", and {count - 3} more."
            return response
    
    def _format_drive_response(self, data: Dict) -> str:
        """Format Drive data into conversational response"""
        count = data.get("count", 0)
        
        if count == 0:
            return "I didn't find any files in your Drive."
        
        files = data.get("files", [])
        if count == 1:
            return f"I found 1 file: {files[0]['name']}."
        elif count <= 3:
            file_names = [f['name'] for f in files]
            return f"I found {count} files: {', '.join(file_names)}."
        else:
            return f"I found {count} files. The most recent are: {files[0]['name']}, {files[1]['name']}, and {files[2]['name']}."
    
    def _format_gmail_popup(self, tool_name: str, data: Dict) -> str:
        """Format Gmail data for popup UI display (rich text like GitHub results)"""
        emails = data.get("emails", [])
        if not emails:
            return ""
        
        lines = []
        for i, email in enumerate(emails, 1):
            sender = email.get("from", "Unknown").split("<")[0].strip()
            subject = email.get("subject", "(no subject)")
            date = email.get("date", "")[:10]  # Just the date part
            snippet = email.get("snippet", "")[:80]
            
            lines.append(f"{i}. {subject}")
            lines.append(f"   From: {sender}")
            if date:
                lines.append(f"   Date: {date}")
            if snippet:
                lines.append(f"   {snippet}")
            lines.append("")
        
        total = data.get("totalUnread", data.get("count", len(emails)))
        header = f"Showing {len(emails)} of {total} emails\n{'â”€' * 40}\n"
        return header + "\n".join(lines)
    
    def _format_calendar_popup(self, data: Dict) -> str:
        """Format Calendar data for popup UI display"""
        events = data.get("events", [])
        if not events:
            return ""
        
        lines = []
        for i, event in enumerate(events, 1):
            title = event.get("title", "Untitled")
            start = event.get("start", "")
            location = event.get("location", "")
            
            # Format time nicely
            time_str = ""
            if start:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    time_str = dt.strftime('%I:%M %p')
                except:
                    time_str = start[:16]
            
            lines.append(f"{i}. {title}")
            if time_str:
                lines.append(f"   Time: {time_str}")
            if location:
                lines.append(f"   Location: {location}")
            lines.append("")
        
        header = f"{len(events)} event(s) today\n{'â”€' * 40}\n"
        return header + "\n".join(lines)



def speak_async(text: str):
    """Speak text asynchronously to avoid blocking. Also sends to UI."""
    if text:
        # Send to JARVIS UI
        ui_jarvis_message(text)
        # Speak via TTS
        thread = threading.Thread(target=speak, args=(text,), daemon=True)
        thread.start()


# Global router instance
_router: Optional[IntentRouter] = None


def get_router() -> IntentRouter:
    """Get the global intent router instance."""
    global _router
    if _router is None:
        _router = IntentRouter()
    return _router


def process_command(user_input: str) -> Dict[str, Any]:
    """
    Main entry point for processing voice commands.
    
    Args:
        user_input: Transcribed user speech
        
    Returns:
        Dict with processing results
    """
    router = get_router()
    return router.process(user_input)


if __name__ == "__main__":
    # Test the router
    print("\nJARVIS Intent Router Test")
    print("=" * 40)
    
    router = get_router()
    
    if not router.engine.is_available():
        print("[X] Ollama not available!")
        sys.exit(1)
    
    print("[OK] System ready")
    print("\nEnter commands to test (Ctrl+C to exit):\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            
            result = router.process(user_input)
            
            print(f"\nResult:")
            for key, value in result.items():
                print(f"  {key}: {value}")
            print()
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break

