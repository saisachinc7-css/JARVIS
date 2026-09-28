"""
n8n Webhook Bridge for JARVIS
Handles all webhook connections to/from n8n.

Flow:
1. n8n sends webhook request → This bridge receives it
2. Bridge forwards to Brain for processing
3. Brain returns response
4. Bridge sends structured output back to n8n → UI + Voice
"""

import json
import sys
import os
from typing import Optional, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from flask import Flask, request, jsonify
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


# ============================================================================
# CONFIGURATION
# ============================================================================
WEBHOOK_HOST = "localhost"
WEBHOOK_PORT = 5678
N8N_BASE_URL = "http://localhost:5679"  # n8n's default URL

# Webhook endpoints registered in n8n
WEBHOOK_ENDPOINTS = {
    "brain_request": "/webhook/jarvis-brain",
    "brain_response": "/webhook/jarvis-response",
}


class N8nBridge:
    """
    Bridge between JARVIS and n8n webhooks.
    
    Receives requests from n8n, processes through Brain,
    and returns structured responses.
    """

    def __init__(self):
        self.app = None
        if FLASK_AVAILABLE:
            self.app = Flask(__name__)
            self._register_routes()

    def _register_routes(self):
        """Register webhook endpoints."""
        
        @self.app.route("/webhook/jarvis-brain", methods=["POST"])
        def handle_brain_request():
            """Receive a request from n8n and process it."""
            data = request.get_json()
            if not data or "command" not in data:
                return jsonify({"error": "Missing 'command' field"}), 400

            command = data["command"]
            print(f"[n8n Bridge] Received command: {command}")

            try:
                # Process through Automation Brain
                from Automations.Automation_Brain import Automation_Brain
                Automation_Brain(command)
                
                return jsonify({
                    "status": "success",
                    "command": command,
                    "message": "Command processed successfully"
                })
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "command": command,
                    "error": str(e)
                }), 500

        @self.app.route("/health", methods=["GET"])
        def health_check():
            return jsonify({"status": "ok", "service": "jarvis-n8n-bridge"})

    def send_to_n8n(self, endpoint: str, data: Dict[str, Any]) -> Optional[Dict]:
        """
        Send data to an n8n webhook endpoint.
        
        Args:
            endpoint: The webhook endpoint name (from WEBHOOK_ENDPOINTS)
            data: Data to send
            
        Returns:
            Response dict or None if failed
        """
        if not REQUESTS_AVAILABLE:
            print("[n8n Bridge] requests library not available")
            return None

        url = f"{N8N_BASE_URL}{WEBHOOK_ENDPOINTS.get(endpoint, endpoint)}"
        
        try:
            response = requests.post(url, json=data, timeout=30)
            return response.json()
        except Exception as e:
            print(f"[n8n Bridge] Error sending to n8n: {e}")
            return None

    def start(self, host: str = None, port: int = None):
        """Start the webhook server."""
        if not self.app:
            print("[n8n Bridge] Flask not available. Run: pip install flask")
            return
            
        host = host or WEBHOOK_HOST
        port = port or WEBHOOK_PORT
        print(f"[n8n Bridge] Starting webhook server on {host}:{port}")
        self.app.run(host=host, port=port, debug=False, threaded=True)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def start_webhook_server():
    """Start the n8n webhook bridge server."""
    bridge = N8nBridge()
    bridge.start()


def send_response_to_n8n(command: str, response: str, status: str = "success"):
    """Send a response back to n8n."""
    bridge = N8nBridge()
    return bridge.send_to_n8n("brain_response", {
        "command": command,
        "response": response,
        "status": status,
    })
