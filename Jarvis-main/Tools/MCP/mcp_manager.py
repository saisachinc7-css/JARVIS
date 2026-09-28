"""
MCP Manager for JARVIS
Handles Model Context Protocol connections via Docker Gateway
Provides high-level access to all MCP servers
"""

import asyncio
from typing import Dict, List, Any, Optional
from Tools.MCP.mcp_client import get_mcp_client, ensure_initialized, search_web_sync, search_obsidian_sync


class MCPManager:
    """
    High-level MCP manager for JARVIS.
    Coordinates access to all MCP servers via Docker Gateway.
    """
    
    def __init__(self):
        self.client = get_mcp_client()
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all MCP servers"""
        return self.client.get_server_status()
    
    def get_available_tools(self) -> List[str]:
        """Get list of all available tools"""
        return self.client.get_available_tools()
    
    async def search_github_repos(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search GitHub repositories - uses REST API directly for reliability"""
        # Use REST API directly since MCP mock execution is not integrated
        return await self._github_rest_fallback(query, max_results)

    
    async def _github_rest_fallback(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Fallback to GitHub REST API if MCP unavailable"""
        import requests
        
        try:
            response = requests.get(
                'https://api.github.com/search/repositories',
                params={'q': query, 'sort': 'stars', 'order': 'desc', 'per_page': max_results},
                headers={'Accept': 'application/vnd.github.v3+json'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return [
                    {
                        'name': item.get('full_name', ''),
                        'description': item.get('description', 'No description'),
                        'stars': item.get('stargazers_count', 0),
                        'url': item.get('html_url', ''),
                        'language': item.get('language', 'Unknown')
                    }
                    for item in data.get('items', [])
                ]
            return []
        except Exception as e:
            print(f"Error in REST fallback: {e}")
            return []
    
    async def fetch_url_content(self, url: str) -> Optional[str]:
        """Fetch URL content via MCP Fetch server"""
        client = await ensure_initialized()
        return await client.fetch_url(url)
    
    async def search_web(self, query: str) -> List[Dict[str, Any]]:
        """Search web via DuckDuckGo MCP server"""
        client = await ensure_initialized()
        return await client.search_duckduckgo(query)
    
    async def search_obsidian_notes(self, query: str) -> List[Dict[str, Any]]:
        """Search Obsidian notes via MCP server"""
        client = await ensure_initialized()
        return await client.search_obsidian(query)


# Global instance
mcp_manager = MCPManager()


async def handle_github_search(query: str) -> str:
    """
    Handle GitHub search requests from JARVIS.
    
    Args:
        query: User's search query
        
    Returns:
        Formatted response string
    """
    repos = await mcp_manager.search_github_repos(query)
    
    if not repos:
        return f"No GitHub repositories found for: {query}"
    
    result = f"Found {len(repos)} GitHub repositories for '{query}':\n\n"
    for i, repo in enumerate(repos, 1):
        result += f"{i}. {repo['name']} ⭐ {repo['stars']}\n"
        result += f"   {repo['description']}\n"
        result += f"   🔗 {repo['url']}\n"
        if repo['language']:
            result += f"   📝 {repo['language']}\n"
        result += "\n"
    
    return result


# Synchronous wrapper for JARVIS integration
def search_github_sync(query: str) -> str:
    """Synchronous wrapper for GitHub search"""
    return asyncio.run(handle_github_search(query))
