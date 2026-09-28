"""
MCP Docker Gateway Client for JARVIS
Connects to Docker MCP Gateway to access all MCP servers efficiently
"""

import asyncio
import json
import subprocess
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class MCPTool:
    """Represents an MCP tool"""
    name: str
    description: str
    server: str
    parameters: Dict[str, Any]


@dataclass
class MCPServer:
    """Represents an MCP server"""
    name: str
    tools: List[MCPTool]
    resources: List[str]


class MCPDockerClient:
    """
    Efficient MCP client that connects to Docker Gateway.
    Manages connections, discovers tools, and executes commands.
    """
    
    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self._initialized = False
        self._lock = threading.Lock()
        self._tool_cache: Dict[str, MCPTool] = {}
    
    async def initialize(self):
        """Initialize connection to Docker MCP Gateway and discover servers"""
        if self._initialized:
            return True
        
        with self._lock:
            try:
                print("[MCP] Connecting to Docker MCP Gateway...")
                
                # List available servers
                result = subprocess.run(
                    ["docker", "mcp", "gateway", "list"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    print(f"[MCP] Gateway response: {result.stdout}")
                    await self._discover_servers()
                    self._initialized = True
                    print(f"[MCP] [OK] Initialized with {len(self.servers)} servers")
                    return True
                else:
                    print(f"[MCP] ✗ Gateway error: {result.stderr}")
                    return False
                    
            except subprocess.TimeoutExpired:
                print("[MCP] ✗ Gateway connection timeout")
                return False
            except FileNotFoundError:
                print("[MCP] ✗ Docker MCP not found. Is Docker running?")
                return False
            except Exception as e:
                print(f"[MCP] ✗ Initialization error: {e}")
                return False
    
    async def _discover_servers(self):
        """Discover all available MCP servers and their tools"""
        # For now, manually configure known servers from the screenshot
        # In production, this would query the gateway dynamically
        
        known_servers = [
            "azure",
            "duckduckgo",
            "fetch",
            "git",
            "github",
            "github-chat",
            "obsidian",
            "playwright"
        ]
        
        for server_name in known_servers:
            try:
                tools = await self._get_server_tools(server_name)
                self.servers[server_name] = MCPServer(
                    name=server_name,
                    tools=tools,
                    resources=[]
                )
                print(f"[MCP] [OK] Discovered server: {server_name} ({len(tools)} tools)")
            except Exception as e:
                print(f"[MCP] ⚠ Could not discover {server_name}: {e}")
    
    async def _get_server_tools(self, server_name: str) -> List[MCPTool]:
        """Get available tools from a specific server"""
        # This would query the MCP protocol's list_tools method
        # For now, returning predefined tools based on server type
        
        tools_map = {
            "duckduckgo": [
                MCPTool("web_search", "Search the web using DuckDuckGo", server_name, {"query": "string"}),
            ],
            "fetch": [
                MCPTool("fetch_url", "Fetch content from a URL", server_name, {"url": "string"}),
            ],
            "github": [
                MCPTool("search_repos", "Search GitHub repositories", server_name, {"query": "string"}),
                MCPTool("get_repo_info", "Get repository information", server_name, {"repo": "string"}),
            ],
            "obsidian": [
                MCPTool("search_notes", "Search Obsidian notes", server_name, {"query": "string"}),
                MCPTool("create_note", "Create a new note", server_name, {"title": "string", "content": "string"}),
            ],
            "playwright": [
                MCPTool("navigate", "Navigate to a URL", server_name, {"url": "string"}),
                MCPTool("screenshot", "Take a screenshot", server_name, {"selector": "string"}),
            ]
        }
        
        return tools_map.get(server_name, [])
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool via Docker MCP Gateway.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters
            
        Returns:
            Tool execution result
        """
        # Find which server owns this tool
        server_name = None
        for srv_name, server in self.servers.items():
            if any(tool.name == tool_name for tool in server.tools):
                server_name = srv_name
                break
        
        if not server_name:
            return {"error": f"Tool '{tool_name}' not found"}
        
        try:
            # Execute via MCP protocol
            # In real implementation, this would use the MCP SDK
            print(f"[MCP] Executing {tool_name} on {server_name} with {parameters}")
            
            # Placeholder - would actually call the Docker gateway
            result = await self._mock_execute(tool_name, parameters)
            return result
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _mock_execute(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Mock execution until real MCP client is integrated"""
        # This will be replaced with actual MCP protocol calls
        return {
            "status": "success",
            "tool": tool_name,
            "result": f"Executed {tool_name} with {parameters}"
        }
    
    async def search_duckduckgo(self, query: str) -> List[Dict[str, Any]]:
        """Search the web using DuckDuckGo MCP server"""
        result = await self.execute_tool("web_search", {"query": query})
        return result
    
    async def fetch_url(self, url: str) -> str:
        """Fetch content from URL using Fetch MCP server"""
        result = await self.execute_tool("fetch_url", {"url": url})
        return result.get("result", "")
    
    async def search_obsidian(self, query: str) -> List[Dict[str, Any]]:
        """Search Obsidian notes"""
        result = await self.execute_tool("search_notes", {"query": query})
        return result
    
    async def github_search(self, query: str) -> List[Dict[str, Any]]:
        """Search GitHub repositories via MCP"""
        result = await self.execute_tool("search_repos", {"query": query})
        return result
    
    def get_available_tools(self) -> List[str]:
        """Get list of all available tool names"""
        tools = []
        for server in self.servers.values():
            tools.extend([tool.name for tool in server.tools])
        return tools
    
    def get_server_status(self) -> Dict[str, Any]:
        """Get status of all MCP servers"""
        return {
            "initialized": self._initialized,
            "servers": {
                name: {
                    "tools_count": len(server.tools),
                    "tools": [t.name for t in server.tools]
                }
                for name, server in self.servers.items()
            }
        }


# Global instance with lazy initialization
_mcp_client = None
_init_lock = threading.Lock()


def get_mcp_client() -> MCPDockerClient:
    """Get or create the global MCP client instance"""
    global _mcp_client
    
    if _mcp_client is None:
        with _init_lock:
            if _mcp_client is None:
                _mcp_client = MCPDockerClient()
    
    return _mcp_client


async def ensure_initialized():
    """Ensure MCP client is initialized"""
    client = get_mcp_client()
    if not client._initialized:
        await client.initialize()
    return client


# Synchronous wrappers for JARVIS integration
def search_web_sync(query: str) -> str:
    """Search web via DuckDuckGo (synchronous)"""
    async def _search():
        client = await ensure_initialized()
        result = await client.search_duckduckgo(query)
        return format_search_results(result)
    
    return asyncio.run(_search())


def search_obsidian_sync(query: str) -> str:
    """Search Obsidian notes (synchronous)"""
    async def _search():
        client = await ensure_initialized()
        result = await client.search_obsidian(query)
        return format_obsidian_results(result)
    
    return asyncio.run(_search())


def format_search_results(results: Any) -> str:
    """Format search results for display"""
    if isinstance(results, dict) and "error" in results:
        return f"Error: {results['error']}"
    
    return f"Search results: {results}"


def format_obsidian_results(results: Any) -> str:
    """Format Obsidian results for display"""
    if isinstance(results, dict) and "error" in results:
        return f"Error: {results['error']}"
    
    return f"Obsidian notes: {results}"
