"""
Multi-Task Queue System for JARVIS
==================================
Decomposes complex user requests into independent OR chained sub-tasks,
queues them, and executes them concurrently (independent) or sequentially (chained).

Architecture:
    TaskDecomposer  -> LLM splits user input into separate tasks
    TaskQueue       -> Thread-safe queue holding pending tasks
    TaskExecutor    -> Orchestrates parallel/sequential execution
    
Flow (Independent):
    User: "Search GitHub for opencv projects and remind me I have a meeting tmrw at 3pm"
      -> TaskDecomposer -> 2 INDEPENDENT tasks
      -> TaskExecutor -> executes in PARALLEL
      -> Collect all results -> deliver unified response

Flow (Chained):
    User: "Summarize my last email and send it to CONTACT_NAME_ONE on WhatsApp"
      -> TaskDecomposer -> 2 CHAINED tasks (task 2 depends on task 1 output)
      -> TaskExecutor -> executes SEQUENTIALLY, passing output forward
      -> Task 1 result feeds into Task 2 -> deliver final response

Key Design:
    - Single-task inputs bypass decomposition entirely (zero overhead)
    - Independent tasks run in parallel via ThreadPoolExecutor
    - Chained/dependent tasks run sequentially, passing output forward
    - Results are aggregated and spoken/displayed AFTER all tasks complete
    - Thread-safe, production-ready with timeouts and error handling
    - All print output is ASCII-safe for Windows cp1252 consoles
"""

import threading
import queue
import time
import json
import re
import traceback
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed, Future

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# SAFE PRINT -- prevents cp1252 encoding crashes on Windows console
# ============================================================================

def _safe_print(msg: str):
    """Print a message safely, replacing non-ASCII characters if needed."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', errors='replace').decode('ascii'))


# ============================================================================
# UNICODE SANITIZER -- for chain context passing on Windows
# ============================================================================

# Common emoji -> ASCII replacements (GitHub results, etc.)
_UNICODE_REPLACEMENTS = {
    '\u2b50': '*',      # â­ -> *
    '\u2606': '*',      # â˜† -> *
    '\u2605': '*',      # â˜… -> *
    '\U0001f517': '',   # ðŸ”— -> (remove)
    '\U0001f4dd': '',   # ðŸ“ -> (remove)
    '\U0001f4e6': '',   # ðŸ“¦ -> (remove)
    '\U0001f30d': '',   # ðŸŒ -> (remove)
    '\U0001f680': '',   # ðŸš€ -> (remove)
    '\U0001f4c1': '',   # ðŸ“ -> (remove)
    '\U0001f4c4': '',   # ðŸ“„ -> (remove)
    '\U0001f4a1': '',   # ðŸ’¡ -> (remove)
    '\U0001f527': '',   # ðŸ”§ -> (remove)
    '\U0001f50d': '',   # ðŸ” -> (remove)
    '\u2192': '->',     # â†’ -> ->
    '\u2190': '<-',     # â† -> <-
    '\u2713': '[ok]',   # âœ“ -> [ok]
    '\u2714': '[ok]',   # âœ” -> [ok]
    '\u2716': '[x]',    # âœ– -> [x]
    '\u2718': '[x]',    # âœ˜ -> [x]
    '\u2500': '-',      # â”€ -> -
    '\u2502': '|',      # â”‚ -> |
    '\u2022': '-',      # â€¢ -> -
    '\u25cf': '-',      # â— -> -
}

def _sanitize_for_chain(text: str) -> str:
    """
    Sanitize text for safe passing between chained tasks.

    Replaces Unicode emojis/symbols with ASCII equivalents so that:
    1. print() never crashes on cp1252 Windows consoles
    2. WhatsApp parsers can cleanly handle the text
    3. LLM re-classification doesn't get confused by emojis

    Also collapses excessive whitespace and trims to a reasonable length.
    """
    if not text:
        return text

    # Replace known emoji/symbol mappings
    for char, replacement in _UNICODE_REPLACEMENTS.items():
        text = text.replace(char, replacement)

    # Strip any remaining non-ASCII characters (safety net)
    # Use 'replace' to substitute with '?' instead of crashing
    text = text.encode('ascii', errors='replace').decode('ascii')

    # Collapse multiple spaces/pipes
    text = re.sub(r'\s{3,}', '  ', text)
    text = re.sub(r'\|\s*\|', '|', text)

    return text.strip()


def _format_github_for_whatsapp(context: str) -> str:
    """
    Reformat GitHub search results into a clean, WhatsApp-friendly message.

    Input format (from mcp_manager.py):
        Found 5 GitHub repositories for 'query':
        1. user/repo â­ 1234
           Description text
           ðŸ”— https://github.com/...
           ðŸ“ Python

    Output format (for WhatsApp):
        GitHub Repos:
        1. user/repo (1234 stars) - Description text
           https://github.com/...
        2. ...
    """
    if not context:
        return context

    lines = context.split('\n')
    formatted_lines = []
    i = 0

    # Keep header line if it looks like "Found X GitHub repositories..."
    if lines and ('github' in lines[0].lower() and 'repositor' in lines[0].lower()):
        header = _sanitize_for_chain(lines[0])
        formatted_lines.append(header)
        formatted_lines.append('')
        i = 1

    # Parse repo entries
    repo_num = 0
    while i < len(lines):
        line = lines[i].strip()

        # Detect a numbered repo line: "1. user/repo â­ 1234"
        repo_match = re.match(r'^(\d+)\.\s+(\S+)\s+.*?(\d+)', _sanitize_for_chain(line))
        if repo_match:
            repo_num += 1
            name = repo_match.group(2)
            stars = repo_match.group(3)

            # Gather description, URL, language from following lines
            desc = ''
            url = ''
            lang = ''
            j = i + 1
            while j < len(lines) and not re.match(r'^\d+\.', lines[j].strip()):
                sline = lines[j].strip()
                if sline.startswith(('\U0001f517', 'http')):
                    # URL line
                    url = re.sub(r'^[^\w]*', '', sline).strip()
                    if not url.startswith('http'):
                        url_match = re.search(r'(https?://\S+)', sline)
                        url = url_match.group(1) if url_match else ''
                elif sline.startswith('\U0001f4dd') or (lang == '' and len(sline) < 30 and sline.replace(' ', '').isalpha()):
                    lang = _sanitize_for_chain(sline)
                elif not desc and sline and not sline.startswith(('\u2b50', '\u2606', '\u2605')):
                    desc = _sanitize_for_chain(sline)
                j += 1

            # Build clean repo entry
            entry = f"{repo_num}. {name} ({stars} stars)"
            if desc:
                entry += f" - {desc}"
            formatted_lines.append(entry)
            if url:
                formatted_lines.append(f"   {url}")
            if lang:
                formatted_lines.append(f"   Language: {lang}")
            formatted_lines.append('')
            i = j
        else:
            i += 1

    result = '\n'.join(formatted_lines).strip()

    # If parsing didn't extract any repos, fall back to plain sanitization
    if repo_num == 0:
        return _sanitize_for_chain(context)

    return result


# ============================================================================
# DATA STRUCTURES
# ============================================================================

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType(Enum):
    """Hint for how the task should be routed."""
    AGENT = "agent"          # Can be delegated to an agent (parallel-safe)
    TOOL = "tool"            # Uses a tool (weather, spotify, etc.)
    CONVERSATIONAL = "conversational"  # Memory/schedule/chat
    COMPLEX = "complex"      # Needs deep thinking (secondary brain)
    UNKNOWN = "unknown"      # Let the brain figure it out


@dataclass
class Task:
    """A single decomposed sub-task."""
    id: int
    text: str                                    # The sub-task text
    task_type: TaskType = TaskType.UNKNOWN        # Routing hint
    hint: str = ""                               # Specific hint (e.g., "github_search", "whatsapp")
    depends_on: Optional[int] = None             # Task ID this depends on (for chained tasks)
    order: int = 0                               # Execution order (0 = parallel, 1+ = sequential chain)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    @property
    def duration(self) -> float:
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return 0.0
    
    @property
    def is_chained(self) -> bool:
        """Check if this task depends on another task's output."""
        return self.depends_on is not None and self.depends_on > 0
    
    def mark_started(self):
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = time.time()
    
    def mark_completed(self, result: Dict[str, Any]):
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.completed_at = time.time()
    
    def mark_failed(self, error: str):
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = time.time()


# ============================================================================
# TASK DECOMPOSER -- Uses LLM to split multi-task requests
# ============================================================================

class TaskDecomposer:
    """
    Uses Ollama qwen3:4b to decompose a user request into sub-tasks.
    
    Supports two modes:
    1. INDEPENDENT tasks -> run in parallel (different topics)
    2. CHAINED tasks -> run sequentially, output feeds into next (dependent workflow)
    
    Single-task inputs are detected quickly and bypass LLM decomposition.
    """
    
    MODEL = "qwen2.5:0.5b"
    
    DECOMPOSE_PROMPT = """You are a task decomposer for a voice assistant. Split user requests into separate tasks.

RULES:
1. If the request contains ONLY ONE task, return exactly one task.
2. If the request has MULTIPLE INDEPENDENT tasks (unrelated), split them with depends_on: 0.
3. If the request has CHAINED/DEPENDENT tasks (task B needs task A's result), mark the dependency.
4. Preserve the user's original wording as much as possible.
5. For chained tasks: the FIRST task produces data, the SECOND task consumes/sends it.

CHAINED vs INDEPENDENT:
- CHAINED: "summarize my email and send it to X on WhatsApp" -> Task 1 produces summary, Task 2 sends it
- CHAINED: "check the weather and tell mom about it" -> Task 1 gets weather, Task 2 sends it
- CHAINED: "read my last email and forward it to X" -> Task 1 reads, Task 2 forwards
- CHAINED: "search for AI news and save the links to obsidian" -> Task 1 searches, Task 2 saves
- INDEPENDENT: "search GitHub for python and I have a meeting tomorrow" -> unrelated tasks
- INDEPENDENT: "play music and check the weather" -> unrelated tasks
- SINGLE: "open chrome and search for news" -> one compound browser action
- SINGLE: "send a message to CONTACT_NAME_ONE saying I will be late" -> one action

TYPE HINTS:
- "agent" -> WhatsApp messaging, browser automation, research/RAG
- "tool" -> weather, spotify, open app, github search, web search, system control, gmail, calendar
- "conversational" -> personal info, memory, schedule, greetings
- "complex" -> code generation, planning, analysis
- "unknown" -> when unsure

SPECIFIC HINTS: "whatsapp", "browser", "github_search", "web_search", "play_media", "open_app", "open_web", "weather", "schedule", "memory", "system_control", "gmail", "calendar", ""

RESPOND WITH ONLY VALID JSON:
{
    "task_count": <number>,
    "is_chained": <true if tasks depend on each other, false if independent>,
    "tasks": [
        {
            "text": "<the sub-task in natural language>",
            "type": "<agent|tool|conversational|complex|unknown>",
            "hint": "<specific hint>",
            "order": <1 for first, 2 for second, etc. 0 if independent>,
            "depends_on": <order number of task it depends on, or 0 if independent>
        }
    ]
}

EXAMPLES:

Input: "summarize my last email and send it to CONTACT_NAME_TWO on whatsapp"
Output: {"task_count": 2, "is_chained": true, "tasks": [{"text": "summarize my last email", "type": "tool", "hint": "gmail", "order": 1, "depends_on": 0}, {"text": "send the email summary to CONTACT_NAME_TWO on whatsapp", "type": "agent", "hint": "whatsapp", "order": 2, "depends_on": 1}]}

Input: "check the weather and tell CONTACT_NAME_ONE about it on whatsapp"
Output: {"task_count": 2, "is_chained": true, "tasks": [{"text": "check the weather", "type": "tool", "hint": "weather", "order": 1, "depends_on": 0}, {"text": "send the weather info to CONTACT_NAME_ONE on whatsapp", "type": "agent", "hint": "whatsapp", "order": 2, "depends_on": 1}]}

Input: "search github for opencv projects and I have a meeting tomorrow at 3pm"
Output: {"task_count": 2, "is_chained": false, "tasks": [{"text": "search github for opencv projects", "type": "tool", "hint": "github_search", "order": 0, "depends_on": 0}, {"text": "I have a meeting tomorrow at 3pm", "type": "conversational", "hint": "schedule", "order": 0, "depends_on": 0}]}

Input: "open spotify and play shape of you"
Output: {"task_count": 1, "is_chained": false, "tasks": [{"text": "open spotify and play shape of you", "type": "tool", "hint": "play_media", "order": 0, "depends_on": 0}]}

Input: "read my last email and send it to YOUR_NAME on whatsapp"
Output: {"task_count": 2, "is_chained": true, "tasks": [{"text": "read my last email", "type": "tool", "hint": "gmail", "order": 1, "depends_on": 0}, {"text": "send the email content to YOUR_NAME on whatsapp", "type": "agent", "hint": "whatsapp", "order": 2, "depends_on": 1}]}

Input: "search for AI news and save the links to obsidian"
Output: {"task_count": 2, "is_chained": true, "tasks": [{"text": "search for AI news", "type": "tool", "hint": "web_search", "order": 1, "depends_on": 0}, {"text": "save the search results to obsidian", "type": "tool", "hint": "obsidian", "order": 2, "depends_on": 1}]}
"""

    def __init__(self):
        self._available = None
    
    def is_available(self) -> bool:
        """Check if Ollama is available for decomposition (with 5s timeout)."""
        if self._available is not None:
            return self._available
        
        result = [False]
        def _check():
            try:
                import ollama
                ollama.chat(model=self.MODEL, messages=[{"role": "user", "content": "hi"}],
                           options={"num_predict": 1})
                result[0] = True
            except Exception:
                result[0] = False
        
        t = threading.Thread(target=_check, daemon=True)
        t.start()
        t.join(timeout=5)
        
        if t.is_alive():
            _safe_print("[TaskDecomposer] Ollama availability check timed out")
            self._available = False
        else:
            self._available = result[0]
        return self._available
    
    def _quick_single_task_check(self, user_input: str) -> bool:
        """
        Fast heuristic to detect single-task inputs WITHOUT calling the LLM.
        Returns True if likely a single task (skip decomposition).
        Returns False if likely multi-task (needs LLM decomposition).
        """
        text = user_input.lower().strip()
        words = text.split()
        
        # Very short inputs are almost always single tasks
        if len(words) <= 5:
            return True
        
        # ---- DIRECT MULTI-TASK SIGNALS ----
        multi_task_signals = [
            " and also ", " and then ", " also ", " plus ",
            " as well ", " additionally ", " meanwhile ",
            " at the same time ", " along with ",
            " btw ", " by the way ", " then ", " then at last ",
        ]
        if any(signal in text for signal in multi_task_signals):
            return False
        
        # ---- CHAINED TASK PATTERNS ----
        # "X and send/tell/forward/share to Y" = compound dependent tasks
        # Pronoun group matches: it, them, these X, those X, the X, etc.
        _OBJ = r'(?:(?:it|them|(?:these|those|the)(?:\s+\w+)?)\s+)?'
        chained_patterns = [
            r"and\s+send\s+" + _OBJ + r"(?:to|on|in)\b",
            r"and\s+tell\s+\w+\s+(?:about|on)\b",
            r"and\s+forward\s+" + _OBJ + r"to\b",
            r"and\s+share\s+" + _OBJ + r"(?:with|to|on)\b",
            r"and\s+save\s+" + _OBJ + r"(?:to|in)\b",
            r"and\s+copy\s+" + _OBJ + r"to\b",
            r"and\s+paste\s+" + _OBJ + r"(?:to|in)\b",
            r"and\s+post\s+" + _OBJ + r"(?:to|on|in)\b",
            r"and\s+(?:whatsapp|email|message|text)\s+" + _OBJ + r"to\b",
            r"and\s+(?:reply|respond)\s+(?:to|with)\b",
            # Broader: "and can you send/update/message X" (optional modal)
            r"and\s+(?:can you |could you |please )?(?:send|update|forward|share|message|text|whatsapp|email|inform|notify)\b",
            # "and message/tell X about" (without "to" preposition)
            r"and\s+(?:tell|message|inform|update)\s+\w+\s+about\b",
        ]
        for pattern in chained_patterns:
            if re.search(pattern, text):
                return False
        
        # ---- BACK-REFERENCE CHECK ----
        # If the command part refers BACK to the personal statement with
        # "about that/it/this", "regarding that", "that to X", it's a SINGLE unified task.
        # e.g. "I might not be available for dinner tonight can you chat with CONTACT_NAME_TWO about that"
        #      â†’ single task (message CONTACT_NAME_TWO about not being available)
        back_reference_endings = [
            "about that", "about it", "about this",
            "regarding that", "regarding this",
            "with that", "on that",
        ]
        has_back_reference = any(text.endswith(ref) or f"{ref} " in text for ref in back_reference_endings)
        
        # ---- PERSONAL STATEMENT + COMMAND MIX ----
        personal_starts = ["i ", "i'm ", "i am ", "my ", "tomorrow ", "today "]
        mid_command_phrases = ["can you ", "could you ", "please ", "search ", 
                               "find ", "open ", "play ", "send ", "check ",
                               "tell me ", "show me "]
        
        starts_personal = any(text.startswith(p) for p in personal_starts)
        
        if starts_personal and len(words) > 8:
            for phrase in mid_command_phrases:
                idx = text.find(phrase, 5)
                if idx > 0:
                    before = text[:idx].strip()
                    after = text[idx:].strip()
                    if len(before.split()) >= 3 and len(after.split()) >= 3:
                        # If the command references back to the personal info,
                        # it's a single unified task (e.g. "tell X about that")
                        if has_back_reference:
                            return True
                        # If the command is about communicating the personal info
                        # to someone (chat/tell/message/inform), it's single
                        comm_verbs = ["chat ", "tell ", "message ", "inform ", 
                                      "text ", "whatsapp ", "notify "]
                        if any(after.startswith(f"{phrase.strip()} {cv}") or 
                               after.startswith(cv) for cv in comm_verbs 
                               for phrase in ["can you", "could you", "please"]):
                            if has_back_reference:
                                return True
                        return False
        
        # ---- "AND" WITH CONTEXT SHIFT ----
        has_and = " and " in text
        
        if has_and:
            parts = text.split(" and ", 1)
            if len(parts) == 2:
                before = parts[0].strip()
                after = parts[1].strip()
                
                # ---- BOTH SIDES PERSONAL â†’ SINGLE TASK ----
                # "i have a meeting tomorrow at 4pm and i am planning a road trip"
                # Both halves are personal statements/plans â€” NOT two separate tasks.
                # The smart conversational handler will detect multiple implicit actions
                # (calendar + weather) from this single unified message.
                personal_starts_list = ["i ", "i'm ", "i am ", "my ", "tomorrow", "today"]
                before_personal = any(before.startswith(p) for p in personal_starts_list)
                after_personal = any(after.startswith(p) for p in personal_starts_list)
                
                if before_personal and after_personal:
                    return True  # Single task â€” let smart response handle it
                
                action_verbs = [
                    "open", "close", "play", "search", "find", "send",
                    "check", "tell", "remind", "remember", "show",
                    "summarize", "read", "get", "fetch",
                    "i ", "i'm", "can you", "could you", "what", "how",
                    "set", "turn", "lock", "shut", "restart",
                ]
                
                before_has_verb = any(before.startswith(v) for v in action_verbs)
                after_has_verb = any(after.startswith(v) for v in action_verbs)
                
                if before_has_verb and after_has_verb:
                    # Both start personal â†’ already handled above (single)
                    # Only split when it's action+action (not personal+personal)
                    if not (before_personal and after_personal):
                        return False
                
                command_starts = ["search", "find", "open", "play", "send", "check",
                                  "can you", "could you", "summarize", "read"]
                
                after_command = any(after.startswith(c) for c in command_starts)
                before_command = any(before.startswith(c) for c in command_starts)
                
                if (before_personal and after_command) or (before_command and after_personal):
                    return False
        
        return True
    
    # ---- FAST REGEX FALLBACK (no LLM needed) ----
    
    # Connectors that clearly split independent tasks
    _SPLIT_CONNECTORS = [
        r'\band\s+also\b', r'\balso\b', r'\bplus\b',
        r'\badditionally\b', r'\bmeanwhile\b', r'\balong\s+with\s+that\b',
        r'\bbtw\b', r'\bby\s+the\s+way\b', r'\band\s+then\b',
    ]
    
    # Connectors that split chained/dependent tasks
    # Pronoun group: it, them, these X, those X, the X
    _OBJ = r'(?:(?:it|them|(?:these|those|the)(?:\s+\w+)?)\s+)?'
    _CHAINED_CONNECTORS = [
        r'\band\s+send\s+' + _OBJ + r'(?:to|on|in)\b',
        r'\band\s+forward\s+' + _OBJ + r'to\b',
        r'\band\s+share\s+' + _OBJ + r'(?:with|to|on)\b',
        r'\band\s+save\s+' + _OBJ + r'(?:to|in)\b',
        r'\band\s+post\s+' + _OBJ + r'(?:to|on|in)\b',
        # WhatsApp-specific: "and whatsapp/message them to X"
        r'\band\s+(?:whatsapp|message|text|email)\s+' + _OBJ + r'to\b',
        # Broader: "and can you update/send/message X ..." (catches modal verbs)
        r'\band\s+(?:can you |could you |please )?(?:send|update|forward|share|message|text|whatsapp|email|inform|notify)\b',
        # "and tell/message X about" (no preposition "to")
        r'\band\s+(?:tell|message|inform|update)\s+\w+\s+about\b',
    ]
    
    LLM_TIMEOUT = 60  # Max seconds to wait for LLM decomposition (think=True needs more)
    
    def _fast_regex_decompose(self, user_input: str) -> Optional[List[Task]]:
        """
        Fast regex-based decomposition using known split connectors.
        Returns task list if a clean split is found, else None (needs LLM).
        This is the instant fallback when LLM is too slow or unavailable.
        """
        text = user_input.strip()
        lower = text.lower()
        
        # Try chained connectors first (higher priority)
        for pattern in self._CHAINED_CONNECTORS:
            match = re.search(pattern, lower)
            if match:
                before = text[:match.start()].strip().rstrip(',').strip()
                after = text[match.start():].strip()
                # Remove the "and" prefix from after part
                after = re.sub(r'^and\s+', '', after, flags=re.IGNORECASE).strip()
                
                if before and after and len(before.split()) >= 2 and len(after.split()) >= 2:
                    _safe_print(f"[TaskDecomposer] Fast regex split (chained): '{before[:40]}...' -> '{after[:40]}...'")
                    return [
                        Task(id=1, text=before, task_type=TaskType.UNKNOWN, order=1),
                        Task(id=2, text=after, task_type=TaskType.UNKNOWN, order=2, depends_on=1),
                    ]
        
        # Try independent connectors
        for pattern in self._SPLIT_CONNECTORS:
            match = re.search(pattern, lower)
            if match:
                before = text[:match.start()].strip().rstrip(',').strip()
                after = text[match.end():].strip().lstrip(',').strip()
                
                if before and after and len(before.split()) >= 2 and len(after.split()) >= 2:
                    _safe_print(f"[TaskDecomposer] Fast regex split (independent): '{before[:40]}...' -> '{after[:40]}...'")
                    return [
                        Task(id=1, text=before, task_type=TaskType.UNKNOWN, order=0),
                        Task(id=2, text=after, task_type=TaskType.UNKNOWN, order=0),
                    ]
        
        return None  # No clean split found
    
    def _llm_decompose_with_timeout(self, user_input: str) -> Optional[List[Task]]:
        """
        Call LLM decomposition with a timeout. Returns None if times out.
        Uses think=True so qwen3 can reason internally and produce clean JSON.
        """
        result_container = [None]  # Mutable container for thread result
        error_container = [None]
        
        def _call_llm():
            try:
                import ollama
                response = ollama.chat(
                    model=self.MODEL,
                    messages=[
                        {"role": "system", "content": self.DECOMPOSE_PROMPT},
                        {"role": "user", "content": user_input}
                    ],
                    think=True,   # Let model reason, content has clean JSON
                    format="json",
                    options={
                        "temperature": 0.1,
                        "num_predict": 3000,  # Budget for thinking + JSON
                    }
                )
                result_container[0] = response
            except Exception as e:
                error_container[0] = e
        
        thread = threading.Thread(target=_call_llm, daemon=True)
        thread.start()
        thread.join(timeout=self.LLM_TIMEOUT)
        
        if thread.is_alive():
            _safe_print(f"[TaskDecomposer] LLM timed out after {self.LLM_TIMEOUT}s, using fast fallback")
            return None
        
        if error_container[0]:
            _safe_print(f"[TaskDecomposer] LLM error: {error_container[0]}")
            return None
        
        response = result_container[0]
        if not response:
            return None
        
        try:
            # With think=True, content is cleanly separated from thinking
            raw = (response.message.content or "").strip() if response else ""
            # Safety: also strip any residual think tags
            raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
            
            _safe_print(f"[TaskDecomposer] Raw LLM output: {raw[:200]}")
            
            data = json.loads(raw)
            tasks_data = data.get("tasks", [])
            is_chained = data.get("is_chained", False)
            
            if not tasks_data:
                return None
            
            tasks = []
            for i, t in enumerate(tasks_data, 1):
                task_type_str = t.get("type", "unknown").lower()
                try:
                    task_type = TaskType(task_type_str)
                except ValueError:
                    task_type = TaskType.UNKNOWN
                
                depends_on_val = t.get("depends_on", 0)
                order_val = t.get("order", 0)
                
                task = Task(
                    id=i,
                    text=t.get("text", "").strip(),
                    task_type=task_type,
                    hint=t.get("hint", ""),
                    depends_on=depends_on_val if depends_on_val > 0 else None,
                    order=order_val,
                )
                if task.text:
                    tasks.append(task)
            
            if not tasks:
                return None
            
            chain_label = "CHAINED" if is_chained else "INDEPENDENT"
            _safe_print(f"[TaskDecomposer] Decomposed into {len(tasks)} {chain_label} tasks:")
            for t in tasks:
                dep_str = f" [depends on #{t.depends_on}]" if t.is_chained else ""
                _safe_print(f"  [#{t.id}] ({t.task_type.value}/{t.hint}) {t.text}{dep_str}")
            
            return tasks
            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            _safe_print(f"[TaskDecomposer] LLM parse error: {e}")
            return None
    
    def decompose(self, user_input: str) -> List[Task]:
        """
        Decompose user input into a list of tasks.
        
        Strategy (fast to slow):
            1. Heuristic single-task check (instant)
            2. Fast regex split on known connectors (instant)
            3. LLM decomposition with timeout (only if regex can't split)
        
        Returns:
            List of Task objects. For chained tasks, depends_on and order are set.
            For single-task inputs, returns exactly 1 task.
        """
        # Fast path 1: single-task inputs (instant)
        if self._quick_single_task_check(user_input):
            _safe_print(f"[TaskDecomposer] Single task detected (heuristic)")
            return [Task(id=1, text=user_input, task_type=TaskType.UNKNOWN)]
        
        # Fast path 2: try regex-based split first (instant, no LLM)
        regex_result = self._fast_regex_decompose(user_input)
        if regex_result:
            # Regex found a clean split â€” use it immediately, no LLM needed
            _safe_print(f"[TaskDecomposer] Using fast regex decomposition ({len(regex_result)} tasks)")
            return regex_result
        
        # Slow path: regex couldn't split, try LLM with timeout
        _safe_print(f"[TaskDecomposer] No regex split possible, trying LLM decomposition...")
        
        if self.is_available():
            llm_result = self._llm_decompose_with_timeout(user_input)
            if llm_result:
                return llm_result
        
        # Nothing worked â€” treat as single task
        _safe_print(f"[TaskDecomposer] No decomposition possible, treating as single task")
        return [Task(id=1, text=user_input, task_type=TaskType.UNKNOWN)]


# ============================================================================
# TASK QUEUE -- Thread-safe queue for pending tasks
# ============================================================================

class TaskQueue:
    """
    Thread-safe task queue with status tracking.
    Supports enqueueing, dequeueing, and monitoring task progress.
    """
    
    def __init__(self):
        self._queue: queue.Queue[Task] = queue.Queue()
        self._all_tasks: List[Task] = []
        self._lock = threading.Lock()
    
    def enqueue(self, task: Task):
        """Add a task to the queue."""
        with self._lock:
            self._all_tasks.append(task)
        self._queue.put(task)
        _safe_print(f"[TaskQueue] Enqueued task {task.id}: {task.text[:50]}...")
    
    def enqueue_all(self, tasks: List[Task]):
        """Add multiple tasks to the queue."""
        for task in tasks:
            self.enqueue(task)
    
    def dequeue(self, timeout: float = None) -> Optional[Task]:
        """Get next task from queue. Returns None if empty/timeout."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def is_empty(self) -> bool:
        return self._queue.empty()
    
    @property
    def total_tasks(self) -> int:
        with self._lock:
            return len(self._all_tasks)
    
    @property
    def completed_count(self) -> int:
        with self._lock:
            return sum(1 for t in self._all_tasks 
                      if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED))
    
    @property
    def pending_count(self) -> int:
        with self._lock:
            return sum(1 for t in self._all_tasks if t.status == TaskStatus.PENDING)
    
    def all_done(self) -> bool:
        """Check if all tasks are completed or failed."""
        with self._lock:
            return all(t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
                      for t in self._all_tasks)
    
    def get_results(self) -> List[Dict[str, Any]]:
        """Get results from all completed tasks, ordered by task ID."""
        with self._lock:
            results = []
            for task in sorted(self._all_tasks, key=lambda t: t.id):
                results.append({
                    "task_id": task.id,
                    "text": task.text,
                    "type": task.task_type.value,
                    "hint": task.hint,
                    "status": task.status.value,
                    "result": task.result,
                    "error": task.error,
                    "duration": task.duration,
                })
            return results
    
    def clear(self):
        """Clear the queue and all tasks."""
        with self._lock:
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
            self._all_tasks.clear()

    def cancel_all_tasks(self):
        """Cancel all pending or in-progress tasks."""
        with self._lock:
            for task in self._all_tasks:
                if task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS):
                    task.mark_failed("Cancelled by stop command")
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break



# ============================================================================
# TASK EXECUTOR -- Orchestrates concurrent AND chained task execution
# ============================================================================

class TaskExecutor:
    """
    Executes tasks from the queue.
    
    Two modes:
    1. PARALLEL -- Independent tasks run concurrently via ThreadPoolExecutor
    2. CHAINED  -- Dependent tasks run sequentially; each task's output is
                   injected into the next task's input as context
    
    Results are collected after ALL tasks complete.
    """
    
    MAX_WORKERS = 4
    TASK_TIMEOUT = 90  # seconds
    
    def __init__(self, execute_fn: Callable[[str], Dict[str, Any]]):
        """
        Args:
            execute_fn: Function that executes a single task string and returns result dict.
        """
        self.execute_fn = execute_fn
        self._decomposer = TaskDecomposer()
        self._current_total = 0
        self._current_completed = 0

    # ---- CHAINED CONTEXT REWRITING ----
    # When a chained task depends on a previous task's output, the text needs
    # to be rewritten so that the downstream handler (e.g., WhatsApp agent)
    # can properly parse it.

    # Patterns to detect "send/share to <contact>" in a task
    _SEND_TO_PATTERNS = [
        # "send them to CONTACT_NAME_TWO on whatsapp"
        re.compile(r'send\s+(?:it|them|these|those|the\s+\w+)?\s*(?:to|on)\s+(\w+)', re.IGNORECASE),
        # "share (those results|it|them) with CONTACT_NAME_TWO" â€” flexible object matching
        re.compile(r'share\s+(?:\w+\s+)*?(?:with|to)\s+(\w+)', re.IGNORECASE),
        # "whatsapp them to CONTACT_NAME_TWO" / "message CONTACT_NAME_TWO"
        re.compile(r'(?:whatsapp|message|text)\s+(?:it|them|these|those|the\s+\w+)?\s*(?:to\s+)?(\w+)', re.IGNORECASE),
        # "forward (these|it) to CONTACT_NAME_TWO"
        re.compile(r'forward\s+(?:\w+\s+)*?to\s+(\w+)', re.IGNORECASE),
        # "send to CONTACT_NAME_TWO"
        re.compile(r'send\s+to\s+(\w+)', re.IGNORECASE),
    ]

    # Words that should NOT be treated as contact names
    _NOT_CONTACTS = {
        "whatsapp", "telegram", "email", "gmail", "obsidian", "discord",
        "slack", "message", "text", "it", "them", "these", "those",
        "the", "a", "an", "and", "in", "on", "via", "through",
    }

    def _extract_contact_from_task(self, task_text: str) -> str:
        """Extract the contact name from a send/share task text."""
        for pattern in self._SEND_TO_PATTERNS:
            match = pattern.search(task_text)
            if match:
                contact = match.group(1).strip().lower()
                if contact not in self._NOT_CONTACTS and len(contact) >= 2:
                    return match.group(1).strip()
        return ""

    def _is_messaging_task(self, task_text: str) -> bool:
        """Check if a task is about sending/sharing via a messaging platform."""
        lower = task_text.lower()
        send_signals = ["send ", "share ", "forward ", "whatsapp", "message ", "text "]
        platform_signals = ["whatsapp", "telegram", "email", "gmail"]
        has_send = any(s in lower for s in send_signals)
        has_platform = any(s in lower for s in platform_signals)
        return has_send or has_platform

    def _build_chained_task_text(self, task: Task, context: str) -> str:
        """
        Build the task text for a chained task that has context from a previous step.
        
        For messaging tasks (WhatsApp, email, etc.): rewrites into a proper
        'send message to <contact> saying <content>' format so the WhatsApp
        agent can parse it correctly.
        
        For other tasks: appends context as before.
        
        All output is sanitized to ASCII-safe text (no emojis) to prevent
        cp1252 encoding crashes on Windows.
        """
        if not context:
            return task.text

        if self._is_messaging_task(task.text):
            contact = self._extract_contact_from_task(task.text)
            if contact:
                # Check if context looks like GitHub results and reformat FIRST
                # (before sanitization strips the structure)
                ctx_lower = context.lower()
                if 'github' in ctx_lower and ('repositor' in ctx_lower or 'repo' in ctx_lower):
                    msg_content = _format_github_for_whatsapp(context)
                else:
                    msg_content = context.strip()

                # NOW sanitize (after formatting preserved the structure)
                msg_content = _sanitize_for_chain(msg_content)

                # Truncate for messaging (WhatsApp practical limit)
                if len(msg_content) > 2000:
                    msg_content = msg_content[:2000] + "..."

                # Collapse multiline into single line for regex parsers
                # (WhatsApp automator will re-expand when pasting)
                msg_content = msg_content.replace('\n', ' | ')

                rewritten = f"whatsapp {contact} saying {msg_content}"
                _safe_print(f"[TaskExecutor] Rewrote chained task: send to {contact} ({len(msg_content)} chars)")
                return rewritten

        # Non-messaging task or couldn't extract contact -- append context normally
        sanitized_context = _sanitize_for_chain(context)
        return f"{task.text}\n\nContext from previous step:\n{sanitized_context}"
    
    def _execute_single_task(self, task: Task, context: str = "") -> Task:
        """
        Execute a single task and update its status.
        
        Args:
            task: The task to execute
            context: Optional context from a previous chained task's output
        """
        try:
            from SpeechToText.speech_buffer import get_speech_buffer
            buffer = get_speech_buffer()
        except ImportError:
            buffer = None
            
        if buffer and buffer.is_cancelled():
            _safe_print(f"[TaskExecutor] Task {task.id} aborted (cancellation flag set)")
            task.mark_failed("Cancelled by user")
            return task

        task.mark_started()
        _safe_print(f"\n[TaskExecutor] >> Starting task {task.id}: {task.text[:60]}...")
        
        if context:
            _safe_print(f"[TaskExecutor]    (with context from previous task)")
        
        # Update shared state for UI
        try:
            from shared_state import set_task_queue_status
            set_task_queue_status(active=True, total=self._current_total,
                                completed=self._current_completed)
        except Exception:
            pass
        
        try:
            # If there's context from a chained task, inject it into the task text
            task_text = task.text
            if context:
                task_text = self._build_chained_task_text(task, context)
            
            result = self.execute_fn(task_text)
            
            # Normalize result to dict
            if result is None:
                result = {"status": "success", "response": "Done."}
            elif isinstance(result, bool):
                result = {"status": "success" if result else "error", 
                         "response": "Done." if result else "Failed."}
            elif isinstance(result, str):
                result = {"status": "success", "response": result}
            elif not isinstance(result, dict):
                result = {"status": "success", "response": str(result)}
            
            task.mark_completed(result)
            _safe_print(f"[TaskExecutor] [OK] Task {task.id} completed in {task.duration:.1f}s")
            
            self._current_completed += 1
            
        except Exception as e:
            error_msg = str(e).encode('ascii', errors='replace').decode('ascii')
            _safe_print(f"[TaskExecutor] [FAIL] Task {task.id} failed: {error_msg}")
            traceback.print_exc()
            task.mark_failed(error_msg)
        
        return task
    
    def _has_chained_tasks(self, tasks: List[Task]) -> bool:
        """Check if any tasks have dependencies (chained execution needed)."""
        return any(t.is_chained for t in tasks)
    
    def _extract_task_output(self, task: Task) -> str:
        """Extract the meaningful output from a completed task to pass to the next.
        
        NOTE: Output is returned RAW (may contain Unicode emojis, etc.).
        Sanitization happens later in _build_chained_task_text() where we know
        the downstream context (messaging vs. other) and can format appropriately.
        """
        if not task.result:
            return ""
        
        result = task.result
        if isinstance(result, dict):
            # Priority: response > data > result > message
            output = result.get("response", "")
            if not output:
                output = str(result.get("data", ""))
            if not output:
                output = str(result.get("result", ""))
            if not output:
                output = str(result.get("message", ""))
            
            # Trim if too long (keep generous limit for chain context)
            if output and len(output) > 3000:
                output = output[:3000] + "..."
            
            return output
        
        return str(result)[:3000]
    
    def _execute_chained(self, tasks: List[Task]) -> List[Task]:
        """
        Execute tasks in dependency order (chained workflow).
        Each task's output is passed as context to the next task that depends on it.
        """
        # Sort by order (tasks with order > 0 go in sequence)
        ordered = sorted(tasks, key=lambda t: t.order if t.order > 0 else 0)
        
        # Separate into: independent (order=0, no depends) and chained (order>0 or depends_on)
        independent = [t for t in ordered if t.order == 0 and not t.is_chained]
        chained = [t for t in ordered if t.order > 0 or t.is_chained]
        chained.sort(key=lambda t: t.order)
        
        # Execute independent tasks in parallel first (if any)
        if independent:
            _safe_print(f"[TaskExecutor] Running {len(independent)} independent task(s) in parallel...")
            with ThreadPoolExecutor(max_workers=min(self.MAX_WORKERS, len(independent))) as pool:
                futures = {pool.submit(self._execute_single_task, t): t for t in independent}
                for future in as_completed(futures, timeout=self.TASK_TIMEOUT):
                    try:
                        future.result()
                    except Exception as e:
                        task = futures[future]
                        task.mark_failed(str(e))
        
        # Execute chained tasks sequentially, passing context forward
        if chained:
            _safe_print(f"[TaskExecutor] Running {len(chained)} chained task(s) sequentially...")
            task_outputs: Dict[int, str] = {}
            
            for task in chained:
                context = ""
                
                # Get context from the task this depends on
                if task.depends_on:
                    # Check by order number first, then by task ID
                    context = task_outputs.get(task.depends_on, "")
                
                # Execute with context
                self._execute_single_task(task, context=context)
                
                # Store output for downstream tasks (indexed by both order and ID)
                if task.status == TaskStatus.COMPLETED:
                    output = self._extract_task_output(task)
                    if task.order > 0:
                        task_outputs[task.order] = output
                    task_outputs[task.id] = output
                else:
                    _safe_print(f"[TaskExecutor] Chain broken at task {task.id}, skipping downstream")
                    # Mark remaining dependent tasks as failed
                    for remaining in chained:
                        if remaining.status == TaskStatus.PENDING:
                            if remaining.depends_on == task.order or remaining.depends_on == task.id:
                                remaining.mark_failed(f"Upstream task {task.id} failed")
        
        return tasks
    
    def process_input(self, user_input: str) -> Dict[str, Any]:
        """
        Main entry point: decompose -> queue -> execute -> aggregate.
        
        Handles both independent (parallel) and chained (sequential) workflows.
        """
        # Step 1: Decompose
        tasks = self._decomposer.decompose(user_input)
        
        # Step 2: Single task -- execute directly (no queue overhead)
        if len(tasks) == 1:
            _safe_print(f"[TaskExecutor] Single task, executing directly")
            self._execute_single_task(tasks[0])
            return tasks[0].result or {"status": "error", "error": tasks[0].error}
        
        # Step 3: Multiple tasks -- determine execution strategy
        has_chain = self._has_chained_tasks(tasks)
        mode = "CHAINED" if has_chain else "PARALLEL"
        
        _safe_print(f"\n{'='*60}")
        _safe_print(f"[TaskExecutor] Processing {len(tasks)} tasks ({mode})")
        _safe_print(f"{'='*60}")
        
        self._current_total = len(tasks)
        self._current_completed = 0
        
        # Notify user
        try:
            from shared_state import ui_system_message, set_task_queue_status
            mode_desc = "in sequence" if has_chain else "simultaneously"
            ui_system_message(f"Processing {len(tasks)} tasks {mode_desc}...")
            set_task_queue_status(active=True, total=len(tasks), completed=0)
        except Exception:
            pass
        
        start_time = time.time()
        
        if has_chain:
            # CHAINED execution (sequential with context passing)
            tasks = self._execute_chained(tasks)
        else:
            # PARALLEL execution
            task_queue = TaskQueue()
            task_queue.enqueue_all(tasks)
            
            with ThreadPoolExecutor(max_workers=min(self.MAX_WORKERS, len(tasks))) as pool:
                futures: Dict[Future, Task] = {}
                
                while not task_queue.is_empty():
                    task = task_queue.dequeue()
                    if task:
                        future = pool.submit(self._execute_single_task, task)
                        futures[future] = task
                
                for future in as_completed(futures, timeout=self.TASK_TIMEOUT):
                    task = futures[future]
                    try:
                        future.result()
                    except Exception as e:
                        _safe_print(f"[TaskExecutor] Task {task.id} exception: {e}")
                        task.mark_failed(str(e))
        
        total_time = time.time() - start_time
        
        # Step 4: Collect results
        results = []
        for task in sorted(tasks, key=lambda t: t.id):
            results.append({
                "task_id": task.id,
                "text": task.text,
                "type": task.task_type.value,
                "hint": task.hint,
                "status": task.status.value,
                "result": task.result,
                "error": task.error,
                "duration": task.duration,
            })
        
        _safe_print(f"\n{'='*60}")
        _safe_print(f"[TaskExecutor] All {len(tasks)} tasks completed in {total_time:.1f}s")
        for r in results:
            status_icon = "[OK]" if r["status"] == "completed" else "[FAIL]"
            _safe_print(f"  {status_icon} Task {r['task_id']}: {r['text'][:50]}... ({r['duration']:.1f}s)")
        _safe_print(f"{'='*60}\n")
        
        # Clear queue status
        try:
            from shared_state import set_task_queue_status
            set_task_queue_status(active=False, total=len(tasks), completed=len(tasks))
        except Exception:
            pass
        
        # Step 5: Aggregate and deliver
        aggregated = self._aggregate_results(results, total_time)
        self._deliver_summary(aggregated)
        
        return aggregated
    
    def _aggregate_results(self, results: List[Dict], total_time: float) -> Dict[str, Any]:
        """Aggregate individual task results into a unified response."""
        
        successful = [r for r in results if r["status"] == "completed"]
        failed = [r for r in results if r["status"] == "failed"]
        
        summary_parts = []
        
        for r in results:
            task_result = r.get("result", {})
            if isinstance(task_result, dict):
                response = task_result.get("response", task_result.get("message", ""))
            else:
                response = str(task_result) if task_result else ""
            
            if r["status"] == "completed" and response:
                summary_parts.append(response)
            elif r["status"] == "failed":
                summary_parts.append(f"Sorry, I couldn't complete: {r['text'][:40]}")
        
        if len(summary_parts) == 1:
            combined_response = summary_parts[0]
        elif summary_parts:
            combined_response = " Also, ".join(summary_parts)
        else:
            combined_response = "All tasks have been processed."
        
        return {
            "status": "success" if not failed else ("partial" if successful else "error"),
            "multi_task": True,
            "task_count": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "total_time": total_time,
            "response": combined_response,
            "results": results,
        }
    
    def _deliver_summary(self, aggregated: Dict[str, Any]):
        """Deliver the aggregated summary via TTS and UI."""
        response = aggregated.get("response", "")
        
        if not response:
            return
        
        try:
            from shared_state import ui_jarvis_message
            from TextToSpeech.Fast_DF_TTS import speak
            
            task_count = aggregated.get("task_count", 1)
            
            if task_count > 1:
                successful = aggregated.get("successful", 0)
                failed = aggregated.get("failed", 0)
                
                if failed == 0:
                    summary_speech = f"All {successful} tasks completed successfully."
                else:
                    summary_speech = f"{successful} of {task_count} tasks completed. {failed} had issues."
                
                ui_jarvis_message(summary_speech)
                threading.Thread(target=speak, args=(summary_speech,), daemon=True).start()
                
        except Exception as e:
            _safe_print(f"[TaskExecutor] Summary delivery error: {e}")


# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

_decomposer: Optional[TaskDecomposer] = None
_executor: Optional[TaskExecutor] = None


def get_decomposer() -> TaskDecomposer:
    """Get the global TaskDecomposer instance."""
    global _decomposer
    if _decomposer is None:
        _decomposer = TaskDecomposer()
    return _decomposer


def get_executor(execute_fn: Callable = None) -> TaskExecutor:
    """Get the global TaskExecutor instance."""
    global _executor
    if _executor is None:
        if execute_fn is None:
            raise ValueError("execute_fn must be provided on first call")
        _executor = TaskExecutor(execute_fn)
    return _executor


def process_multi_task(user_input: str, execute_fn: Callable) -> Dict[str, Any]:
    """
    Convenience function: decompose and execute a potentially multi-task input.
    
    Handles independent (parallel) and chained (sequential) workflows.
    Single-task inputs flow through with zero overhead.
    """
    executor = TaskExecutor(execute_fn)
    return executor.process_input(user_input)

