"""
Shared state module for coordinating between TTS and Speech Recognition.
Prevents the microphone from hearing its own TTS output.
Also tracks listening state for wake word detection.
"""
import threading

# Flag to indicate if TTS is currently speaking
is_speaking = False

# Flag to indicate if actively listening for command (after wake word)
is_listening_for_command = False

# Pending command being processed (for interruption handling)
pending_command = ""

# Current JARVIS state for UI
jarvis_state = "idle"  # idle, listening, processing, speaking

# Chat messages history
chat_history = []

_lock = threading.Lock()


def set_speaking(state: bool):
    """Set the speaking state"""
    global is_speaking
    with _lock:
        is_speaking = state
    # Update UI state
    if state:
        set_jarvis_state("speaking")


def get_speaking() -> bool:
    """Check if TTS is currently speaking"""
    with _lock:
        return is_speaking


def set_listening(state: bool):
    """Set the listening for command state"""
    global is_listening_for_command
    with _lock:
        is_listening_for_command = state
    # Update UI state
    if state:
        set_jarvis_state("listening")


def get_listening() -> bool:
    """Check if actively listening for command"""
    with _lock:
        return is_listening_for_command


def set_pending_command(command: str):
    """Set the pending command being processed"""
    global pending_command
    with _lock:
        pending_command = command


def get_pending_command() -> str:
    """Get the pending command"""
    with _lock:
        return pending_command


def clear_pending_command():
    """Clear the pending command"""
    global pending_command
    with _lock:
        pending_command = ""


# ============================================================================
# JARVIS UI INTEGRATION
# ============================================================================

def set_jarvis_state(state: str):
    """Set JARVIS state and update UI if available."""
    global jarvis_state
    with _lock:
        jarvis_state = state
    try:
        from UI.jarvis_ui import set_state
        set_state(state)
    except:
        pass  # UI not available


def get_jarvis_state() -> str:
    """Get current JARVIS state."""
    with _lock:
        return jarvis_state


def ui_message(role: str, content: str):
    """Send a message to the JARVIS UI."""
    global chat_history
    import time
    with _lock:
        # Prevent duplicate consecutive jarvis messages to avoid double-printing bugs
        if role == "jarvis" and chat_history and chat_history[-1]["role"] == "jarvis" and chat_history[-1]["content"].strip() == content.strip():
            return
            
        chat_history.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
        if len(chat_history) > 50:
            chat_history.pop(0)
    try:
        from UI.jarvis_ui import add_message
        add_message(role, content)
    except:
        pass  # UI not available


def get_chat_history() -> list:
    """Get the current chat history."""
    with _lock:
        return list(chat_history)


def ui_user_message(content: str):
    """Send a user message to UI."""
    ui_message("user", content)


def ui_voice_user_message(content: str):
    """Send a user voice message to UI."""
    ui_message("user_voice", content)



def ui_jarvis_message(content: str):
    """Send a JARVIS response to UI."""
    ui_message("jarvis", content)


def ui_tool_message(content: str):
    """Send a tool result to UI."""
    ui_message("tool", content)


def ui_system_message(content: str):
    """Send a system message to UI."""
    ui_message("system", content)


# ============================================================================
# VOICE POPUP INTEGRATION
# ============================================================================

def show_voice_popup():
    """Show the compact voice activation popup."""
    try:
        from UI.voice_popup import show_voice_popup as _show
        _show()
    except:
        pass


def hide_voice_popup():
    """Hide the voice popup."""
    try:
        from UI.voice_popup import hide_voice_popup as _hide
        _hide()
    except:
        pass


def update_voice_text(text: str):
    """Update the text shown in voice popup."""
    try:
        from UI.voice_popup import update_voice_text as _update
        _update(text)
    except:
        pass


def set_voice_popup_status(status: str):
    """Set voice popup status text."""
    try:
        from UI.voice_popup import set_popup_status as _set
        _set(status)
    except:
        pass


def show_idle_voice_popup():
    """Show popup in idle state - stopped animation, 'Say Friday' text."""
    try:
        from UI.voice_popup import show_idle_popup as _idle
        _idle()
    except:
        pass


def show_results_in_popup(title: str, content: str, auto_hide_seconds: int = 20):
    """Display results in the expandable voice popup panel."""
    try:
        from UI.voice_popup import show_results_in_popup as _show_results
        _show_results(title, content, auto_hide_seconds)
    except:
        pass


def collapse_popup_results():
    """Collapse the voice popup results panel."""
    try:
        from UI.voice_popup import collapse_popup_results as _collapse
        _collapse()
    except:
        pass


# ============================================================================
# MULTI-TASK QUEUE STATE
# ============================================================================

# ============================================================================
# WAKE WORD AUDIO DUCKING STATE
# ============================================================================

# When True, other apps are ducked (quiet) — set on wake word, cleared after TTS
_wake_ducking_active = False


def set_wake_ducking(active: bool):
    """Set whether audio ducking is active (wake word detected → other apps quiet)."""
    global _wake_ducking_active
    with _lock:
        _wake_ducking_active = active


def get_wake_ducking() -> bool:
    """Check if audio ducking is currently active."""
    with _lock:
        return _wake_ducking_active


# Track active multi-task processing
_task_queue_active = False
_task_queue_total = 0
_task_queue_completed = 0

def set_task_queue_status(active: bool, total: int = 0, completed: int = 0):
    """Update multi-task queue status for UI display."""
    global _task_queue_active, _task_queue_total, _task_queue_completed
    with _lock:
        _task_queue_active = active
        _task_queue_total = total
        _task_queue_completed = completed
    
    if active and total > 1:
        ui_system_message(f"Processing task {completed + 1} of {total}...")


def get_task_queue_status() -> dict:
    """Get current multi-task queue status."""
    with _lock:
        return {
            "active": _task_queue_active,
            "total": _task_queue_total,
            "completed": _task_queue_completed,
        }


def is_multi_task_active() -> bool:
    """Check if multi-task processing is currently active."""
    with _lock:
        return _task_queue_active


# ============================================================================
# TTS INTERRUPT CONTROL (for "Friday stop" / speech interruption)
# ============================================================================

_tts_stop_requested = False


def request_tts_stop():
    """Signal that TTS should stop immediately (called on 'Friday stop' or interrupt)."""
    global _tts_stop_requested
    with _lock:
        _tts_stop_requested = True


def clear_tts_stop():
    """Clear the TTS stop flag (called after TTS acknowledges the stop)."""
    global _tts_stop_requested
    with _lock:
        _tts_stop_requested = False


def is_tts_stop_requested() -> bool:
    """Check if TTS stop has been requested."""
    with _lock:
        return _tts_stop_requested


def stop_all_operations() -> str:
    """
    Terminates all active TTS speech, running tasks, task queues, and resets JARVIS state to IDLE.
    """
    import pygame

    print("\n[JARVIS] 🛑 EMERGENCY STOP: Halting speech, tasks, and queued operations...")

    # 1. Flag TTS stop
    request_tts_stop()
    set_speaking(False)

    # 2. Stop Pygame Audio playback immediately
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.stop()
    except Exception as e:
        print(f"[STOP] Pygame stop exception: {e}")

    # 3. Cancel SpeechBuffer execution flag (force stops listening/executing thread)
    try:
        from SpeechToText.speech_buffer import get_speech_buffer
        buffer = get_speech_buffer()
        buffer.force_stop()
    except Exception as e:
        print(f"[STOP] SpeechBuffer stop exception: {e}")

    # 4. Clear multi-task queue state
    try:
        set_task_queue_status(active=False, total=0, completed=0)
    except Exception:
        pass

    # 5. Reset JARVIS state & update UI status log
    set_jarvis_state("idle")
    ui_system_message("🛑 Current task stopped. Ready for your next command, Sir.")

    try:
        from shared_state import show_idle_voice_popup
        show_idle_voice_popup()
    except Exception:
        pass

    return "Current task stopped, Sir. Standing by for your next command."


# ============================================================================
# RESPONSE MEMORY SYSTEM
# ============================================================================

latest_generated_response = None

def set_latest_generated_response(content: str):
    """Store the generated content as the Latest Generated Response in session memory and copy to system clipboard."""
    global latest_generated_response
    if not content:
        return
    # Strip whitespace
    latest_generated_response = content.strip()
    print(f"[ResponseMemory] Stored response length: {len(latest_generated_response)}")
    try:
        import pyperclip
        pyperclip.copy(latest_generated_response)
        print("[ResponseMemory] Copied stored response to clipboard.")
    except Exception as e:
        print(f"[ResponseMemory] Clipboard copy failed: {e}")

def get_latest_generated_response() -> str:
    """Retrieve the Latest Generated Response from session memory."""
    global latest_generated_response
    # Fallback to clipboard if session memory is empty but clipboard has content
    if not latest_generated_response:
        try:
            import pyperclip
            val = pyperclip.paste()
            if val and val.strip():
                return val.strip()
        except Exception:
            pass
    return latest_generated_response



