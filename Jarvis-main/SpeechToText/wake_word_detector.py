"""
Wake Word Detector for JARVIS Voice Assistant - OPTIMIZED VERSION
High-speed wake word detection with instant command processing.

OPTIMIZATION STRATEGY:
1. FAST PATH: If "hey jarvis [command]" spoken together → process immediately
2. SLOW PATH: If just "hey jarvis" → wait for command (1.5s buffer max)
3. Single API call per phrase (not multiple)
4. No unnecessary waiting

State Machine:
  WAITING → detect "hey jarvis [cmd]" → INSTANT PROCESS
  WAITING → detect "hey jarvis" only → QUICK_LISTEN → process after 1.5s
"""

import speech_recognition as sr
from colorama import Fore
import time
from difflib import SequenceMatcher
from typing import Optional, Tuple
import threading

# Voice popup integration
from shared_state import show_voice_popup, hide_voice_popup, update_voice_text, set_voice_popup_status


# ============================================================================
# AUDIO DUCKING ON WAKE WORD
# ============================================================================

def _duck_on_wake():
    """Instantly duck other apps when wake word is detected.
    Runs in a thread to avoid blocking the speech pipeline."""
    try:
        from Laptop_Controls.adaptive_volume import on_wake_word
        on_wake_word()
    except Exception as e:
        print(Fore.YELLOW + f"[WakeWord] Audio ducking unavailable: {e}")


# ============================================================================
# CONFIGURATION - SPEED OPTIMIZED
# ============================================================================

# Wake word phrases - "Jarvis" (and "Friday" as fallback)
WAKE_PHRASES = [
    "hey jarvis",
    "hey jarivs",
    "jarvis what's up",
    "jarvis whats up",
    "jarivs what's up",
    "jarivs whats up",
    "what's up jarvis",
    "whats up jarvis",
    "what's up jarivs",
    "whats up jarivs",
    "hi jarvis",
    "hi jarivs",
    "hello jarvis",
    "hello jarivs",
    "hey jar",
    "hey jarv",
    "hey jarb",
    "hey charvis",
    "wake up jarvis",
    "wake up jarivs",
    "jarvis",
    "jarivs",
    "jarves",
    "jarvys",
    "charvis",
]

# Minimum similarity for fuzzy matching
WAKE_SIMILARITY_THRESHOLD = 0.60

# FAST: Wait 4 seconds for continuation (gives time to finish speaking)
SILENCE_BUFFER_SECONDS = 4.0

# Maximum listen time after wake word (prevents hanging)
MAX_COMMAND_WAIT_SECONDS = 20.0

# Single phrase time limit
PHRASE_TIME_LIMIT = 12.0  # Long enough for full command in one breath


# ============================================================================
# OPTIMIZED WAKE WORD DETECTOR
# ============================================================================

class WakeWordDetector:
    """
    High-speed wake word detector with instant command processing.
    
    FAST PATH: "hey jarvis open youtube" → processes immediately, no delay
    SLOW PATH: "hey jarvis" (pause) "open youtube" → 1.5s buffer
    """
    
    def __init__(self, recognizer: sr.Recognizer):
        self.recognizer = recognizer
        self._lock = threading.Lock()
        
    def get_command(self) -> Optional[str]:
        """
        Listen for wake word and return command.
        Optimized for speed - processes immediately when possible.
        """
        with sr.Microphone() as source:
            print(Fore.CYAN + "Say 'Jarvis' (or 'Friday') + command...")
            
            try:
                # Single listen - capture wake word AND command together
                audio = self.recognizer.listen(
                    source, 
                    timeout=None,  # Wait indefinitely
                    phrase_time_limit=PHRASE_TIME_LIMIT  # 8 seconds max per phrase
                )
            except sr.WaitTimeoutError:
                return None
        
        # Process the audio
        start_time = time.time()
        
        try:
            text = self.recognizer.recognize_google(audio).lower().strip()
            api_time = time.time() - start_time
            print(Fore.LIGHTBLACK_EX + f"   [API: {api_time:.2f}s] Heard: '{text}'")
            
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            print(Fore.RED + f"[ERROR] API Error: {e}")
            return None
        
        # Check if it's a wake word
        is_wake, confidence = self._is_wake_word(text)
        
        if not is_wake:
            # Not a wake word - show what we heard for debugging
            print(Fore.YELLOW + f"   (not wake word)")
            return None
        
        print(Fore.GREEN + f"Wake: '{text}' [{confidence:.0%}]")
        
        # INSTANT: Duck background audio so JARVIS can be heard clearly
        threading.Thread(target=_duck_on_wake, daemon=True).start()
        
        # Show voice popup
        show_voice_popup()
        set_voice_popup_status("Listening...")
        
        # FAST PATH: Extract command from the same phrase
        command = self._extract_command_from_wake(text)
        
        if command and len(command.split()) >= 2:
            # Full command detected in wake phrase - INSTANT PROCESS
            print(Fore.MAGENTA + f"FAST: {command}")
            update_voice_text(command)
            set_voice_popup_status("Processing...")
            return command
        
        # SLOW PATH: Need to listen for more
        if command:
            # Partial command - get the rest
            print(Fore.BLUE + f"Partial: {command}")
            more = self._listen_for_more()
            if more:
                command = command + " " + more
            return command if command else None
        else:
            # Just wake word, no command - listen for it
            print(Fore.GREEN + "Ready, speak command...")
            return self._listen_for_more()
    
    def _listen_for_more(self) -> Optional[str]:
        """
        Quick listen for additional command after wake word.
        Uses SHORT timeout to stay responsive.
        """
        with sr.Microphone() as source:
            try:
                audio = self.recognizer.listen(
                    source,
                    timeout=SILENCE_BUFFER_SECONDS,  # 1.5s timeout
                    phrase_time_limit=PHRASE_TIME_LIMIT
                )
            except sr.WaitTimeoutError:
                print(Fore.YELLOW + "No speech detected")
                return None
        
        try:
            text = self.recognizer.recognize_google(audio).lower().strip()
            
            if not text:
                return None
            
            # Strip wake word if user repeated it
            is_wake, _ = self._is_wake_word(text)
            if is_wake:
                text = self._extract_command_from_wake(text) or text
            
            print(Fore.BLUE + f">> {text}")
            update_voice_text(text)
            set_voice_popup_status("Processing...")
            return text
            
        except sr.UnknownValueError:
            return None
        except sr.RequestError:
            return None
    
    def _is_wake_word(self, text: str) -> Tuple[bool, float]:
        """Fast wake word detection with fuzzy matching."""
        text = text.lower().strip()
        
        # Exact match (fastest)
        for phrase in WAKE_PHRASES:
            if text.startswith(phrase):
                return True, 1.0
            if phrase in text:
                return True, 0.95
        
        # Fuzzy match on first 3 words
        words = text.split()[:3]
        potential_wake = " ".join(words)
        
        best_score = 0.0
        for phrase in WAKE_PHRASES:
            score = SequenceMatcher(None, potential_wake, phrase).ratio()
            best_score = max(best_score, score)
        
        return (best_score >= WAKE_SIMILARITY_THRESHOLD, best_score)
    
    def _extract_command_from_wake(self, text: str) -> str:
        """Extract command portion after wake word."""
        text = text.lower().strip()
        
        # Try exact wake phrase removal
        for phrase in sorted(WAKE_PHRASES, key=len, reverse=True):
            if text.startswith(phrase):
                return text[len(phrase):].strip()
        
        # Fuzzy removal - skip first 2 words if they're wake-like
        words = text.split()
        if len(words) >= 2:
            potential_wake = " ".join(words[:2])
            for phrase in WAKE_PHRASES:
                if SequenceMatcher(None, potential_wake, phrase).ratio() >= WAKE_SIMILARITY_THRESHOLD:
                    return " ".join(words[2:])
        
        return ""


# ============================================================================
# STANDALONE TEST
# ============================================================================

if __name__ == "__main__":
    from colorama import init
    init(autoreset=True)
    
    print(Fore.YELLOW + "Optimized Wake Word Detector")
    print(Fore.YELLOW + "=" * 40)
    print(Fore.CYAN + "Test: Say 'Jarvis, open youtube' in one phrase\n")
    
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = False
    recognizer.pause_threshold = 0.5
    recognizer.phrase_threshold = 0.1
    recognizer.non_speaking_duration = 0.3
    
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        print(Fore.GREEN + "[OK] Ready!\n")
    
    detector = WakeWordDetector(recognizer)
    
    while True:
        try:
            start = time.time()
            command = detector.get_command()
            elapsed = time.time() - start
            
            if command:
                print(Fore.MAGENTA + f"\nCOMMAND: {command}")
                print(Fore.LIGHTBLACK_EX + f"   Total: {elapsed:.2f}s\n")
                print(Fore.YELLOW + "-" * 40 + "\n")
        except KeyboardInterrupt:
            print(Fore.YELLOW + "\nGoodbye!")
            break

