"""
Document Intelligence Engine for JARVIS 2.0
Handles document location resolution, multi-file disambiguation state,
in-document keyword search, viewer control execution, and StudyEngine handoff.
"""

import os
import re
from typing import Dict, List, Any, Optional

from Agents.Study_Agent.study_engine import get_study_session, load_study_material
from Agents.Study_Agent.document_parser import parse_file
from Tools.document_finder import resolve_document_location, find_documents
from Tools.document_controller import (
    open_document,
    scroll_document,
    zoom_document,
    goto_page_in_viewer,
    close_document_viewer
)


class DocumentIntelligenceState:
    """Manages active disambiguation state and document status."""

    def __init__(self):
        self.pending_candidates: List[Dict[str, Any]] = []
        self.last_query: str = ""

    def clear_disambiguation(self):
        self.pending_candidates = []
        self.last_query = ""


_state = DocumentIntelligenceState()


def get_doc_state() -> DocumentIntelligenceState:
    global _state
    return _state


def open_and_ingest_document(user_query: str) -> str:
    """
    Locate document on disk, open viewer, extract text, and set as active context.
    """
    state = get_doc_state()
    res = resolve_document_location(user_query)
    status = res["status"]

    if status == "not_found":
        state.clear_disambiguation()
        return (
            f"Sir, I searched your Desktop, Documents, and Downloads folders, "
            f"but could not find any document matching '{user_query}'."
        )

    if status == "multiple_matches":
        candidates = res["candidates"]
        state.pending_candidates = candidates
        state.last_query = user_query

        cand_lines = []
        for i, c in enumerate(candidates, 1):
            cand_lines.append(f"  {i}. `{c['name']}` (in `{os.path.dirname(c['path'])}`)")

        cand_str = "\n".join(cand_lines)
        return (
            f"Sir, I found {len(candidates)} matching documents for '{user_query}':\n\n"
            f"{cand_str}\n\n"
            f"👉 *Which one would you like me to open? (Reply with 1, 2, 3... or the filename)*"
        )

    # Single match!
    file_info = res["file"]
    file_path = file_info["path"]
    state.clear_disambiguation()

    # Open viewer & ingest
    open_document(file_path)
    ingest_msg = load_study_material(file_path)

    return (
        f"📖 **Opened `{file_info['name']}`!**\n\n"
        f"• **Location**: `{file_path}`\n"
        f"{ingest_msg}"
    )


def resolve_disambiguation_selection(user_input: str) -> str:
    """
    User selected a candidate from disambiguation list (e.g. '1', 'the second one', 'Resume_2026.docx').
    """
    state = get_doc_state()
    candidates = state.pending_candidates

    if not candidates:
        return None

    selected = None
    input_lower = user_input.lower().strip()

    # Check number input
    digit_match = re.search(r'\b([1-9])\b', input_lower)
    if digit_match:
        idx = int(digit_match.group(1)) - 1
        if 0 <= idx < len(candidates):
            selected = candidates[idx]

    # Check words like "first", "second", "third"
    word_map = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2}
    if not selected:
        for w, idx in word_map.items():
            if w in input_lower and idx < len(candidates):
                selected = candidates[idx]
                break

    # Check filename match
    if not selected:
        for c in candidates:
            if c["name"].lower() in input_lower or os.path.splitext(c["name"].lower())[0] in input_lower:
                selected = c
                break

    if not selected:
        # Default to top candidate if selection unclear
        selected = candidates[0]

    state.clear_disambiguation()

    file_path = selected["path"]
    open_document(file_path)
    ingest_msg = load_study_material(file_path)

    return (
        f"📖 **Opened `{selected['name']}`!**\n\n"
        f"• **Location**: `{file_path}`\n"
        f"{ingest_msg}"
    )


def search_text_in_active_document(search_term: str) -> str:
    """
    Search for all occurrences/mentions of a keyword/phrase inside the active document.
    """
    session = get_study_session()
    doc = session.get_active_doc()

    if not doc:
        return "Sir, no document is currently open. Please ask me to open a document first."

    term_clean = search_term.lower().strip()
    pages = doc.get("pages", [])
    matches = []

    for p in pages:
        p_num = p.get("page_number", 1)
        p_content = p.get("content", "")

        lines = p_content.split("\n")
        for line_idx, line in enumerate(lines, 1):
            if term_clean in line.lower():
                matches.append({
                    "page": p_num,
                    "line": line_idx,
                    "snippet": line.strip()
                })

    if not matches:
        return f"Sir, I searched `{doc['title']}` for '{search_term}', but found no mentions of it."

    match_lines = []
    for m in matches[:10]:  # Limit top 10
        match_lines.append(f"• **Page {m['page']}**: \"...{m['snippet']}...\"")

    matches_summary = "\n".join(match_lines)
    count_str = f"found {len(matches)} mentions" if len(matches) > 10 else f"found {len(matches)} mention(s)"

    return (
        f"🔍 **Search Results for '{search_term}' in `{doc['title']}`**\n\n"
        f"I {count_str}:\n\n"
        f"{matches_summary}\n\n"
        f"Sir, would you like me to explain any of these pages or sections in detail?"
    )


def handle_viewer_control(command: str) -> str:
    """
    Handle viewer interaction commands (scroll, zoom, go to page, close).
    """
    cmd_lower = command.lower().strip()

    if any(w in cmd_lower for w in ["scroll down", "next page", "page down"]):
        scroll_document("down", amount=4)
        return "Sir, I have scrolled down the document."

    if any(w in cmd_lower for w in ["scroll up", "previous page", "page up"]):
        scroll_document("up", amount=4)
        return "Sir, I have scrolled up the document."

    if any(w in cmd_lower for w in ["zoom in", "enlarge", "make bigger"]):
        zoom_document("in")
        return "Sir, I zoomed in on the document."

    if any(w in cmd_lower for w in ["zoom out", "make smaller"]):
        zoom_document("out")
        return "Sir, I zoomed out of the document."

    if any(w in cmd_lower for w in ["close the document", "close document", "close file"]):
        close_document_viewer()
        return "Sir, I have closed the active document viewer."

    # Go to page X in viewer
    p_match = re.search(r'(?:go to|jump to|open)\s+page\s+(\d+)', cmd_lower)
    if p_match:
        page_num = int(p_match.group(1))
        goto_page_in_viewer(page_num)
        session = get_study_session()
        session.current_page = page_num
        return f"Sir, I navigated the document viewer to Page {page_num}."

    return None
