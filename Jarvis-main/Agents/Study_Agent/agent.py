"""
Study Agent — Standard Agent Implementation for JARVIS 2.0
Handles intelligent study mode, document ingestion, quiz generation, Q&A, and tutoring.
"""

import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Agents.base_agent import BaseAgent
from Agents.Study_Agent import config
from Agents.Study_Agent.study_engine import (
    get_study_session,
    load_study_material,
    summarize_material,
    explain_concept,
    extract_formulas,
    extract_key_points,
    find_important_definitions,
    get_important_topics,
    generate_flashcards,
    generate_revision_notes,
    generate_questions,
    start_interactive_quiz,
    handle_quiz_answer,
    compare_documents,
    answer_document_query,
    track_reading_progress,
    translate_document,
    generate_study_roadmap,
    explain_visuals,
)


class StudyAgent(BaseAgent):
    """
    JARVIS Study Agent — Autonomous AI Professor and Study Engine.
    """

    AGENT_NAME = config.AGENT_NAME

    def _load_config(self):
        self.model = config.MODEL_NAME
        self.system_prompt = config.SYSTEM_PROMPT
        self.ollama_options = config.OLLAMA_OPTIONS.copy()

    def process(self, request: str, **kwargs) -> dict:
        """
        Process a study mode request.
        """
        self.log(f"Processing Study Request: {request}")
        req_lower = request.lower().strip()
        session = get_study_session()

        # Check if loading a new document or url
        file_match = re.search(r'(?:read|load|study|open|parse|ingest)\s+(?:this\s+)?(?:pdf|document|file|notes|url|page|material|article)?\s*:?\s*([^\s,]+\.[a-zA-Z0-9]+|https?://[^\s]+)', request, re.IGNORECASE)
        has_file_kw = file_match or any(k in req_lower for k in ["read this pdf", "load document", "load pdf", "read document", "study material"])
        
        if not session.active_document and not has_file_kw and not session.quiz_state.get("active"):
            return {
                "success": True,
                "agent": self.AGENT_NAME,
                "response": "I don't currently have an active document. Please open a document first."
            }

        # 1. Check if user is responding to an active interactive quiz
        if session.quiz_state.get("active"):
            # Check if answer input like A, B, C, D or single option
            quiz_resp = handle_quiz_answer(request)
            if quiz_resp:
                return {
                    "success": True,
                    "agent": self.AGENT_NAME,
                    "response": quiz_resp
                }

        # 2. File / Material Ingestion detection ("read this pdf", "load file.pdf", "read http...")
        if has_file_kw:
            target = file_match.group(1) if file_match else ""
            if not target:
                # search for path in full string
                paths = [w for w in request.split() if "." in w or "http" in w or "/" in w or "\\" in w]
                target = paths[0] if paths else request

            resp = load_study_material(target)
            return {"success": True, "agent": self.AGENT_NAME, "response": resp}

        # 3. Summarize document / chapter
        if any(k in req_lower for k in ["summarize", "summary", "overview of document", "give me a summary"]):
            chapter = None
            ch_match = re.search(r'chapter\s+(\d+|[a-zA-Z]+)', req_lower)
            if ch_match:
                chapter = ch_match.group(0)
            resp = summarize_material(chapter)
            return {"success": True, "agent": self.AGENT_NAME, "response": resp}

        # 4. Interactive Quiz / Ask me questions one by one
        if any(k in req_lower for k in ["ask me questions one by one", "create a quiz", "interactive quiz", "start quiz", "test me", "quiz me", "quiz"]):
            num_match = re.search(r'(\d+)\s+questions?', req_lower)
            num_q = int(num_match.group(1)) if num_match else 5
            resp = start_interactive_quiz(num_q)
            return {"success": True, "agent": self.AGENT_NAME, "response": resp}

        # 5. Question Generation (MCQ, Interview, Important Qs)
        if any(k in req_lower for k in ["generate important questions", "create multiple-choice", "mcq", "interview questions", "create questions", "test"]):
            q_type = "all"
            num_q = None
            # Extract number of questions if present (e.g., "generate 20 mcqs", "create 30 multiple choice questions")
            num_match = re.search(r'(\d+)\s*(?:mcq|multiple|question|interview|short|long)', req_lower)
            if num_match:
                num_q = int(num_match.group(1))

            if "mcq" in req_lower or "multiple-choice" in req_lower or "multiple choice" in req_lower:
                q_type = "mcq"
            elif "short" in req_lower:
                q_type = "short"
            elif "long" in req_lower:
                q_type = "long"
            elif "interview" in req_lower:
                q_type = "interview"
            resp = generate_questions(q_type, num_questions=num_q)
            return {"success": True, "agent": self.AGENT_NAME, "response": resp}

        # 6. Explanation styles (Beginner / ELI5, Simple, Technical, Exam, Intermediate, Expert)
        if any(k in req_lower for k in ["explain this like i'm a beginner", "explain in simple language", "explain technically", "explain for exam", "explain this chapter", "explain concept", "intermediate", "expert", "advanced"]):
            style = "detailed"
            if "beginner" in req_lower or "eli5" in req_lower:
                style = "beginner"
            elif "simple" in req_lower:
                style = "simple"
            elif "technical" in req_lower or "rigorous" in req_lower:
                style = "technical"
            elif "exam" in req_lower:
                style = "exam"
            elif "intermediate" in req_lower:
                style = "intermediate"
            elif "expert" in req_lower or "advanced" in req_lower:
                style = "expert"

            concept = request
            # strip command words
            for w in ["explain this like i'm a beginner", "explain in simple language", "explain technically", "explain for exam", "explain this chapter", "explain"]:
                concept = concept.lower().replace(w, "").strip()
            concept = concept or "the main topic"

            resp = explain_concept(concept, style)
            return {"success": True, "agent": self.AGENT_NAME, "response": resp}

        # 7. Formulas & Equations
        if any(k in req_lower for k in ["important formulas", "formulas", "equations", "give me formulas"]):
            resp = extract_formulas()
            return {"success": True, "agent": self.AGENT_NAME, "response": resp}

        # 8. Key points & Important Notes
        if any(k in req_lower for k in ["key points", "extract key points", "main takeaways", "important notes", "read notes", "read out the notes", "read out important notes", "read out key points", "notes"]):
            resp = extract_key_points()
            return {"success": True, "agent": self.AGENT_NAME, "response": resp}


        # 9. Definitions & Glossaries
        if any(k in req_lower for k in ["important definitions", "definitions", "glossary", "terms"]):
            resp = find_important_definitions()
            return {"success": True, "agent": self.AGENT_NAME, "response": resp}

        # 10. Important topics
        if any(k in req_lower for k in ["important topics", "most important topics", "high yield topics"]):
            resp = get_important_topics()
            return {"success": True, "agent": self.AGENT_NAME, "response": resp}

        # 11. Flashcards & Revision Notes
        if any(k in req_lower for k in ["flashcards", "generate flashcards", "revision notes", "create revision notes"]):
            if "flashcard" in req_lower:
                resp = generate_flashcards()
            else:
                resp = generate_revision_notes()
            return {"success": True, "agent": self.AGENT_NAME, "response": resp}

        # 12. Compare documents
        if any(k in req_lower for k in ["compare", "difference between documents", "compare uploaded documents"]):
            resp = compare_documents()
            return {"success": True, "agent": self.AGENT_NAME, "response": resp}

        # 13. Reading progress tracking ("continue from last page", "go to page X")
        if any(k in req_lower for k in ["continue from the last page", "continue reading", "next page", "page "]):
            page_num = None
            p_match = re.search(r'page\s+(\d+)', req_lower)
            if p_match:
                page_num = int(p_match.group(1))
            resp = track_reading_progress(page_num)
            return {"success": True, "agent": self.AGENT_NAME, "response": resp}

        # 14. Study Roadmap
        if any(k in req_lower for k in ["roadmap", "study roadmap", "learning path", "plan"]):
            resp = generate_study_roadmap()
            return {"success": True, "agent": self.AGENT_NAME, "response": resp}

        # 15. Translation
        if "translate" in req_lower:
            lang_match = re.search(r'(?:to|into)\s+([a-zA-Z]+)', req_lower)
            target_lang = lang_match.group(1) if lang_match else "English"
            resp = translate_document(target_lang)
            return {"success": True, "agent": self.AGENT_NAME, "response": resp}

        # 16. Visuals / Tables / Diagrams
        if any(k in req_lower for k in ["table", "diagram", "chart", "visual", "figure"]):
            resp = explain_visuals()
            return {"success": True, "agent": self.AGENT_NAME, "response": resp}

        # 17. Strict Document Q&A / Answer doubts ("using only this document")
        strict = any(k in req_lower for k in ["only this document", "strictly from document", "without hallucinating", "no outside info"])
        resp = answer_document_query(request, strict=strict)
        return {
            "success": True,
            "agent": self.AGENT_NAME,
            "response": resp
        }


_agent = None


def get_study_agent() -> StudyAgent:
    global _agent
    if _agent is None:
        _agent = StudyAgent()
    return _agent
