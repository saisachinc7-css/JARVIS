import pyautogui
import random
import time
from TextToSpeech.Fast_DF_TTS import speak

# Dialogue responses for YouTube search
yt_search = [
    "Searching on YouTube...",
    "Let me find that for you on YouTube.",
    "Looking it up on YouTube.",
    "Sure, searching YouTube now.",
]

s1 = [
    "Here we go...",
    "Just a moment...",
    "Searching now...",
]

s2 = [
    "Here's what I found.",
    "Done! Check it out.",
    "There you go!",
]


def youtube_search(text):
    """Search for something on YouTube (only works when YouTube is already open)"""
    dlg = random.choice(yt_search)
    speak(dlg, 3)
    time.sleep(0.3)
    pyautogui.press("/")  # Focus YouTube search box
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "a")  # Select all existing text
    time.sleep(0.1)
    pyautogui.write(text, interval=0.03)  # This will replace selected text
    s12 = random.choice(s1)
    speak(s12, 3)
    time.sleep(0.3)
    pyautogui.press("enter")
    s12 = random.choice(s2)
    speak(s12, 3)


def play_pause():
    pyautogui.press('space')

def volume_up():
    pyautogui.press('up')

def volume_down():
    pyautogui.press('down')

def seek_forward():
    pyautogui.press('right')

def seek_backward():
    pyautogui.press('left')

def seek_forward_10s():
    pyautogui.press('l')

def seek_backward_10s():
    pyautogui.press('j')

def seek_backward_frame():
    pyautogui.press(',')

def seek_forward_frame():
    pyautogui.press('.')

def seek_to_beginning():
    pyautogui.press('home')

def seek_to_end():
    pyautogui.press('end')

def seek_to_previous_chapter():
    pyautogui.hotkey('ctrl', 'left')

def seek_to_next_chapter():
    pyautogui.hotkey('ctrl', 'right')

def decrease_playback_speed():
    pyautogui.hotkey('shift', ',')

def increase_playback_speed():
    pyautogui.hotkey('shift', '.')

def move_to_next_video():
    pyautogui.hotkey('shift', 'n')

def move_to_previous_video():
    pyautogui.hotkey('shift', 'p')


def handle_video_commands(text):
    text = text.lower()

    # ---- PLAY FIRST VIDEO (Checked BEFORE generic play/pause) ----
    if "first" in text:
        pyautogui.press("esc")
        time.sleep(0.15)
        for _ in range(7):
            pyautogui.press("tab")
            time.sleep(0.05)
        pyautogui.press("enter")

    # ---- PLAY / PAUSE ----
    elif any(word in text for word in [
        "play", "pause", "resume", "continue", "stop"
    ]):
        play_pause()

    # ---- VOLUME UP ----
    elif any(word in text for word in [
        "volume up", "sound up", "increase volume", "increase sound",
        "louder", "raise volume"
    ]):
        volume_up()

    # ---- VOLUME DOWN ----
    elif any(word in text for word in [
        "volume down", "sound down", "decrease volume",
        "lower volume", "quieter", "reduce sound"
    ]):
        volume_down()

    # ---- SEEK FORWARD ----
    elif any(word in text for word in [
        "forward", "skip ahead", "go ahead"
    ]):
        seek_forward()

    # ---- SEEK BACKWARD ----
    elif any(word in text for word in [
        "back", "rewind", "go back"
    ]):
        seek_backward()

    # ---- FORWARD / BACKWARD 10s ----
    elif "10" in text and "forward" in text:
        seek_forward_10s()

    elif "10" in text and ("back" in text or "rewind" in text):
        seek_backward_10s()

    # ---- FRAME BY FRAME ----
    elif "next frame" in text:
        seek_forward_frame()

    elif "previous frame" in text or "frame back" in text:
        seek_backward_frame()

    # ---- START / END ----
    elif any(word in text for word in [
        "start", "beginning", "from start"
    ]):
        seek_to_beginning()

    elif any(word in text for word in [
        "end", "finish", "to the end"
    ]):
        seek_to_end()

    # ---- CHAPTER NAVIGATION ----
    elif "next chapter" in text:
        seek_to_next_chapter()

    elif "previous chapter" in text:
        seek_to_previous_chapter()

    # ---- PLAYBACK SPEED ----
    elif any(word in text for word in [
        "slow down", "reduce speed", "slower"
    ]):
        decrease_playback_speed()

    elif any(word in text for word in [
        "speed up", "increase speed", "faster"
    ]):
        increase_playback_speed()

    # ---- VIDEO NAVIGATION ----
    elif any(word in text for word in [
        "next video", "play next"
    ]):
        move_to_next_video()

    elif any(word in text for word in [
        "previous video", "play previous"
    ]):
        move_to_previous_video()

    # ---- YOUTUBE SEARCH ----
    elif "search" in text:
        # Extract the search query (everything after "search")
        search_query = text.split("search", 1)[-1].strip()
        if search_query:
            youtube_search(search_query)

    else:
        pass
