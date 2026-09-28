"""
Custom Workflow Automations for JARVIS

Example: "let's create a video today"
→ Opens YouTube (Edge), Instagram (Edge), Premiere Pro, After Effects

Add more workflows by defining new functions and registering them
in the WORKFLOWS dict at the bottom.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Tools.Simple_Automations.App_open import open as open_app
from Tools.Simple_Automations.Web_open import open as open_web


def video_creation_workflow():
    """
    'Let's create a video today' workflow.
    Opens all apps needed for video production.
    """
    print("[Custom] 🎬 Starting video creation workflow...")
    
    # Open reference sites in Edge
    open_web("youtube")
    open_web("instagram")
    
    # Open editing software
    open_app("premiere pro")
    open_app("after effects")
    
    print("[Custom] [OK] Video creation workspace ready!")
    return "Video creation workspace is set up, sir! YouTube, Instagram, Premiere Pro, and After Effects are opening."


def coding_workflow():
    """
    'Let's code today' workflow.
    Opens VS Code, terminal, and documentation.
    """
    print("[Custom] 💻 Starting coding workflow...")
    
    open_app("visual studio code")
    open_web("github")
    
    print("[Custom] [OK] Coding workspace ready!")
    return "Coding workspace is set up, sir! VS Code and GitHub are opening."


def research_workflow():
    """
    'Let's do research' workflow.
    Opens research tools.
    """
    print("[Custom] 📚 Starting research workflow...")
    
    open_web("google scholar")
    open_app("obsidian")
    open_web("chatgpt")
    
    print("[Custom] [OK] Research workspace ready!")
    return "Research workspace is ready, sir! Scholar, Obsidian, and ChatGPT are opening."


# ============================================================================
# WORKFLOW REGISTRY
# ============================================================================
WORKFLOWS = {
    "video": video_creation_workflow,
    "coding": coding_workflow,
    "research": research_workflow,
}


def run_workflow(name: str) -> str:
    """Run a named workflow."""
    workflow = WORKFLOWS.get(name.lower())
    if workflow:
        return workflow()
    return f"No workflow found for '{name}'. Available: {', '.join(WORKFLOWS.keys())}"
