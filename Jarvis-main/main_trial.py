"""
JARVIS Main Entry Point
Listens for voice input and speaks it back using Edge TTS.
"""
from TextToSpeech import Fast_DF_TTS
from SpeechToText.SpeechToText_python import speech_to_text_python
import threading
import time

def main():
    """Main function to start JARVIS"""
    print("🚀 JARVIS Starting...")
    print("🎤 Speak something and I'll repeat it back!")
    
    # Just run the speech-to-text (it calls speak directly now)
    try:
        speech_to_text_python()
    except KeyboardInterrupt:
        print("\n👋 JARVIS shutting down...")


if __name__ == "__main__":
    main()
