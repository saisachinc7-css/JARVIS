import pyautogui

# ---------- Browser Action Functions ----------

def open_new_tab():
    pyautogui.hotkey('ctrl', 't')

def close_tab():
    pyautogui.hotkey('ctrl', 'w')

def open_browser_menu():
    pyautogui.hotkey('alt', 'f')

def zoom_in():
    pyautogui.hotkey('ctrl', '+')

def zoom_out():
    pyautogui.hotkey('ctrl', '-')

def refresh_page():
    pyautogui.hotkey('ctrl', 'r')

def switch_to_next_tab():
    pyautogui.hotkey('ctrl', 'tab')

def switch_to_previous_tab():
    pyautogui.hotkey('ctrl', 'shift', 'tab')

def open_history():
    pyautogui.hotkey('ctrl', 'h')

def open_bookmarks():
    pyautogui.hotkey('ctrl', 'b')

def go_back():
    pyautogui.hotkey('alt', 'left')

def go_forward():
    pyautogui.hotkey('alt', 'right')

def open_dev_tools():
    pyautogui.hotkey('ctrl', 'shift', 'i')

def toggle_full_screen():
    pyautogui.hotkey('f11')

def open_private_window():
    pyautogui.hotkey('ctrl', 'shift', 'n')


# ---------- Command Handler ----------

def handle_browser_commands(text):
    text = text.lower()

    if "open new tab" in text or "new tab kholo" in text or "naya tab" in text:
        open_new_tab()

    elif "close tab" in text or "tab band karo" in text:
        close_tab()

    elif "browser menu" in text or "menu kholo" in text:
        open_browser_menu()

    elif "zoom in" in text or "zoom badhao" in text:
        zoom_in()

    elif "zoom out" in text or "zoom kam karo" in text:
        zoom_out()

    elif "refresh page" in text or "reload karo" in text:
        refresh_page()

    elif "next tab" in text or "aage tab" in text:
        switch_to_next_tab()

    elif "previous tab" in text or "pichla tab" in text:
        switch_to_previous_tab()

    elif "open history" in text or "history kholo" in text:
        open_history()

    elif "open bookmarks" in text or "bookmarks kholo" in text:
        open_bookmarks()

    elif "go back" in text or "peeche jao" in text:
        go_back()

    elif "go forward" in text or "aage jao" in text:
        go_forward()

    elif "developer tools" in text or "inspect element" in text:
        open_dev_tools()

    elif "full screen" in text or "maximize" in text:
        toggle_full_screen()

    elif "private window" in text or "incognito kholo" in text:
        open_private_window()

    else:
        pass
