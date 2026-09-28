import os
import json
import time
import re
from datetime import datetime, timedelta
import threading

REMINDERS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "DATA", "reminders.json")
_lock = threading.Lock()

def load_reminders() -> list:
    """Load reminders from reminders.json."""
    if not os.path.exists(REMINDERS_FILE):
        return []
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ReminderManager] Error loading reminders: {e}")
        return []

def save_reminders(reminders: list):
    """Save reminders to reminders.json."""
    try:
        os.makedirs(os.path.dirname(REMINDERS_FILE), exist_ok=True)
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(reminders, f, indent=4)
    except Exception as e:
        print(f"[ReminderManager] Error saving reminders: {e}")

def add_reminder(task: str, trigger_datetime: datetime) -> dict:
    """Add a new reminder and save it."""
    with _lock:
        reminders = load_reminders()
        trigger_timestamp = trigger_datetime.timestamp()
        
        now = datetime.now()
        if trigger_datetime.date() == now.date():
            time_label = trigger_datetime.strftime("%I:%M %p")
        else:
            time_label = trigger_datetime.strftime("%b %d, %I:%M %p")
            
        reminder = {
            "id": int(time.time() * 1000),
            "text": task,
            "time": trigger_timestamp,
            "formatted_time": time_label,
            "active": True
        }
        reminders.append(reminder)
        # Keep only active or last 10 completed reminders
        active_reminders = [r for r in reminders if r["active"]]
        inactive_reminders = [r for r in reminders if not r["active"]][-10:]
        reminders = active_reminders + inactive_reminders
        save_reminders(reminders)
        return reminder

def get_all_reminders() -> list:
    """Get all reminders (sorted by time)."""
    with _lock:
        reminders = load_reminders()
        return sorted(reminders, key=lambda x: x["time"])

def get_active_reminders() -> list:
    """Get active reminders (sorted by time)."""
    with _lock:
        reminders = load_reminders()
        return sorted([r for r in reminders if r["active"]], key=lambda x: x["time"])

def check_reminders_trigger() -> list:
    """Check if any active reminders have expired. Mark them inactive and return them."""
    with _lock:
        reminders = load_reminders()
        now = time.time()
        triggered = []
        changed = False
        for r in reminders:
            if r["active"] and now >= r["time"]:
                r["active"] = False
                triggered.append(r)
                changed = True
        if changed:
            save_reminders(reminders)
        return triggered

def parse_reminder(text: str):
    """
    Parses a reminder command and returns (task, trigger_time) or None.
    trigger_time is datetime.
    """
    text = text.lower().strip()
    
    # Standardize phrasing variations to fit standard regex patterns
    text = text.replace("set me a reminder", "remind me")
    text = text.replace("set a reminder", "remind me")
    text = text.replace("add a reminder", "remind me")
    text = text.replace("add to my to do list", "remind me")
    text = text.replace("add it to my to do list", "remind me")
    text = text.replace("that i have to", "to")
    text = text.replace("that i need to", "to")
    text = text.replace("that i must", "to")
    text = text.replace("that", "to")
    
    # 1. "remind me to {task} in {num} {minutes/hours/seconds}"
    # 2. "remind me in {num} {minutes/hours/seconds} to {task}"
    in_pattern = r"(?:remind me to (.+?) in (\d+)\s*(sec|second|min|minute|hour|hr)s?|remind me in (\d+)\s*(sec|second|min|minute|hour|hr)s? to (.+))"
    match = re.search(in_pattern, text)
    if match:
        groups = match.groups()
        if groups[0] is not None:
            task = groups[0].strip()
            num = int(groups[1])
            unit = groups[2]
        else:
            num = int(groups[3])
            unit = groups[4]
            task = groups[5].strip()
            
        now = datetime.now()
        if "sec" in unit:
            trigger_time = now + timedelta(seconds=num)
        elif "min" in unit:
            trigger_time = now + timedelta(minutes=num)
        elif "hour" in unit or "hr" in unit:
            trigger_time = now + timedelta(hours=num)
        else:
            return None
        return task, trigger_time

    # 3. "remind me to {task} at {time}"
    # 4. "remind me at {time} to {task}"
    at_pattern = r"(?:remind me to (.+?) at (\d+:\d+|\d+)\s*(am|pm)?|remind me at (\d+:\d+|\d+)\s*(am|pm)? to (.+))"
    match = re.search(at_pattern, text)
    if match:
        groups = match.groups()
        if groups[0] is not None:
            task = groups[0].strip()
            time_str = groups[1]
            ampm = groups[2]
        else:
            time_str = groups[3]
            ampm = groups[4]
            task = groups[5].strip()
            
        now = datetime.now()
        hour = 0
        minute = 0
        if ":" in time_str:
            parts = time_str.split(":")
            hour = int(parts[0])
            minute = int(parts[1])
        else:
            hour = int(time_str)
            
        if ampm:
            ampm = ampm.lower()
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
                
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target < now:
            target += timedelta(days=1)
        return task, target

    return None
