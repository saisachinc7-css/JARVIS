# ============================================================================
# FIX: Force UTF-8 stdout/stderr BEFORE any other imports touch sys.stdout.
# Prevents cp1252 UnicodeEncodeError on Windows consoles for emojis, Unicode.
# Uses reconfigure() to modify in-place (avoids closing the underlying buffer).
# ============================================================================
import sys
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Mock pywhatkit's connection check to prevent startup hang due to network checks
try:
    import pywhatkit.core.core as pw_core
    pw_core.check_connection = lambda: True
except Exception:
    pass

from Automations.Automation_Brain import Automation_Brain
from Tools.Simple_Automations.battery import battery_Alert
from Tools.Simple_Automations.active_window import start_window_monitor, get_current_context, log_window_change
from SpeechToText.SpeechToText_python import listen
from shared_state import ui_user_message, ui_jarvis_message, ui_system_message, set_jarvis_state, show_idle_voice_popup, ui_voice_user_message
import threading
import time
import atexit
import signal

# Fix Qt DPI scaling issue
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from notification import Alert

# Singleton instance port lock to prevent multiple JARVIS instances from running
_singleton_socket = None

def check_singleton():
    import socket
    global _singleton_socket
    try:
        _singleton_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Bind to a specific local port (20850) to act as a singleton lock
        _singleton_socket.bind(('127.0.0.1', 20850))
    except socket.error:
        print("\n[JARVIS] ⚠️  ERROR: Another instance of JARVIS is already running.")
        print("[JARVIS] Please close the other instance before starting a new one.")
        sys.exit(1)

# Adaptive Volume Control for Friday
def _init_adaptive_volume():
    """Pre-initialize adaptive volume controller at startup."""
    try:
        from Laptop_Controls.adaptive_volume import get_adaptive_volume
        avc = get_adaptive_volume()
        vol = avc.get_system_volume()
        print(f"[JARVIS] Adaptive volume control ready (system vol: {vol}%)")
        return avc
    except Exception as e:
        print(f"[JARVIS] Adaptive volume unavailable: {e}")
        return None

def clear_input():
    """Clear input.txt to reset state"""
    with open("input.txt", "w") as f:
        f.write("")
    print("[JARVIS] input.txt cleared")

def check_inputs():
    """Monitor input.txt for new commands and process them.
    
    Integrates with the Smart Speech Buffer:
    - Executes commands immediately (no buffering delay)
    - After execution, checks for re-execution requests (user spoke during execution)
    - Loops re-execution until no more pending speech
    - "Friday stop" force-cancels at any point
    """
    from SpeechToText.speech_buffer import get_speech_buffer

    buffer = get_speech_buffer()
    last_command = ""
    last_command_time = 0
    DEBOUNCE_SECONDS = 2  # Prevent same command within 2 seconds
    
    while True:

        try:
            with open("input.txt", "r") as file:
                current_command = file.read().strip().lower()
            
            # Only process if there's a non-empty command
            if current_command:
                current_time = time.time()
                
                # Check for duplicate command within debounce window
                if current_command == last_command and (current_time - last_command_time) < DEBOUNCE_SECONDS:
                    print(f"[JARVIS] Skipping duplicate command: {current_command}")
                    # Still clear input.txt
                    with open("input.txt", "w") as f:
                        f.write("")
                    time.sleep(0.3)
                    continue
                
                print(f"[JARVIS] Processing command: {current_command}")
                
                # Send to JARVIS UI
                ui_voice_user_message(current_command)
                set_jarvis_state("processing")

                
                # CLEAR input.txt IMMEDIATELY to prevent re-processing
                with open("input.txt", "w") as f:
                    f.write("")
                
                # Update tracking
                last_command = current_command
                last_command_time = current_time
                
                # Check for stop command vs new command execution
                if buffer.is_stop_command(current_command):
                    from shared_state import stop_all_operations
                    stop_all_operations()
                    continue
                else:
                    # New command -> reset cancellation flag so it executes cleanly
                    buffer.reset_cancel()

                # ── Execute the command ──

                Automation_Brain(current_command)
                
                # ── Re-execution loop ──
                # If the user spoke during execution, consume_reexec()
                # returns the merged text.  Re-execute immediately and
                # keep looping until no more pending speech.
                while True:
                    reexec = buffer.consume_reexec()
                    if not reexec:
                        break
                    print(f"[JARVIS] Re-executing (merged): {reexec}")
                    ui_user_message(reexec)
                    set_jarvis_state("processing")
                    last_command = reexec
                    last_command_time = time.time()
                    Automation_Brain(reexec)
                
                # ── Post-execution ──
                if buffer.try_complete_execution():
                    print("[JARVIS] Command completed. Listening...\n")
                    set_jarvis_state("idle")
                    show_idle_voice_popup()
                else:
                    # Force-stopped or state changed externally
                    print("[JARVIS] Command finished (was stopped)")
                
        except FileNotFoundError:
            pass  # File doesn't exist yet
        except Exception as e:
            print(f"[JARVIS] Error: {e}")
            try:
                buffer.try_complete_execution()
            except Exception:
                pass
            
        time.sleep(0.3)  # Check every 300ms


def start_jarvis_threads():
    """Start JARVIS voice and command processing in background threads."""
    # Clear input.txt on startup
    clear_input()
    
    print("[JARVIS] Starting voice assistant...")
    
    # Initialize adaptive volume control (pre-warm COM interfaces)
    _init_adaptive_volume()

    # Pre-warm all Ollama LLM models into GPU VRAM NOW (background, non-blocking).
    # Without this, the first command after startup stalls for 30-100s while the
    # model loads from disk. With this, models are already hot before you speak.
    try:
        from Brain.model_prewarm import prewarm_models_async
        prewarm_models_async()
        print("[JARVIS] LLM model pre-warming started in background (GPU warming...)")
    except Exception as e:
        print(f"[JARVIS] Model pre-warming skipped: {e}")

    # Start active window monitoring (detects current app/website)
    start_window_monitor(callback=log_window_change, interval=1.0)
    print("[JARVIS] Active window detection enabled")
    
    t1 = threading.Thread(target=listen, daemon=True)
    t2 = threading.Thread(target=check_inputs, daemon=True)
    t3 = threading.Thread(target=battery_Alert, daemon=True)  # Battery monitoring
    t1.start()
    t2.start()
    t3.start()
    
    # Start Telegram bot in background
    try:
        from telegram_bot import start_telegram_thread
        start_telegram_thread()
        print("[JARVIS] Telegram bot started (@JARVIS_PERSONAL_ASSISTANT_bot)")
    except Exception as e:
        print(f"[JARVIS] Telegram bot skipped: {e}")
    
    # Start background reminder trigger checker loop
    try:
        from Brain.reminder_manager import check_reminders_trigger
        def check_reminders_loop():
            from notification import Alert
            from TextToSpeech.Fast_DF_TTS import speak
            import threading
            while True:
                try:
                    triggered = check_reminders_trigger()
                    for r in triggered:
                        print(f"[Reminders] Triggered reminder: {r['text']}")
                        Alert(f"Reminder: {r['text']}")
                        msg = f"Sir, this is a reminder: {r['text']}"
                        try:
                            from shared_state import ui_jarvis_message
                            ui_jarvis_message(msg)
                        except:
                            pass
                        threading.Thread(target=speak, args=(msg,), daemon=True).start()
                except Exception as e:
                    print(f"[Reminders] Error checking triggers: {e}")
                time.sleep(1.0)
        threading.Thread(target=check_reminders_loop, daemon=True, name="JarvisReminderChecker").start()
        print("[JARVIS] Reminder check loop active")
    except Exception as e:
        print(f"[JARVIS] Failed to start reminder loop: {e}")

    return t1, t2, t3


def jarvis():
    # Enforce singleton instance port lock
    check_singleton()
    
    # Register cleanup for normal exit
    atexit.register(clear_input)
    
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n[JARVIS] Shutting down...")
        clear_input()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start Esc global killer switch thread
    try:
        def esc_killer_switch():
            import ctypes
            import time
            user32 = ctypes.windll.user32
            VK_ESCAPE = 0x1B
            print("[JARVIS] Esc global killer switch active. Press Esc to shutdown.")
            while True:
                if user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000:
                    print("\n[JARVIS] Kill switch triggered! Shutting down...")
                    clear_input()
                    os._exit(0)
                time.sleep(0.1)
        threading.Thread(target=esc_killer_switch, daemon=True).start()
    except Exception as e:
        print(f"[JARVIS] Esc killer switch failed to start: {e}")
        
    # Show startup notification
    Alert("JARVIS is ready!")
    
    # Start JARVIS threads first (voice + commands)
    threads = start_jarvis_threads()
    
    # Start local HTTP HUD server and open the browser
    try:
        from UI.hud_server import start_hud_server
        start_hud_server()
    except Exception as e:
        print(f"[JARVIS] Failed to start HUD server: {e}")
        
    # Play premium startup greeting once at startup in background after browser launches
    def play_startup_greeting_delayed():
        time.sleep(2.5)  # Wait for HUD server to launch and browser to open
        try:
            from Brain.startup_greetings import play_startup_greeting
            play_startup_greeting()
        except Exception as e:
            print(f"[JARVIS] Startup greeting error: {e}")
    threading.Thread(target=play_startup_greeting_delayed, daemon=True).start()
    
    # Try to start ONLY the compact voice popup (not the big JARVIS window)
    try:
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:
            from PyQt6.QtWidgets import QApplication
        from UI.voice_popup import create_popup as create_voice_popup, PYQT_AVAILABLE
        
        if PYQT_AVAILABLE:
            print("[Voice Popup] Starting...")
            app = QApplication(sys.argv)
            app.setStyle("Fusion")
            
            # Create ONLY the compact voice popup (hidden initially)
            voice_popup = create_voice_popup(app)
            
            # Store reference for messaging
            import UI.voice_popup as popup_module
            popup_module._voice_popup = voice_popup
            popup_module._app = app
            
            print("[Voice Popup] [OK] Ready (shows on wake word)")
            
            # Run Qt event loop (this blocks until app closes)
            sys.exit(app.exec())
        else:
            print("[JARVIS] PyQt6 not available, running without popup")
            threads[0].join()
            threads[1].join()
            
    except ImportError as e:
        print(f"[JARVIS] Voice popup not available: {e}")
        threads[0].join()
        threads[1].join()
    except Exception as e:
        print(f"[JARVIS] Error starting voice popup: {e}")
        threads[0].join()
        threads[1].join()


if __name__ == "__main__":
    jarvis()





