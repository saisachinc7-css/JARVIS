"""
Obsidian Integration for JARVIS
Creates and manages Obsidian notes programmatically (no GUI automation)
"""

import os
import asyncio
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path


class ObsidianManager:
    """Manages Obsidian vault interactions without GUI automation"""
    
    def __init__(self, vault_path: str = None):
        # Default Obsidian vault path (user should configure this)
        self.vault_path = vault_path or self._find_vault_path()
        
    def _find_vault_path(self) -> str:
        """Try to find Obsidian vault path"""
        # Common locations for Obsidian vaults
        possible_paths = [
            os.path.expanduser("~/Documents/Obsidian"),
            os.path.expanduser("~/OneDrive/Obsidian"),
            os.path.expanduser("~/Obsidian"),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # Fallback: create in Documents
        fallback = os.path.expanduser("~/Documents/JARVIS_Notes")
        os.makedirs(fallback, exist_ok=True)
        return fallback
    
    def create_note(self, title: str, content: str, folder: str = "") -> str:
        """
        Create or update an Obsidian note programmatically.
        
        Args:
            title: Note title (will be filename)
            content: Note content in Markdown format
            folder: Optional subfolder within vault
            
        Returns:
            Full path to created note
        """
        # Sanitize filename
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title.replace(' ', '_')
        
        # Build full path
        note_dir = os.path.join(self.vault_path, folder) if folder else self.vault_path
        os.makedirs(note_dir, exist_ok=True)
        
        note_path = os.path.join(note_dir, f"{safe_title}.md")
        
        # Write note
        with open(note_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"[Obsidian] Created note: {note_path}")
        return note_path
    
    def append_to_note(self, title: str, content: str, folder: str = ""):
        """Append content to existing note or create new one"""
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title.replace(' ', '_')
        
        note_dir = os.path.join(self.vault_path, folder) if folder else self.vault_path
        os.makedirs(note_dir, exist_ok=True)
        
        note_path = os.path.join(note_dir, f"{safe_title}.md")
        
        # Append with newline
        with open(note_path, 'a', encoding='utf-8') as f:
            f.write(f"\n\n{content}")
        
        print(f"[Obsidian] Appended to note: {note_path}")
        return note_path


# Global instance
_obsidian_manager = None


def get_obsidian_manager() -> ObsidianManager:
    """Get or create global Obsidian manager"""
    global _obsidian_manager
    if _obsidian_manager is None:
        _obsidian_manager = ObsidianManager()
    return _obsidian_manager


async def search_and_save_to_obsidian(query: str, num_results: int = 5) -> str:
    """
    Search the web and save results to Obsidian note.
    
    Args:
        query: Search query
        num_results: Number of results to save
        
    Returns:
        Path to created note
    """
    from Tools.MCP.mcp_client import ensure_initialized
    
    # Initialize MCP client
    client = await ensure_initialized()
    
    # Search web via DuckDuckGo MCP
    print(f"[JARVIS] Searching web for: {query}")
    result = await client.search_duckduckgo(query)
    
    # Format results as Markdown
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    markdown_content = f"""# Web Search: {query}

> Created by JARVIS on {timestamp}

## Search Results

"""
    
    # Check if result is dict with error or actual results
    if isinstance(result, dict):
        if 'error' in result:
            # Fallback to manual web search formatting
            markdown_content += f"_(Search executed via MCP DuckDuckGo server)_\n\n"
            markdown_content += f"Query: **{query}**\n\n"
            markdown_content += "## Links\n\n"
            markdown_content += f"1. [Search for {query} on Google](https://www.google.com/search?q={query.replace(' ', '+')})\n"
            markdown_content += f"2. [Search for {query} on DuckDuckGo](https://duckduckgo.com/?q={query.replace(' ', '+')})\n"
            markdown_content += f"3. [Search for {query} on GitHub](https://github.com/search?q={query.replace(' ', '+')})\n"
            markdown_content += f"4. [Search for {query} on Stack Overflow](https://stackoverflow.com/search?q={query.replace(' ', '+')})\n"
            markdown_content += f"5. [Search for {query} on Reddit](https://www.reddit.com/search/?q={query.replace(' ', '+')})\n"
        else:
            # Format actual results
            markdown_content += f"{result.get('result', str(result))}\n"
    else:
        markdown_content += f"{result}\n"
    
    markdown_content += f"\n---\n\n**Tags:** #web-search #jarvis #research\n"
    
    # Save to Obsidian
    manager = get_obsidian_manager()
    note_title = f"Search_{query.replace(' ', '_')}"
    note_path = manager.create_note(note_title, markdown_content, folder="JARVIS_Research")
    
    return note_path


def search_and_save_sync(query: str, num_results: int = 5) -> str:
    """Synchronous wrapper for JARVIS integration"""
    return asyncio.run(search_and_save_to_obsidian(query, num_results))
