"""
Telegram Bot for JARVIS — True Input Extension
Telegram = typing instead of speaking. Same brain, same pipeline, same terminal logs.

Flow (identical to voice):
    Telegram Message
      --> Print in terminal (like voice input)
      --> Automation_Brain(text)  (exact same function as voice)
      --> All processing visible in terminal
      --> Capture response
      --> Send response back to Telegram
"""

import sys
import os
import re
import asyncio
import threading
import logging
import queue

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)

# ============================================================================
# CONFIG
# ============================================================================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")

logging.basicConfig(format="[Telegram] %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress the HTTP Request spam from telegram and httpx
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ============================================================================
# THREAD-SAFE RESPONSE CAPTURE
# Uses thread ID to only capture responses from Telegram threads,
# so voice pipeline is never affected.
# ============================================================================
_telegram_threads = set()       # Set of thread IDs that are Telegram handlers
_thread_responses = {}          # {thread_id: [responses]}
_lock = threading.Lock()


def _patched_speak(text):
    """
    Replacement for speak(). 
    - If called from a Telegram thread: capture text, DON'T play audio
    - If called from voice thread: play audio normally (original behavior)
    """
    tid = threading.current_thread().ident
    with _lock:
        is_telegram = tid in _telegram_threads
    
    if is_telegram:
        # Capture for Telegram reply
        with _lock:
            if tid not in _thread_responses:
                _thread_responses[tid] = []
            _thread_responses[tid].append(str(text))
        # Print to terminal (so operator sees it)
        safe = str(text).encode('ascii', errors='replace').decode()
        print(f"[Telegram -> Brain] Response: {safe}")
    else:
        # Voice thread — call original speak
        if _original_speak:
            _original_speak(text)


def _patched_ui_jarvis(text):
    """
    Replacement for ui_jarvis_message().
    Captures response for Telegram threads, passes through for others.
    """
    tid = threading.current_thread().ident
    with _lock:
        is_telegram = tid in _telegram_threads

    if is_telegram:
        with _lock:
            if tid not in _thread_responses:
                _thread_responses[tid] = []
            _thread_responses[tid].append(str(text))

    # Always call original UI (it's fine if UI isn't running)
    if _original_ui_jarvis:
        try:
            _original_ui_jarvis(text)
        except Exception:
            pass


# Store originals
_original_speak = None
_original_ui_jarvis = None
_patched = False


def setup_patches():
    """Monkey-patch speak and ui_jarvis_message ONCE."""
    global _original_speak, _original_ui_jarvis, _patched
    if _patched:
        return
    _patched = True

    try:
        import TextToSpeech.Fast_DF_TTS as tts
        _original_speak = tts.speak
        tts.speak = _patched_speak
        print("[Telegram] Patched speak() for response capture")
    except Exception as e:
        print(f"[Telegram] Could not patch TTS: {e}")

    try:
        import shared_state
        _original_ui_jarvis = shared_state.ui_jarvis_message
        shared_state.ui_jarvis_message = _patched_ui_jarvis
        print("[Telegram] Patched ui_jarvis_message() for response capture")
    except Exception as e:
        print(f"[Telegram] Could not patch shared_state: {e}")


# ============================================================================
# BRAIN EXECUTION — Exact same pipeline as voice input
# ============================================================================
def process_through_brain(user_input: str) -> str:
    """
    Process text through Automation_Brain — IDENTICAL to voice input.
    All processing logs appear in terminal just like voice commands.
    """
    tid = threading.current_thread().ident

    # Register this thread as Telegram
    with _lock:
        _telegram_threads.add(tid)
        _thread_responses[tid] = []

    # === Print to terminal EXACTLY like voice input does ===
    safe_input = user_input.encode('ascii', errors='replace').decode()
    print(f"\n{'='*50}")
    print(f"[Telegram Input] {safe_input}")
    print(f"{'='*50}")

    try:
        # Import and call the EXACT same function as voice
        from Automations.Automation_Brain import Automation_Brain
        Automation_Brain(user_input)
    except Exception as e:
        safe_err = str(e).encode('ascii', errors='replace').decode()
        print(f"[Telegram -> Brain] Error: {safe_err}")
        with _lock:
            _telegram_threads.discard(tid)
        return f"Sorry sir, something went wrong: {str(e)[:150]}"

    # Collect captured responses
    with _lock:
        responses = _thread_responses.pop(tid, [])
        _telegram_threads.discard(tid)

    print(f"[Telegram] Captured {len(responses)} response(s)")

    if responses:
        # Return the last meaningful response
        # (earlier ones might be tool status messages)
        return responses[-1]
    
    return "Done, sir."


# ============================================================================
# TELEGRAM HANDLERS
# ============================================================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Hey {user.first_name}! I'm JARVIS.\n\n"
        "I work exactly like voice — just type instead of speak.\n"
        "Everything I can do via voice, I can do here:\n\n"
        "- Open apps & websites\n"
        "- Play music (Spotify/YouTube)\n"
        "- Send WhatsApp messages\n"
        "- Check weather, battery\n"
        "- Control laptop\n"
        "- Remember facts, schedule\n\n"
        "Just type naturally!"
    )


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        from Brain.Memory.memory_manager import get_memory
        mm = get_memory()
        if not mm.is_available():
            await update.message.reply_text("Memory starting up...")
            return
        all_mem = mm.get_all()
        if not all_mem:
            await update.message.reply_text("No memories yet.")
            return
        text = "What I know:\n"
        cat = ""
        for m in all_mem:
            c = m["category"].upper()
            if c != cat:
                cat = c
                text += f"\n[{c}]\n"
            text += f"  {m['key']}: {m['value']}\n"
        await update.message.reply_text(text[:4000])
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        from Brain.Memory.memory_manager import get_memory
        mm = get_memory()
        today = datetime.now().strftime("%Y-%m-%d")
        events = mm.get_schedule(today)
        if not events:
            await update.message.reply_text("No events today!")
            return
        text = f"Schedule for {datetime.now().strftime('%A, %B %d')}:\n\n"
        for e in events:
            t = e.get("start_time", "")
            if e.get("end_time"):
                t += f" - {e['end_time']}"
            p = f" (with {e['people']})" if e.get("people") else ""
            text += f"  {t}  {e['title']}{p}\n"
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process Telegram message — identical to voice input pipeline."""
    user_input = update.message.text
    user = update.effective_user

    # Show typing indicator
    await update.message.chat.send_action("typing")

    # Process through brain in thread pool (so terminal shows everything)
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None, process_through_brain, user_input)

    # Send response back to Telegram
    if response:
        if len(response) > 4000:
            for i in range(0, len(response), 4000):
                await update.message.reply_text(response[i:i+4000])
        else:
            await update.message.reply_text(response)


async def handle_error(update, context):
    logger.error(f"Error: {context.error}")


# ============================================================================
# MAIN
# ============================================================================
def run_telegram_bot():
    """Start the Telegram bot (blocking)."""
    print("[Telegram] Starting JARVIS Telegram bot...")
    setup_patches()

    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("[Telegram] Bot token not configured. Skipping Telegram bot startup.")
        return

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(handle_error)

    print("[Telegram] Bot ready! (@YOUR_TELEGRAM_BOT_USERNAME)")
    print("[Telegram] Messages will appear in this terminal just like voice input")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


def start_telegram_thread():
    """Start in background thread (called from Jarvis.py)."""
    t = threading.Thread(target=run_telegram_bot, daemon=True, name="TelegramBot")
    t.start()
    print("[Telegram] Bot started in background")
    return t


if __name__ == "__main__":
    run_telegram_bot()
