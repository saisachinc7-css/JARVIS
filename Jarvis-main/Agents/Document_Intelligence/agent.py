"""
Document Intelligence Agent for JARVIS 2.0
Standard Agent implementation connecting Document Finder, Controller, and Study Engine.
"""

import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Agents.base_agent import BaseAgent
from Agents.Document_Intelligence import config
from Agents.Document_Intelligence.intelligence_engine import (
    get_doc_state,
    open_and_ingest_document,
    resolve_disambiguation_selection,
    search_text_in_active_document,
    handle_viewer_control,
)
from Agents.Study_Agent.agent import get_study_agent
from Agents.Study_Agent.study_engine import get_study_session


class DocumentIntelligenceAgent(BaseAgent):
    """
    JARVIS Document Intelligence Agent.
    Finds, opens, controls, searches, and explains desktop documents.
    """

    AGENT_NAME = config.AGENT_NAME

    def _load_config(self):
        self.model = config.MODEL_NAME
        self.system_prompt = config.SYSTEM_PROMPT

    def process(self, request: str, **kwargs) -> dict:
        """
        Process a document intelligence request.
        """
        self.log(f"Processing Document Request: {request}")
        req_lower = request.lower().strip()
        state = get_doc_state()
        session = get_study_session()
        active_doc = session.active_document

        # 0. Exclude Web & App Search Queries ("search for ai in google", "search google", "search youtube", etc.)
        is_web_query = any(w in req_lower for w in ["google", "youtube", "github", "obsidian", "web", "online", "internet", "website", "chrome", "browser", "wikipedia"])
        if any(ext in req_lower for ext in [".pdf", ".docx", ".doc", ".pptx", ".ppt", ".txt", ".md", ".rtf", ".html", ".htm"]) or "pdf" in req_lower or "document" in req_lower:
            if not any(w in req_lower for w in ["google", "youtube", "github"]):
                is_web_query = False
                
        if is_web_query:
            return {
                "success": False,
                "agent": self.AGENT_NAME,
                "response": "Sir, this request is a web search. Delegating to web search engine."
            }

        # Check for active document action commands (close, rename, move, delete)
        is_active_action = any(w in req_lower for w in ["close", "rename", "move", "delete"])
        if is_active_action:
            if not active_doc:
                return {
                    "success": True,
                    "agent": self.AGENT_NAME,
                    "response": "I don't currently have an active document. Please open a document first."
                }
            
            # Close
            if any(w in req_lower for w in ["close this document", "close the document", "close document", "close file", "close it"]):
                from Tools.document_controller import close_document_viewer
                close_document_viewer()
                session.active_document = None
                session.active_doc_id = None
                session.loaded_materials = {}
                return {
                    "success": True,
                    "agent": self.AGENT_NAME,
                    "response": "Sir, I have closed the active document viewer and cleared it from session memory."
                }
                
            # Rename
            if any(w in req_lower for w in ["rename this document", "rename the document", "rename document", "rename file", "rename it"]):
                new_name = None
                for marker in [" to ", " as "]:
                    if marker in req_lower:
                        new_name = request.split(marker)[-1].strip().strip('"').strip("'")
                        break
                if not new_name:
                    return {
                        "success": True,
                        "agent": self.AGENT_NAME,
                        "response": "Sir, please specify what you would like to rename the active document to (e.g. 'rename this document to new_name.pdf')."
                    }
                old_path = active_doc["file_path"]
                dir_name = os.path.dirname(old_path)
                old_ext = os.path.splitext(old_path)[1]
                if not os.path.splitext(new_name)[1] and old_ext:
                    new_name += old_ext
                new_path = os.path.join(dir_name, new_name)
                try:
                    os.rename(old_path, new_path)
                    active_doc["file_name"] = new_name
                    active_doc["title"] = new_name
                    active_doc["file_path"] = os.path.abspath(new_path)
                    session.loaded_materials.clear()
                    session.add_material(active_doc)
                    return {
                        "success": True,
                        "agent": self.AGENT_NAME,
                        "response": f"Sir, I have renamed the active document to `{new_name}` and updated session memory."
                    }
                except Exception as e:
                    return {
                        "success": True,
                        "agent": self.AGENT_NAME,
                        "response": f"Sir, I encountered an error renaming the file: {e}"
                    }

            # Move
            if any(w in req_lower for w in ["move this document", "move the document", "move document", "move file", "move it"]):
                dest = None
                for marker in [" to "]:
                    if marker in req_lower:
                        dest = request.split(marker)[-1].strip().strip('"').strip("'")
                        break
                if not dest:
                    return {
                        "success": True,
                        "agent": self.AGENT_NAME,
                        "response": "Sir, please specify the destination path to move the document to (e.g. 'move this document to Desktop')."
                    }
                dest_lower = dest.lower()
                if dest_lower == "desktop":
                    dest = os.path.join(os.path.expanduser("~"), "Desktop")
                elif dest_lower == "documents":
                    dest = os.path.join(os.path.expanduser("~"), "Documents")
                elif dest_lower == "downloads":
                    dest = os.path.join(os.path.expanduser("~"), "Downloads")
                old_path = active_doc["file_path"]
                file_name = active_doc["file_name"]
                if os.path.isdir(dest):
                    new_path = os.path.join(dest, file_name)
                else:
                    new_path = dest
                try:
                    import shutil
                    os.makedirs(os.path.dirname(new_path), exist_ok=True)
                    shutil.move(old_path, new_path)
                    active_doc["file_path"] = os.path.abspath(new_path)
                    active_doc["file_name"] = os.path.basename(new_path)
                    active_doc["title"] = os.path.basename(new_path)
                    session.loaded_materials.clear()
                    session.add_material(active_doc)
                    return {
                        "success": True,
                        "agent": self.AGENT_NAME,
                        "response": f"Sir, I have successfully moved the active document to `{new_path}` and updated session memory."
                    }
                except Exception as e:
                    return {
                        "success": True,
                        "agent": self.AGENT_NAME,
                        "response": f"Sir, I encountered an error moving the file: {e}"
                    }

            # Delete
            if any(w in req_lower for w in ["delete this document", "delete the document", "delete document", "delete file", "delete it"]):
                old_path = active_doc["file_path"]
                from Tools.document_controller import close_document_viewer
                close_document_viewer()
                try:
                    if old_path:
                        try:
                            os.remove(old_path)
                        except FileNotFoundError:
                            pass
                    session.active_document = None
                    session.active_doc_id = None
                    session.loaded_materials = {}
                    return {
                        "success": True,
                        "agent": self.AGENT_NAME,
                        "response": f"Sir, I have deleted the file `{old_path}` from disk and cleared active document memory."
                    }
                except Exception as e:
                    return {
                        "success": True,
                        "agent": self.AGENT_NAME,
                        "response": f"Sir, I encountered an error deleting the file: {e}"
                    }

        # 1. Disambiguation resolution (if user was previously prompted to pick candidate 1, 2, 3...)
        if state.pending_candidates:
            resp = resolve_disambiguation_selection(request)
            if resp:
                return {"success": True, "agent": self.AGENT_NAME, "response": resp}

        # 2. Viewer control commands (scroll, zoom, close, jump to page)
        viewer_resp = handle_viewer_control(request)
        if viewer_resp:
            return {"success": True, "agent": self.AGENT_NAME, "response": viewer_resp}

        # 3. Explicit document search / opening commands ("open ultron.pdf", "find AI notes", "open my resume")
        open_signals = [
            "open ", "find ", "read ", "locate ", "load ", "show me ", "open the ", "find the ", "open my "
        ]
        is_open_cmd = any(req_lower.startswith(sig) for sig in open_signals) or any(ext in req_lower for ext in [".pdf", ".docx", ".pptx", ".txt", ".md"])
        
        # Exclude questions like "what is this document about" from triggering file search
        if is_open_cmd and not any(w in req_lower for w in ["what is this document about", "what does this document say"]):
            target_query = request
            for sig in ["open ", "find ", "read ", "locate ", "load ", "show me "]:
                if target_query.lower().startswith(sig):
                    target_query = target_query[len(sig):].strip()
            
            # Resolve against active document name first (Never search if already the Active Document)
            is_ref_active = False
            if active_doc:
                if any(w == target_query.lower() for w in ["this document", "this file", "the document", "the file", "active document", "active file", "it", "this"]):
                    is_ref_active = True
                elif target_query.lower() in active_doc["file_name"].lower() or os.path.splitext(target_query.lower())[0] in active_doc["file_name"].lower():
                    is_ref_active = True
            
            if is_ref_active:
                if active_doc:
                    from Tools.document_controller import open_document
                    open_document(active_doc["file_path"])
                    return {
                        "success": True,
                        "agent": self.AGENT_NAME,
                        "response": f"📖 **Opened `{active_doc['file_name']}`!**\n\n• **Location**: `{active_doc['file_path']}`\nSir, this is the active document. I have loaded it directly from session memory."
                    }
                else:
                    return {
                        "success": True,
                        "agent": self.AGENT_NAME,
                        "response": "I don't currently have an active document. Please open a document first."
                    }
            elif any(w == target_query.lower() for w in ["this document", "this file", "the document", "the file", "active document", "active file", "it", "this"]) and not active_doc:
                return {
                    "success": True,
                    "agent": self.AGENT_NAME,
                    "response": "I don't currently have an active document. Please open a document first."
                }
            
            resp = open_and_ingest_document(target_query)
            return {"success": True, "agent": self.AGENT_NAME, "response": resp}

        # 4. In-document text search ("find all mentions of X", "search for neural networks")
        search_term = None
        search_patterns = [
            r'(?:occurrences|mentions)\s+of\s+[\'"]?([a-zA-Z0-9_\-\s]{2,})[\'"]?',
            r'where\s+is\s+[\'"]?([a-zA-Z0-9_\-\s]{2,})[\'"]?\s+(?:mentioned|located|found)',
            r'(?:find|search|locate)\s+(?:the\s+)?(?:document|pdf|file|notes)?\s*(?:for|keyword|word)?\s*[\'"]?([a-zA-Z0-9_\-\s]{2,})[\'"]?\s*(?:in\s+.*)?$',
            r'(?:find|search|locate)\s+[\'"]?([a-zA-Z0-9_\-\s]{2,})[\'"]?\s+(?:in|inside)\s+(?:the|this)?\s*(?:document|pdf|file|notes)'
        ]
        
        for pat in search_patterns:
            m = re.search(pat, req_lower)
            if m:
                search_term = m.group(1).strip()
                break

        # Suffix cleaning
        if search_term:
            search_term = re.sub(r'\s+(?:in|inside)\s+(?:this|the|active)?\s*(?:document|pdf|file|notes|page|table|chapter|roadmap)\b.*', '', search_term, flags=re.IGNORECASE)
            search_term = re.sub(r'\s+in\s+[a-zA-Z0-9_\-\.]+\.(?:pdf|docx|txt|md|rtf|html|htm)\b.*', '', search_term, flags=re.IGNORECASE)
            search_term = search_term.strip('\'"?.!, ')

        if search_term:
            resp = search_text_in_active_document(search_term)
            return {"success": True, "agent": self.AGENT_NAME, "response": resp}

        # 5. Document Page specific explanation ("explain page 12", "explain page 5")
        page_exp_match = re.search(r'explain\s+page\s+(\d+)', req_lower)
        if page_exp_match:
            page_num = int(page_exp_match.group(1))
            session = get_study_session()
            session.current_page = page_num
            from Agents.Study_Agent.study_engine import track_reading_progress
            resp = track_reading_progress(page_num)
            return {"success": True, "agent": self.AGENT_NAME, "response": resp}

        # 6. General follow-up study commands ("summarize it", "create a quiz", "explain chapter 3", "what is this document about")
        study_agent = get_study_agent()
        result = study_agent.process(request)

        return {
            "success": result.get("success", True),
            "agent": self.AGENT_NAME,
            "response": result.get("response", "Sir, I have processed your request on the active document.")
        }


_agent = None


def get_doc_intelligence_agent() -> DocumentIntelligenceAgent:
    global _agent
    if _agent is None:
        _agent = DocumentIntelligenceAgent()
    return _agent
