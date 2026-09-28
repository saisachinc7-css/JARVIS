"""
Speech-to-Text module with Smart Speech Buffer & Interrupt Control.
WAKE WORD ACTIVATED - Say "Friday" to start listening.
Executes commands INSTANTLY after wake word — no buffering delay.
Monitors for 4 seconds during execution; new speech cancels + re-executes.

States:
  LISTENING  - Waiting for "Friday" wake word
  EXECUTING  - Command running, monitoring mic for interrupts (4 s window)

"Friday stop" at any time → force-stops everything.
"""
import speech_recognition as sr
from colorama import init, Fore
import time
import os

# Import TTS and shared state
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared_state import (
    get_speaking, show_voice_popup, hide_voice_popup,
    update_voice_text, set_voice_popup_status, show_idle_voice_popup,
)

# Import wake word detector
from SpeechToText.wake_word_detector import WakeWordDetector

# Import speech buffer
from SpeechToText.speech_buffer import (
    get_speech_buffer, BufferState,
    INTERRUPT_LISTEN_TIMEOUT, SILENCE_TIMEOUT,
)

init(autoreset=True)


# ============================================================================
# RAW SPEECH LISTENER (no wake word required)
# ============================================================================

def _listen_raw(recognizer, timeout=4.0, phrase_time_limit=12.0):
    """
    Listen for any speech without requiring a wake word.

    Returns:
        str:             Transcribed text
        SILENCE_TIMEOUT: No speech started within ``timeout`` seconds
        None:            Heard audio but could not transcribe
    """
    with sr.Microphone() as source:
        try:
            audio = recognizer.listen(
                source,
                timeout=timeout,
                phrase_time_limit=phrase_time_limit,
            )
        except sr.WaitTimeoutError:
            return SILENCE_TIMEOUT

    try:
        text = recognizer.recognize_google(audio).lower().strip()
        return text if text else None
    except sr.UnknownValueError:
        return None
    except sr.RequestError as e:
        print(Fore.RED + f"[STT] API error: {e}")
        return None


# ============================================================================
# MAIN LISTEN LOOP
# ============================================================================

def listen():
    """
    Voice command listener with instant execution and 4-second interrupt
    monitor.

    Flow:
      1. LISTENING   → Wait for "Friday" + command
      2.             → Execute immediately (write to input.txt)
      3. EXECUTING   → Monitor mic for 4 s windows
         - New speech  → cancel current, merge texts, re-execute
         - Friday stop → cancel everything, return to LISTENING
         - Silence     → keep monitoring until execution finishes
    """

    recognizer = sr.Recognizer()

    # Speed-optimized settings (preserved from original)
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = False
    recognizer.pause_threshold = 0.5
    recognizer.phrase_threshold = 0.1
    recognizer.non_speaking_duration = 0.3

    print(Fore.YELLOW + "JARVIS Ready! (Instant Execution mode)")
    print(Fore.CYAN + "Say 'Jarvis' to wake me up...")
    print(Fore.CYAN + "Say 'Jarvis stop' at any time to cancel\n")

    # Quick microphone calibration
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        print(Fore.GREEN + "[OK] Microphone ready\n")

    # Initialize components
    detector = WakeWordDetector(recognizer)
    buffer = get_speech_buffer()

    # Resolve path to input.txt once
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_file = os.path.join(base_dir, "input.txt")

    while True:
        try:
            if get_speaking():
                # Listen specifically for interrupts or wake word calls while speaking
                try:
                    result = _listen_raw(recognizer, timeout=0.6, phrase_time_limit=2.5)
                    if result and result is not SILENCE_TIMEOUT:
                        words = result.lower().split()
                        is_interrupt = False
                        
                        # 1. Pure stop keywords: can be up to 4 words (e.g. "jarvis please stop now")
                        pure_stops = ["stop", "quiet", "shut up", "hold on", "wait", "cancel", "hold"]
                        if any(k in words for k in pure_stops) and len(words) <= 4:
                            is_interrupt = True
                            
                        # 2. Wake word interrupt: must be very short to prevent false echoes (e.g. "jarvis" or "hey jarvis")
                        elif any(k in words for k in ["jarvis", "jarivs"]) and len(words) <= 2:
                            is_interrupt = True
                            
                        if is_interrupt:
                            print(Fore.RED + f"[INTERRUPT] Heard '{result}' while speaking. Stopping operations...")
                            from shared_state import stop_all_operations
                            stop_all_operations()
                            time.sleep(0.4)
                            hide_voice_popup()
                            show_idle_voice_popup()
                except Exception as e:
                    time.sleep(0.1)
                continue

            state = buffer.state

            # ────────────────────────────────────────────────────────
            # STATE 1: LISTENING — wait for wake word
            # ────────────────────────────────────────────────────────
            if state == BufferState.LISTENING:
                command = detector.get_command()

                if not command:
                    continue

                # If TTS is speaking, stop it so we can execute the new command immediately
                if get_speaking():
                    print(Fore.YELLOW + "[INTERRUPT] Stopping TTS to execute command...")
                    from shared_state import stop_all_operations
                    stop_all_operations()
                    time.sleep(0.3)

                # Check for "Friday stop" as the initial command
                if buffer.is_stop_command(command):
                    print(Fore.RED + "[STOP] Stop command detected")
                    buffer.force_stop()
                    hide_voice_popup()
                    show_idle_voice_popup()
                    continue

                # ── INSTANT EXECUTION — no buffering delay ──
                print(Fore.MAGENTA + f"Command: {command}")
                buffer.start_immediate_execution(command)

                with open(input_file, "w") as f:
                    f.write(command)

                update_voice_text(command)
                set_voice_popup_status("Processing...")
                print(Fore.GREEN + "[OK] Command sent for execution")

            # ────────────────────────────────────────────────────────
            # STATE 2: EXECUTING — monitor for interrupts (4 s window)
            # ────────────────────────────────────────────────────────
            elif state == BufferState.EXECUTING:
                # Check if execution already completed
                if buffer.execution_done.is_set():
                    show_idle_voice_popup()
                    continue

                # Listen for interruptions (4 s timeout)
                result = _listen_raw(
                    recognizer,
                    timeout=INTERRUPT_LISTEN_TIMEOUT,
                    phrase_time_limit=12.0,
                )

                # Re-check if execution completed during listen
                if buffer.execution_done.is_set():
                    show_idle_voice_popup()
                    continue

                if result is SILENCE_TIMEOUT or result is None:
                    # Silence or unintelligible — keep monitoring
                    continue

                # ── Got speech during execution ──
                if buffer.is_stop_command(result):
                    # HIGHEST PRIORITY: force stop everything
                    print(Fore.RED + "[STOP] Stop during execution!")
                    buffer.force_stop()
                    set_voice_popup_status("Stopped")
                    time.sleep(0.5)
                    hide_voice_popup()
                    show_idle_voice_popup()
                else:
                    # Check if it's a clear new command containing the wake word (or a spelling variant)
                    words = result.lower().split()
                    is_wake_command = any(w in words for w in ["jarvis", "jarivs"]) and len(words) >= 2
                    
                    if is_wake_command:
                        # Extract the actual command
                        actual_cmd = result.lower()
                        for wake in ["hey jarvis", "hey jarivs", "jarvis", "jarivs"]:
                            if actual_cmd.startswith(wake):
                                actual_cmd = actual_cmd[len(wake):].strip()
                                break
                        
                        # Apply auto-correct for 'email this' voice mis-transcriptions
                        if actual_cmd in ["image", "images", "image image", "image this", "images jarvis", "image jarvis"]:
                            actual_cmd = "email this"
                            
                        if actual_cmd:
                            print(Fore.YELLOW + f"[Interrupt] New command during execution: '{actual_cmd}'")
                            buffer.start_immediate_execution(actual_cmd)
                            
                            # Write to input.txt to trigger execution in Jarvis.py
                            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                            input_file = os.path.join(base_dir, "input.txt")
                            with open(input_file, "w") as f:
                                f.write(actual_cmd)
                                
                            show_voice_popup()
                            update_voice_text(actual_cmd)
                            set_voice_popup_status("Processing...")
                    else:
                        # Noise or casual speech - ignore to prevent loop hangs
                        print(Fore.LIGHTBLACK_EX + f"[STT] Ignored noise during execution: '{result}'")

        except KeyboardInterrupt:
            print(Fore.YELLOW + "\n[JARVIS] Speech recognition stopped")
            break
        except Exception as e:
            print(Fore.RED + f"[ERROR] {e}")
            continue


# ============================================================================
# LEGACY (backward compatibility)
# ============================================================================
def listen_once() -> str:
    """
    Listen for a single command without wake word (for testing/direct use).
    
    Returns:
        Transcribed command string
    """
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.pause_threshold = 0.5
    
    with sr.Microphone() as source:
        print(Fore.GREEN + "Listening (direct mode)...")
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
            text = recognizer.recognize_google(audio).lower().strip()
            return text
        except:
            return ""


if __name__ == "__main__":
    listen()