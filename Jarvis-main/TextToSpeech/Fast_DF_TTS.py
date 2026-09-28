"""
Fast Text-to-Speech using Edge TTS with async generation
Optimized for minimal latency - no subprocess overhead
Integrated with Adaptive Volume Control for Friday
Supports mid-speech interruption via pygame mixer.
"""
import os
import sys
import asyncio
import tempfile
import threading
import time as _time
import edge_tts

try:
    from playsound import playsound
    _PLAYSOUND_AVAILABLE = True
except ImportError:
    _PLAYSOUND_AVAILABLE = False

# pygame mixer for interruptible playback
try:
    import pygame
    if not pygame.mixer.get_init():
        pygame.mixer.init()
    _PYGAME_AVAILABLE = True
except Exception:
    _PYGAME_AVAILABLE = False

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared_state import set_speaking, is_tts_stop_requested, clear_tts_stop

# Thread lock to prevent multiple audio playing at once
_speak_lock = threading.Lock()

# Reuse event loop for better performance
_loop = None

# Adaptive volume control - lazy loaded
_adaptive_volume = None


def _get_adaptive_volume():
    """Lazy-load adaptive volume controller to avoid circular imports."""
    global _adaptive_volume
    if _adaptive_volume is None:
        try:
            from Laptop_Controls.adaptive_volume import get_adaptive_volume
            _adaptive_volume = get_adaptive_volume()
            print("[TTS] Adaptive volume control loaded")
        except Exception as e:
            print(f"[TTS] Adaptive volume unavailable: {e}")
    return _adaptive_volume


def _get_loop():
    """Get or create event loop"""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
    return _loop


async def _generate_audio(text: str, output_file: str, voice: str) -> bool:
    """Generate audio file using Edge TTS async API directly"""
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        return True
    except Exception as e:
        print(f"[TTS] Generation error: {e}")
        return False


def _play_interruptible(filepath: str):
    """
    Play an audio file with support for mid-play interruption.

    Uses pygame.mixer (preferred) which supports .stop().
    Falls back to playsound if pygame is unavailable.
    Checks is_tts_stop_requested() every 50 ms during playback.
    """
    if _PYGAME_AVAILABLE:
        try:
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                if is_tts_stop_requested():
                    pygame.mixer.music.stop()
                    clear_tts_stop()
                    print("[TTS] Audio stopped (interrupt)")
                    return
                _time.sleep(0.05)
            return
        except Exception as e:
            print(f"[TTS] pygame play error: {e}, falling back to playsound")

    # Fallback: playsound (blocking, not interruptible)
    if _PLAYSOUND_AVAILABLE:
        playsound(filepath)
    else:
        print("[TTS] No audio backend available")


def speak(text: str, voice: str = "en-CA-LiamNeural") -> None:
    """
    Fast text-to-speech function using Edge TTS.
    Uses async API directly instead of CLI subprocess for lower latency.
    Blocks until audio finishes playing.

    Audio Ducking Flow:
      - Other apps are ALREADY ducked from wake word detection
        (Spotify, Chrome, etc. at ~15% of their volume)
      - System volume is raised if needed so JARVIS's TTS is clearly audible
      - After TTS finishes: system volume restored + all apps un-ducked
    """
    if not text or not text.strip():
        return

    # Check TTS stop flag — skip entirely if stop was requested
    if is_tts_stop_requested():
        clear_tts_stop()
        print("[TTS] Skipped - stop requested")
        return
    
    # Only one speak at a time - skip if already speaking
    if not _speak_lock.acquire(blocking=False):
        print("[TTS] Skipped - already speaking")
        return
    
    output_file = None
    avc = _get_adaptive_volume()
    volume_adjusted = False

    try:
        # ── Adaptive Volume: prepare (duck/raise) before speaking ──
        # NOTE: Per-app ducking may already be active from wake word detection.
        # prepare_for_speech() handles system volume (raise if too low).
        # The per-app ducking stays in effect until restore_after_speech().
        if avc:
            try:
                # If wake word didn't duck yet (e.g. Telegram/text input), duck now
                if not avc._is_ducked:
                    avc.on_wake_word()
                
                vol_info = avc.prepare_for_speech()
                volume_adjusted = True
                print(f"[TTS] Volume adjusted: {vol_info.get('case', '?')} | "
                      f"orig={vol_info.get('original_volume')}% -> "
                      f"target={vol_info.get('target_volume')}%")
            except Exception as e:
                print(f"[TTS] Volume adjust failed (continuing): {e}")

        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmpfile:
            output_file = tmpfile.name
        
        # Generate audio using async API directly (faster than subprocess)
        loop = _get_loop()
        success = loop.run_until_complete(_generate_audio(text, output_file, voice))
        
        # Play audio (interruptible via pygame mixer, playsound fallback)
        if success and os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            print(f"[TTS] Speaking: {text[:40]}...")
            set_speaking(True)  # Signal that TTS is speaking
            try:
                _play_interruptible(output_file)
            finally:
                set_speaking(False)  # Signal that TTS is done
            print("[TTS] Done speaking")
        else:
            print("[TTS] No audio generated")
            
    except Exception as e:
        print(f"[TTS] Error: {e}")
        
    finally:
        # ── Adaptive Volume: restore original volume ──
        # CRITICAL: This MUST succeed even if everything else crashed.
        # Failure here leaves user's volume permanently broken.
        if avc:
            try:
                avc.restore_after_speech()
            except Exception as e:
                # Last resort: force reset all app volumes to 100%
                try:
                    avc._audio._reset_all_app_volumes()
                except Exception:
                    pass
                try:
                    # Restore system volume if we saved it
                    if avc._original_volume is not None:
                        avc._audio.set_volume(avc._original_volume)
                except Exception:
                    pass
                # Clear state flags regardless
                avc._is_adjusted = False
                avc._is_ducked = False
                avc._ducked_originals = {}
                avc._original_volume = None
                avc._adjustment_count = 0

        _speak_lock.release()
        # Clean up temp file
        if output_file and os.path.exists(output_file):
            try:
                os.remove(output_file)
            except:
                pass


if __name__ == "__main__":
    x = input("Enter text: ")
    speak(x)