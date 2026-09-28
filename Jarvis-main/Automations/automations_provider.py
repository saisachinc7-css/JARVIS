"""
Automations Provider for JARVIS
Central router for all automations — picks the right automation based on the request.

Connected to both Primary and Secondary Brain.
Works like ToolsProvider but for automations.

Usage:
    from Automations.automations_provider import get_automations
    auto = get_automations()
    result = auto.route("let's create a video today")
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AutomationsProvider:
    """
    Central router for all automations.
    Analyzes the request and routes to the correct automation.
    
    Subsystems:
        1. Custom Workflows — multi-app workspace setups
        2. Webhooks (n8n)   — external webhook integrations
        3. Automation Brain — rule-based + LLM processing
    """

    # Keywords that trigger each automation type
    AUTOMATION_KEYWORDS = {
        "workflow": [
            "video", "coding", "research", "workspace",
            "let's create", "let's code", "let's do",
            "set up workspace", "workflow",
        ],
        "webhook": [
            "webhook", "n8n", "trigger", "automation flow",
            "send to n8n", "external automation",
        ],
        "brain": [
            # These fall through to Automation_Brain for rule-based processing
            "open", "close", "play", "search", "type",
        ],
    }

    def route(self, user_input: str) -> dict:
        """
        Route a request to the appropriate automation.
        
        Args:
            user_input: The user's request
            
        Returns:
            Dict with automation type, success status, and result
        """
        auto_type = self._identify_automation(user_input)
        
        if not auto_type:
            return {
                "success": False,
                "type": None,
                "message": "No matching automation found."
            }

        print(f"[AutomationsProvider] Routing to: {auto_type}")
        
        handler = {
            "workflow": self._route_workflow,
            "webhook": self._route_webhook,
            "brain": self._route_brain,
        }.get(auto_type)

        if handler:
            return handler(user_input)
        
        return {"success": False, "type": auto_type, "message": "Handler not found"}

    def _identify_automation(self, user_input: str) -> str:
        """Identify which automation type should handle this."""
        input_lower = user_input.lower()
        
        scores = {}
        for auto_type, keywords in self.AUTOMATION_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in input_lower)
            if score > 0:
                scores[auto_type] = score
        
        if not scores:
            return None
        
        return max(scores, key=scores.get)

    def _route_workflow(self, user_input: str) -> dict:
        """Route to Custom Workflows."""
        try:
            from Automations.Custom.video_workflow import run_workflow, WORKFLOWS
            
            # Match to a specific workflow
            input_lower = user_input.lower()
            for name in WORKFLOWS:
                if name in input_lower:
                    result = run_workflow(name)
                    return {
                        "success": True,
                        "type": "workflow",
                        "workflow": name,
                        "result": result,
                    }
            
            # Default: try the first matching keyword
            if "video" in input_lower:
                result = run_workflow("video")
                return {"success": True, "type": "workflow", "workflow": "video", "result": result}
            elif "cod" in input_lower:
                result = run_workflow("coding")
                return {"success": True, "type": "workflow", "workflow": "coding", "result": result}
            elif "research" in input_lower:
                result = run_workflow("research")
                return {"success": True, "type": "workflow", "workflow": "research", "result": result}
            
            return {
                "success": False,
                "type": "workflow",
                "message": f"No matching workflow. Available: {', '.join(WORKFLOWS.keys())}"
            }
        except Exception as e:
            return {"success": False, "type": "workflow", "error": str(e)}

    def _route_webhook(self, user_input: str) -> dict:
        """Route to n8n Webhooks."""
        try:
            from Automations.Webhooks.n8n_bridge import send_response_to_n8n
            
            result = send_response_to_n8n(
                command=user_input,
                response="Triggered from JARVIS",
                status="pending"
            )
            return {
                "success": True,
                "type": "webhook",
                "result": result,
            }
        except Exception as e:
            return {"success": False, "type": "webhook", "error": str(e)}

    def _route_brain(self, user_input: str) -> dict:
        """Route to Automation Brain (rule-based fallback)."""
        try:
            from Automations.Automation_Brain import process_rule_based
            
            handled = process_rule_based(user_input)
            return {
                "success": handled,
                "type": "brain",
                "message": "Processed by rule-based automation" if handled else "Not handled"
            }
        except Exception as e:
            return {"success": False, "type": "brain", "error": str(e)}

    # ===== DIRECT ACCESS =====
    
    def run_workflow(self, name: str) -> str:
        """Run a named workflow directly."""
        from Automations.Custom.video_workflow import run_workflow
        return run_workflow(name)

    def send_webhook(self, command: str, data: dict = None) -> dict:
        """Send to n8n webhook directly."""
        from Automations.Webhooks.n8n_bridge import N8nBridge
        bridge = N8nBridge()
        return bridge.send_to_n8n("brain_response", {
            "command": command,
            **(data or {})
        })


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================
_automations_provider = None


def get_automations() -> AutomationsProvider:
    """Get the global AutomationsProvider instance."""
    global _automations_provider
    if _automations_provider is None:
        _automations_provider = AutomationsProvider()
    return _automations_provider
