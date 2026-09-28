import random
from datetime import datetime

def get_current_time_response() -> str:
    """Generate a custom, context-aware companion message for the current time."""
    now = datetime.now()
    time_str = now.strftime("%I:%M %p")
    # Clean leading zero
    if time_str.startswith("0"):
        time_str = time_str[1:]
        
    hour = now.hour
    
    # Morning (5:00 AM to 11:59 AM)
    if 5 <= hour < 12:
        companions = [
            "A fresh start to the day, sir. Let's make today highly productive.",
            "A perfect time to prioritize your most important work while your focus is fresh.",
            "Good morning, sir. I hope you've had a refreshing start to your day.",
            "The morning is young. Let's conquer those goals today, sir.",
            "A beautiful morning to get started on your projects, sir."
        ]
    # Afternoon (12:00 PM to 4:59 PM)
    elif 12 <= hour < 17:
        companions = [
            "Don't forget to stay hydrated and take a short break if you've been working for a while.",
            "A good time to check your progress and stretch if you've been sitting down, sir.",
            "Powering through the day. Let me know if you need any adjustments to your schedule, sir.",
            "Keep up the momentum, sir. You're making excellent progress today.",
            "A perfect time for a quick screen break to keep your eyes fresh, sir."
        ]
    # Evening (5:00 PM to 8:59 PM)
    elif 17 <= hour < 21:
        companions = [
            "A great time to wrap up any remaining tasks before you unwind for the evening.",
            "The day is winding down. I hope it has been a highly successful one for you, sir.",
            "A perfect evening to relax and recharge your energy, sir.",
            "Sunset is approaching, sir. Time to start shifting your focus towards relaxation.",
            "Winding down the work day. Let's make sure everything is saved and organized, sir."
        ]
    # Night (9:00 PM to 4:59 AM)
    else:
        companions = [
            "You've had a productive day—consider getting some rest to recharge for tomorrow.",
            "It's getting late, sir. Make sure you get some quality sleep tonight.",
            "A quiet night, sir. I'll be here if you need anything before you head to sleep.",
            "Late hours are great for quiet focus, but don't forget to recharge, sir.",
            "The night is quiet. I recommend wrapping up soon to protect your sleep cycle, sir."
        ]
        
    companion = random.choice(companions)
    return f"It's {time_str}. {companion}"


def get_sophisticated_greeting() -> str:
    """Generate a sophisticated, dynamic personal greeting for JARVIS."""
    # 1. Time-of-day greeting
    now = datetime.now()
    hour = now.hour
    if 5 <= hour < 12:
        salutation = "Good morning, Sir."
    elif 12 <= hour < 17:
        salutation = "Good afternoon, Sir."
    elif 17 <= hour < 22:
        salutation = "Good evening, Sir."
    else:
        salutation = "Greetings, Sir. It is late, but I am online."
        
    # 2. System Status
    statuses = [
        "All systems are online and operating at optimal efficiency.",
        "Core protocol layers are fully operational and active.",
        "System diagnostics report nominal performance levels.",
        "All models are prewarmed in GPU VRAM and ready for execution.",
        "Headless server bindings are secure and online."
    ]
    status = random.choice(statuses)
    
    # 3. Live info checks (Reminders)
    live_info = ""
    try:
        from Brain.reminder_manager import get_active_reminders
        active = get_active_reminders()
        if active:
            live_info += f" You have {len(active)} active reminders pending on your schedule."
    except:
        pass
        
    # 4. Closing prompt
    closings = [
        "What would you like to accomplish today, Sir?",
        "I am standing by for your instructions, Sir.",
        "Standing by. What is your command, Sir?",
        "Ready to orchestrate your tasks, Sir."
    ]
    if 17 <= hour < 22:
        closings.append("How may I assist you this evening, Sir?")
    elif hour >= 22 or hour < 5:
        closings.append("How may I assist you tonight, Sir?")
    else:
        closings.append("How may I assist you today, Sir?")
        
    closing = random.choice(closings)
    
    return f"{salutation} {status}{live_info} {closing}"
