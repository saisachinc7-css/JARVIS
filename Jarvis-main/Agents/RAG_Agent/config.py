"""
RAG Agent Configuration
Custom LLM settings for document Q&A and knowledge retrieval.
"""

# ============================================================================
# AGENT INFO
# ============================================================================
AGENT_NAME = "RAG Agent"

# ============================================================================
# LLM CONFIGURATION
# ============================================================================
MODEL_NAME = "qwen3:4b"

OLLAMA_OPTIONS = {
    "temperature": 0.15,
    "top_p": 0.85,
    "repeat_penalty": 1.15,
    "repeat_last_n": 128,
    "num_ctx": 4096,
    "num_batch": 256,
    "seed": 42,
    "num_predict": 1500,
}

# ============================================================================
# SYSTEM PROMPT
# ============================================================================
SYSTEM_PROMPT = """You are the RAG Agent for JARVIS, a personal voice assistant.

Your ONLY job is to answer questions based on uploaded documents and PDFs.

RESPONSIBILITIES:
- Process and index PDF documents
- Answer questions about document content
- Summarize documents
- Find specific information in the knowledge base

RULES:
- Only answer from the document content you have
- If the answer is not in the documents, say so
- Provide page numbers or references when possible
- Keep answers concise and relevant

OUTPUT: Return the answer with relevant context.
/nothink"""
