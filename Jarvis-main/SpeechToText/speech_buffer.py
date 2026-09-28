"""
Smart Speech Buffer & Interrupt Control for JARVIS Voice Assistant.

Commands execute INSTANTLY after wake word detection (no pre-execution
buffering delay).  During execution a 4-second interrupt window monitors
the microphone.  If new speech is detected, the current execution is
cancelled and the merged text is re-executed immediately.

State Machine:
  LISTENING  → wake word + command          → EXECUTING  (instant)
  EXECUTING  → 4 s silence                  → keep running / wait for done
  EXECUTING  → new speech                   → cancel + re-execute (merged text)
  EXECUTING  → "Jarvis stop"                → LISTENING  (cancel everything)
  EXECUTING  → execution completes normally → LISTENING

Priority:
  1. "Jarvis stop"  (highest — force-stops everything)
  2. New speech during execution  (cancel + merge + re-execute)
  3. Normal execution completion
"""

import os
import sys
import threading
import time
from enum import Enum
from typing import Optional
from difflib import SequenceMatcher

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from colorama import Fore


# ============================================================================
# CONSTANTS
# ============================================================================

class BufferState(Enum):
    LISTENING = "listening"
    EXECUTING = "executing"


# Stop command variations (fuzzy-matched)
STOP_PHRASES = [
    "stop",
    "stop all",
    "stop tasks",
    "stop work",
    "stop speaking",
    "stop talking",
    "stop now",
    "cancel",
    "cancel all",
    "abort",
    "terminate",
    "halt",
    "shut up",
    "be quiet",
    "quiet",
    "hush",
    "pause",
    "jarvis stop",
    "jarves stop",
    "jarvys stop",
    "charvis stop",
    "jarvis halt",
    "jarvis cancel",
    "jarvis abort",
    "jarvis shut up",
]


STOP_SIMILARITY_THRESHOLD = 0.70

# How long to listen for interrupt speech during execution (seconds)
INTERRUPT_LISTEN_TIMEOUT = 4.0

# Sentinel returned by _listen_raw to distinguish silence timeout from
# unintelligible audio (both return no text, but have different meanings)
SILENCE_TIMEOUT = "__SILENCE_TIMEOUT__"


# ============================================================================
# SPEECH BUFFER
# ============================================================================

class SpeechBuffer:
    """
    Thread-safe speech buffer with two-state machine.

    Initial commands execute immediately — no delay.
    During execution, a 4-second microphone window checks for
    new speech.  If detected, the current execution is cancelled,
    the texts are merged, and the merged command is re-executed
    through the ``consume_reexec()`` handshake with ``check_inputs()``.
    """

    def __init__(self):
        self._state = BufferState.LISTENING
        self._accumulated_text = ""
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._execution_done = threading.Event()
        # Holds merged text for re-execution after an interrupt
        self._reexecute_text = ""

    # ── Properties ──

    @property
    def state(self) -> BufferState:
        with self._lock:
            return self._state

    @property
    def accumulated_text(self) -> str:
        with self._lock:
            return self._accumulated_text

    @property
    def cancel_event(self) -> threading.Event:
        return self._cancel_event

    @property
    def execution_done(self) -> threading.Event:
        return self._execution_done

    # ── State Transitions ──

    def start_immediate_execution(self, text: str):
        """
        Execute a command instantly — no buffering delay.
        LISTENING → EXECUTING.
        """
        with self._lock:
            self._accumulated_text = text.strip()
            self._state = BufferState.EXECUTING
            self._cancel_event.clear()
            self._execution_done.clear()
            self._reexecute_text = ""
        print(Fore.GREEN + f"[Buffer] Execute now: '{text.strip()}'")

    def interrupt_execution(self, new_text: str):
        """
        New speech detected during execution.
        Cancels the running command, merges texts, and queues
        the merged text for immediate re-execution.
        State stays EXECUTING (check_inputs + listen loop cooperate).
        """
        with self._lock:
            self._cancel_event.set()
            new_text = new_text.strip()
            if self._accumulated_text:
                merged = self._accumulated_text + " " + new_text
            else:
                merged = new_text
            self._accumulated_text = merged
            self._reexecute_text = merged
            self._execution_done.clear()

        # Stop TTS immediately
        try:
            from shared_state import request_tts_stop
            request_tts_stop()
        except Exception:
            pass

        print(Fore.YELLOW + f"[Buffer] Interrupted → will re-execute: '{merged}'")

    def consume_reexec(self) -> str:
        """
        Called by ``check_inputs()`` after ``Automation_Brain`` returns.
        Returns the pending re-execution text (if any) and resets the
        cancel flag so the next execution proceeds normally.
        Returns empty string when nothing is pending.
        """
        with self._lock:
            text = self._reexecute_text
            self._reexecute_text = ""
            if text:
                self._cancel_event.clear()
                self._execution_done.clear()
            return text

    def force_stop(self):
        """
        Force stop everything (highest priority).
        ANY STATE → LISTENING.
        Triggered by "Friday stop" command.
        """
        with self._lock:
            self._cancel_event.set()
            self._accumulated_text = ""
            self._reexecute_text = ""
            self._state = BufferState.LISTENING
            self._execution_done.set()

        # Stop TTS
        try:
            from shared_state import request_tts_stop
            request_tts_stop()
        except Exception:
            pass

        # Kill any active project runner cmd windows
        try:
            import subprocess
            subprocess.run('taskkill /F /FI "WINDOWTITLE eq JARVIS_RUNNER*"', shell=True, capture_output=True)
        except Exception:
            pass

        print(Fore.RED + "[Buffer] FORCE STOP — returned to listening")

    def try_complete_execution(self) -> bool:
        """
        Mark execution as normally complete.
        EXECUTING → LISTENING.
        Returns True if the transition happened (state was still EXECUTING
        and no re-execution is pending).
        Returns False if state already changed (interrupted / force-stopped)
        or a re-execution is queued.
        """
        with self._lock:
            if self._state == BufferState.EXECUTING and not self._reexecute_text:
                self._accumulated_text = ""
                self._state = BufferState.LISTENING
                self._execution_done.set()
                return True
            return False

    def is_cancelled(self) -> bool:
        """Check if cancellation was requested."""
        return self._cancel_event.is_set()

    def reset_cancel(self):
        """Reset cancellation flag to allow new tasks to execute cleanly."""
        with self._lock:
            self._cancel_event.clear()
            self._reexecute_text = ""


    # ── Stop Command Detection ──

    @staticmethod
    def is_stop_command(text: str) -> bool:
        """
        Check if text is an explicit 'stop' or variant command.
        Prevents false positives on full sentences like 'read the important points from the pdf'.
        """
        if not text:
            return False
        text_lower = text.lower().strip()
        words = text_lower.split()
        if not words:
            return False

        # Single word stop check
        if len(words) == 1:
            return words[0] in ["stop", "cancel", "abort", "halt", "quiet", "hush", "pause", "terminate"]

        # Exact multi-word stop phrases (e.g. "jarvis stop", "stop all", "shut up", "be quiet", "stop speaking")
        explicit_stop_phrases = [
            "stop all", "stop tasks", "stop work", "stop speaking", "stop talking", "stop now",
            "cancel all", "shut up", "be quiet", "jarvis stop", "jarves stop", "jarvys stop",
            "charvis stop", "jarvis halt", "jarvis cancel", "jarvis abort", "jarvis shut up",
            "stop current task", "stop operation"
        ]

        if any(phrase == text_lower for phrase in explicit_stop_phrases):
            return True

        # For short inputs (<= 4 words), check if it starts with an explicit stop phrase
        if len(words) <= 4:
            for phrase in explicit_stop_phrases:
                if text_lower.startswith(phrase):
                    return True

        # Fuzzy match on short prefix for 2-3 word inputs only
        if len(words) in (2, 3):
            for phrase in explicit_stop_phrases:
                score = SequenceMatcher(None, text_lower, phrase).ratio()
                if score >= STOP_SIMILARITY_THRESHOLD:
                    return True

        return False




# ============================================================================
# SINGLETON ACCESS
# ============================================================================

_speech_buffer: Optional[SpeechBuffer] = None
_singleton_lock = threading.Lock()


def get_speech_buffer() -> SpeechBuffer:
    """Get the global SpeechBuffer singleton."""
    global _speech_buffer
    with _singleton_lock:
        if _speech_buffer is None:
            _speech_buffer = SpeechBuffer()
        return _speech_buffer
