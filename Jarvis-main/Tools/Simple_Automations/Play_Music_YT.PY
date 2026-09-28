try:
    import pywhatkit as pw
except ImportError:
    pw = None
import webbrowser

def play_music_on_youtube(Song_name):
    if pw is not None:
        pw.playonyt(Song_name)
        return

    webbrowser.open(f"https://www.youtube.com/results?search_query={Song_name.replace(' ', '+')}")
    print(f"pywhatkit unavailable; opened YouTube search for '{Song_name}'.")

if __name__ == "__main__":
    while True:
        x = input("Song name: ")
        play_music_on_youtube(x)

