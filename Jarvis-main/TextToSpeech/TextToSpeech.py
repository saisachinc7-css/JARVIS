"""
Text-to-Speech module using Edge TTS.
Integrated with Adaptive Volume Control for Friday.
"""

import os
import sys
import asyncio
import edge_tts
import pygame

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Voice configuration - you can change this to any voice from Edge TTS voice list
VOICE = "en-CA-LiamNeural"

# Adaptive volume control - lazy loaded
_adaptive_volume = None


def _get_adaptive_volume():
    """Lazy-load adaptive volume controller."""
    global _adaptive_volume
    if _adaptive_volume is None:
        try:
            from Laptop_Controls.adaptive_volume import get_adaptive_volume
            _adaptive_volume = get_adaptive_volume()
        except Exception:
            pass
    return _adaptive_volume


def remove_file(file_path):
    """Remove file with retry mechanism"""
    max_attempts = 3
    
    for attempt in range(max_attempts):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            break
        except Exception as e:
            if attempt == max_attempts - 1:
                print(f"Error removing file: {e}")


async def generate_speech(text, output_file):
    """Async function to generate speech and save to file"""
    try:
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(output_file)
        return True
    except Exception as e:
        print(f"Error generating speech: {e}")
        return False


def play_audio(file_path):
    """Play audio using pygame mixer"""
    try:
        pygame.mixer.init()
        sound = pygame.mixer.Sound(file_path)
        sound.play()
        
        # Wait until audio finishes playing
        while pygame.mixer.get_busy():
            pygame.time.Clock().tick(10)
            
        pygame.mixer.quit()
    except Exception as e:
        print(f"Error playing audio: {e}")


def speak(text):
    """Main speak function - generates and plays speech with adaptive volume."""
    # Use script directory for output file (more reliable than cwd)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(script_dir, "speech.mp3")

    avc = _get_adaptive_volume()
    volume_adjusted = False

    try:
        # Adaptive Volume: prepare before speaking
        if avc:
            try:
                avc.prepare_for_speech()
                volume_adjusted = True
            except Exception:
                pass

        # Generate the speech file
        success = asyncio.run(generate_speech(text, output_file))

        if success and os.path.exists(output_file):
            # Play the audio
            play_audio(output_file)
            # Clean up after playing
            remove_file(output_file)
        else:
            print(f"Failed to generate speech for: {text}")

    finally:
        # Adaptive Volume: restore original volume
        if avc and volume_adjusted:
            try:
                avc.restore_after_speech()
            except Exception:
                pass


# Test the speak function
if __name__ == "__main__":
    speak("Hello, I am vellaar, loaded and ready to serve")
   