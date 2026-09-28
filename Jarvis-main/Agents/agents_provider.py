"""
Agents Provider for JARVIS
Central router for all agents â€” picks the right agent based on the request.

Connected to both Primary and Secondary Brain.
Works like ToolsProvider but for agents.

Usage:
    from Agents.agents_provider import get_agents
    agents = get_agents()
    result = agents.route("send hi to CONTACT_NAME_THREE on whatsapp")
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AgentsProvider:
    """
    Central router for all agents.
    Analyzes the request and routes to the correct agent.
    
    Agents:
        1. WhatsApp Agent  â€” messaging, chat, reply
        2. Browser Agent   â€” web navigation, page interaction
        3. RAG Agent       â€” PDF Q&A, document search
    """

    # Keywords that trigger each agent
    AGENT_KEYWORDS = {
        "whatsapp": [
            "whatsapp", "message", "send to", "text to", "reply to",
            "chat with", "wa ", "draft message", "contact",
        ],
        "browser": [
            "browse", "navigate to", "go to url", "click on",
            "fill form", "take screenshot", "inspect page",
            "browser tab", "playwright",
        ],
        "doc_intel": [
            "open ", "find ", "read pdf", "open the", "find the", "open my",
            "from desktop", "from downloads", "from documents", "scroll down",
            "scroll up", "zoom in", "zoom out", "close document", "go to page",
            "find all mentions", "search for", "what is this document about",
            "explain page", "document intelligence",
        ],
        "study": [
            "study", "read this pdf", "summarize this document", "explain this chapter",
            "generate important questions", "create a quiz", "ask me questions one by one",
            "explain this like i'm a beginner", "explain in simple language",
            "important formulas", "extract key points", "find important definitions",
            "important topics", "ask doubts", "only this document", "compare two uploaded documents",
            "translate this document", "revision notes", "flashcards", "interview questions",
            "multiple-choice questions", "continue from the last page", "study mode",
        ],
    }

    def route(self, user_input: str) -> dict:
        """
        Route a request to the appropriate agent.
        
        Args:
            user_input: The user's request
            
        Returns:
            Dict with agent name, success status, and result
        """
        agent = self._identify_agent(user_input)
        
        if not agent:
            return {
                "success": False,
                "agent": None,
                "message": "No matching agent found for this request."
            }

        print(f"[AgentsProvider] Routing to: {agent}")
        
        handler = {
            "whatsapp": self._route_whatsapp,
            "browser": self._route_browser,
            "rag": self._route_rag,
            "study": self._route_study,
            "doc_intel": self._route_doc_intel,
        }.get(agent)


        if handler:
            return handler(user_input)
        
        return {"success": False, "agent": agent, "message": "Agent handler not found"}

    def _identify_agent(self, user_input: str) -> str:
        """Identify which agent should handle this request."""
        input_lower = user_input.lower()
        
        scores = {}
        for agent, keywords in self.AGENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in input_lower)
            if score > 0:
                scores[agent] = score
        
        if not scores:
            return None
        
        return max(scores, key=scores.get)

    def _route_whatsapp(self, user_input: str) -> dict:
        """Route to WhatsApp Agent (standardized)."""
        try:
            from Agents.WhatsApp_Agent.agent import get_whatsapp_agent
            agent = get_whatsapp_agent()
            return agent.process(user_input)
        except Exception as e:
            return {"success": False, "agent": "WhatsApp Agent", "error": str(e)}

    def _route_browser(self, user_input: str) -> dict:
        """Route to Browser Agent (standardized)."""
        try:
            from Agents.Browser_Agent.agent import get_browser_agent
            agent = get_browser_agent()
            return agent.process(user_input)
        except Exception as e:
            return {"success": False, "agent": "Browser Agent", "error": str(e)}

    def _route_rag(self, user_input: str) -> dict:
        """Route to RAG Agent (standardized)."""
        try:
            from Agents.RAG_Agent.agent import get_rag_agent
            agent = get_rag_agent()
            return agent.process(user_input)
        except Exception as e:
            return {"success": False, "agent": "RAG Agent", "error": str(e)}

    def _route_study(self, user_input: str) -> dict:
        """Route to Study Agent."""
        try:
            from Agents.Study_Agent.agent import get_study_agent
            agent = get_study_agent()
            return agent.process(user_input)
        except Exception as e:
            return {"success": False, "agent": "Study Agent", "error": str(e)}

    def _route_doc_intel(self, user_input: str) -> dict:
        """Route to Document Intelligence Agent."""
        try:
            from Agents.Document_Intelligence.agent import get_doc_intelligence_agent
            agent = get_doc_intelligence_agent()
            return agent.process(user_input)
        except Exception as e:
            return {"success": False, "agent": "Document Intelligence Agent", "error": str(e)}

    # ===== DIRECT ACCESS =====
    
    @property
    def whatsapp(self):
        """Direct access to WhatsApp agent handler."""
        from Agents.WhatsApp_Agent.whatsapp_skill import handle_whatsapp_command
        return handle_whatsapp_command

    @property
    def browser(self):
        """Direct access to Browser agent config/handler."""
        from Agents.Browser_Agent import config as browser_config
        return browser_config

    @property
    def rag(self):
        """Direct access to RAG agent config."""
        from Agents.RAG_Agent import config as rag_config
        return rag_config

    @property
    def study(self):
        """Direct access to Study agent config."""
        from Agents.Study_Agent import config as study_config
        return study_config

    @property
    def doc_intel(self):
        """Direct access to Document Intelligence agent config."""
        from Agents.Document_Intelligence import config as doc_config
        return doc_config



# ============================================================================
# GLOBAL INSTANCE
# ============================================================================
_agents_provider = None


def get_agents() -> AgentsProvider:
    """Get the global AgentsProvider instance."""
    global _agents_provider
    if _agents_provider is None:
        _agents_provider = AgentsProvider()
    return _agents_provider

