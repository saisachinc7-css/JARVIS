import random
from datetime import datetime
from TextToSpeech.Fast_DF_TTS import speak
from shared_state import ui_jarvis_message, update_voice_text, set_voice_popup_status

# Keep track of the last selected greeting to avoid consecutive repetitions
_last_greeting = None

GREETINGS = {
    "morning": [
        "Good morning. Welcome back. All systems are online and operating normally. How may I assist you today?",
        "Good morning. Core systems are initialized and ready. What would you like to accomplish today?",
        "Good morning, Sir. All diagnostics report nominal. I'm ready whenever you are.",
        "Good morning. Memory banks synchronized and network interface active. How may I assist you?",
        "Good morning. System checks complete, everything is fully operational. What shall we work on today?"
    ],
    "afternoon": [
        "Good afternoon. Welcome back. All diagnostics report nominal. How may I assist you?",
        "Good afternoon. Systems are fully operational. I'm ready whenever you are.",
        "Good afternoon. Processor load minimal, connection secure. What shall we accomplish today?",
        "Good afternoon. Core database synchronized. Awaiting your instructions.",
        "Good afternoon, Sir. Standing by to assist. What is our next objective?"
    ],
    "evening": [
        "Good evening. Welcome back. Core systems online. Memory synchronized. All diagnostics report nominal. How may I assist you today?",
        "Good evening. Welcome back. I've completed my system checks and everything is operating normally. What shall we work on today?",
        "Good evening, Sir. All systems report nominal. I'm ready whenever you are.",
        "Good evening. Connection secure and power levels optimal. How may I serve you tonight?",
        "Good evening. Systems fully initialized. Awaiting your instructions, Sir."
    ],
    "night": [
        "Welcome back, Sir. Burning the midnight oil again? All systems are online and ready.",
        "Welcome back. It's late, but I'm fully operational. How may I assist you tonight?",
        "Late night session initialized. Connection secure, diagnostic nominal. Awaiting your instructions, Sir.",
        "All systems are online and fully operational. I am ready for your command.",
        "Ready for the late shift, Sir. What shall we work on tonight?"
    ]
}

def get_time_period() -> str:
    """Determine the current time period based on hour of the day."""
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 22:
        return "evening"
    else:
        return "night"

def get_random_greeting() -> str:
    """Select a random greeting for the current time period, ensuring no consecutive repetition."""
    global _last_greeting
    period = get_time_period()
    choices = GREETINGS[period]
    
    # Filter out the last selected greeting if there are multiple choices
    valid_choices = [c for c in choices if c != _last_greeting]
    if not valid_choices:
        valid_choices = choices
        
    selected = random.choice(valid_choices)
    _last_greeting = selected
    return selected

def play_startup_greeting():
    """Play a premium startup greeting for JARVIS."""
    greeting = get_random_greeting()
    print(f"[JARVIS] Startup greeting selected: '{greeting}'")
    
    # Display in UI chat log and popup
    try:
        ui_jarvis_message(greeting)
        update_voice_text(greeting)
        set_voice_popup_status("Speaking...")
    except Exception as e:
        print(f"[JARVIS] UI greeting update error: {e}")
        
    # Speak the greeting
    speak(greeting)
