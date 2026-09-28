"""
RAG Agent — Standard Agent Implementation
Wraps document Q&A and knowledge retrieval.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Agents.base_agent import BaseAgent
from Agents.RAG_Agent import config


class RAGAgent(BaseAgent):
    """RAG Agent — handles document Q&A and knowledge retrieval."""

    AGENT_NAME = config.AGENT_NAME

    def _load_config(self):
        self.model = config.MODEL_NAME
        self.system_prompt = config.SYSTEM_PROMPT
        self.ollama_options = config.OLLAMA_OPTIONS.copy()

    def process(self, request: str, **kwargs) -> dict:
        """
        Process a RAG/document request.
        """
        self.log(f"Processing: {request}")

        try:
            from Agents.RAG_Agent.rag_chatbot import query_documents
            result = query_documents(request)
            return {
                "success": True,
                "agent": self.AGENT_NAME,
                "response": result,
            }
        except ImportError:
            return {
                "success": False,
                "agent": self.AGENT_NAME,
                "response": "RAG system not fully configured yet. Please upload documents first.",
            }
        except Exception as e:
            safe_err = str(e).encode('ascii', errors='replace').decode()
            self.log(f"Error: {safe_err}")
            return {
                "success": False,
                "agent": self.AGENT_NAME,
                "response": f"RAG error: {safe_err[:100]}",
            }


_agent = None

def get_rag_agent() -> RAGAgent:
    global _agent
    if _agent is None:
        _agent = RAGAgent()
    return _agent
