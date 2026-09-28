"""
Battery monitoring module - alerts for battery status
"""
import psutil
import time
import threading
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from TextToSpeech.Fast_DF_TTS import speak
from notification import Alert


def battery_Alert():
    """Monitor battery percentage and alert at critical levels"""
    alerted_100 = False
    alerted_20 = False
    alerted_10 = False
    alerted_5 = False
    
    while True:
        battery = psutil.sensors_battery()
        if battery is None:
            print("[Battery] No battery detected")
            time.sleep(60)
            continue
            
        percentage = int(battery.percent)
        
        # Reset alerts when charging state changes
        if battery.power_plugged:
            alerted_20 = False
            alerted_10 = False
            alerted_5 = False
        else:
            alerted_100 = False
        
        # Check conditions (order matters - check lowest first)
        if percentage <= 5 and not alerted_5 and not battery.power_plugged:
            t1 = threading.Thread(target=Alert, args=("Battery is about to die!",))
            t2 = threading.Thread(target=speak, args=("Sir, this is your last chance. Charge your system now!",))
            t1.start()
            t2.start()
            t1.join()
            t2.join()
            alerted_5 = True
            
        elif percentage <= 10 and not alerted_10 and not battery.power_plugged:
            t1 = threading.Thread(target=Alert, args=("Battery is very low!",))
            t2 = threading.Thread(target=speak, args=("Sir, we are running on very low battery power.",))
            t1.start()
            t2.start()
            t1.join()
            t2.join()
            alerted_10 = True
            
        elif percentage <= 20 and not alerted_20 and not battery.power_plugged:
            t1 = threading.Thread(target=Alert, args=("Battery Low",))
            t2 = threading.Thread(target=speak, args=("Sir, battery is low now.",))
            t1.start()
            t2.start()
            t1.join()
            t2.join()
            alerted_20 = True
            
    
        
        time.sleep(30)  # Check every 30 seconds





def check_percentage():
    """Speak current battery percentage"""
    battery = psutil.sensors_battery()
    if battery is None:
        speak("No battery detected.")
        return
        
    percent = int(battery.percent)
    plugged = "and charging" if battery.power_plugged else ""
    
    t1 = threading.Thread(target=Alert, args=(f"Battery: {percent}%",))
    t2 = threading.Thread(target=speak, args=(f"The device is running on {percent}% power {plugged}.",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()


if __name__ == "__main__":
    check_percentage()