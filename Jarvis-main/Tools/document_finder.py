"""
Document Finder for JARVIS Document Intelligence
Autonomously searches Desktop, Documents, Downloads, Pictures, User Home, and Workspaces
for requested documents with smart fuzzy matching and disambiguation support.
"""

import os
import re
import glob
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional


COMMON_FOLDERS = [
    os.path.join(os.path.expanduser("~"), "Desktop"),
    os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop"),
    os.path.join(os.path.expanduser("~"), "Documents"),
    os.path.join(os.path.expanduser("~"), "OneDrive", "Documents"),
    os.path.join(os.path.expanduser("~"), "Downloads"),
    os.path.join(os.path.expanduser("~"), "Pictures"),
    r"d:\ANTIGRAVITY\JARVIS 2.0\Jarvis-main",
    os.path.expanduser("~"),
]

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".txt", ".md",
    ".png", ".jpg", ".jpeg", ".webp", ".html", ".csv", ".json", ".rtf"
}



def _clean_query(query: str) -> str:
    """Clean query string removing command prefixes like 'open', 'find', 'from desktop'."""
    q = query.lower().strip()
    remove_words = [
        "open", "find", "load", "read", "search for", "search", "show me", "locate",
        "the", "file", "document", "pdf", "docx", "pptx", "from my desktop", "from desktop",
        "from downloads", "from documents", "my", "please", "jarvis"
    ]
    for w in remove_words:
        q = q.replace(w, " ")
    q = re.sub(r"\s+", " ", q).strip()
    return q if q else query.lower().strip()


def find_documents(query: str, target_folder: Optional[str] = None, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search common directories for files matching the query.
    
    Returns a list of candidate dicts:
    [{'name': str, 'path': str, 'ext': str, 'size': int, 'score': float}]
    """
    query_clean = _clean_query(query)
    query_tokens = [t for t in query_clean.split() if len(t) > 1]
    
    # Determine search roots
    search_roots = []
    if target_folder:
        tf_lower = target_folder.lower()
        if "desktop" in tf_lower:
            search_roots.extend([
                os.path.join(os.path.expanduser("~"), "Desktop"),
                os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
            ])
        elif "download" in tf_lower:
            search_roots.append(os.path.join(os.path.expanduser("~"), "Downloads"))
        elif "document" in tf_lower:
            search_roots.extend([
                os.path.join(os.path.expanduser("~"), "Documents"),
                os.path.join(os.path.expanduser("~"), "OneDrive", "Documents")
            ])
    
    if not search_roots:
        search_roots = COMMON_FOLDERS

    candidates = []
    seen_paths = set()

    for root in search_roots:
        if not os.path.exists(root):
            continue
            
        # Walk up to 3 levels deep
        for dirpath, _, filenames in os.walk(root):
            # Limit depth
            depth = dirpath.count(os.sep) - root.count(os.sep)
            if depth > 3:
                continue

            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in SUPPORTED_EXTENSIONS:
                    continue

                full_path = os.path.normpath(os.path.join(dirpath, fname))
                if full_path in seen_paths:
                    continue
                seen_paths.add(full_path)

                fname_lower = fname.lower()
                fname_no_ext = os.path.splitext(fname_lower)[0]

                # Match scoring
                score = 0.0

                # Exact filename match
                if query.lower() == fname_lower or query.lower() == fname_no_ext:
                    score = 1.0
                # Exact token match
                elif query_clean in fname_lower:
                    score = 0.9
                else:
                    # Token overlap match
                    matched_tokens = sum(1 for t in query_tokens if t in fname_lower)
                    if matched_tokens > 0:
                        ratio = matched_tokens / len(query_tokens) if query_tokens else 0
                        fuzzy_ratio = SequenceMatcher(None, query_clean, fname_no_ext).ratio()
                        score = max(ratio * 0.8, fuzzy_ratio * 0.7)

                if score > 0.35:
                    candidates.append({
                        "name": fname,
                        "path": full_path,
                        "ext": ext,
                        "size_kb": round(os.path.getsize(full_path) / 1024, 1),
                        "score": score
                    })

    # Sort candidates by score descending
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:max_results]


def resolve_document_location(user_query: str) -> Dict[str, Any]:
    """
    High-level document finder interface.
    Returns:
      {
        "status": "single_match" | "multiple_matches" | "not_found",
        "file": dict (if single_match),
        "candidates": list (if multiple_matches),
        "message": str
      }
    """
    # Check if target folder specified ("from my desktop", "in downloads")
    target_folder = None
    query_lower = user_query.lower()
    if "desktop" in query_lower:
        target_folder = "desktop"
    elif "download" in query_lower:
        target_folder = "downloads"
    elif "document" in query_lower:
        target_folder = "documents"

    candidates = find_documents(user_query, target_folder=target_folder)

    if not candidates:
        return {
            "status": "not_found",
            "file": None,
            "candidates": [],
            "message": f"Sir, I searched your folders but could not find any document matching '{user_query}'."
        }

    # If top candidate score is significantly higher than second (e.g. score >= 0.9), pick it immediately
    if len(candidates) == 1 or candidates[0]["score"] >= 0.85 or (len(candidates) > 1 and candidates[0]["score"] - candidates[1]["score"] > 0.3):
        return {
            "status": "single_match",
            "file": candidates[0],
            "candidates": candidates,
            "message": f"Found '{candidates[0]['name']}'."
        }

    # Multiple close candidates — requires disambiguation
    return {
        "status": "multiple_matches",
        "file": None,
        "candidates": candidates,
        "message": f"Sir, I found multiple documents matching '{user_query}'."
    }
