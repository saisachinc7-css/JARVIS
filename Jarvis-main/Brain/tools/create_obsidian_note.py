"""
Obsidian note creation tool for JARVIS
"""

import os
from datetime import datetime


def create_obsidian_note(title: str, content: str) -> str:
    """
    Create an Obsidian note.
    
    Args:
        title: Title of the note
        content: Content to write in the note
        
    Returns:
        Path to created note
    """
    from Tools.obsidian_integration import get_obsidian_manager
    
    manager = get_obsidian_manager()
    
    # Add timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    markdown_content = f"""# {title}

> Created by JARVIS on {timestamp}

{content}

---

**Tags:** #jarvis #notes
"""
    
    note_path = manager.create_note(title, markdown_content,folder="JARVIS_Notes")
    
    return f"Note '{title}' created at: {note_path}"
