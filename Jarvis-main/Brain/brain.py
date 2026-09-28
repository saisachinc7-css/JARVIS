from pathlib import Path

from webscout import PhindSearch as brain
from rich import print
from webscout.AIutel import RawDog
from TextToSpeech.Fast_DF_TTS import speak


rawdog = RawDog()
intro_prompt = rawdog.intro_prompt

ai = brain(
    is_conversation=True,
    max_tokens=800,
    timeout=30,
    intro=intro_prompt,
    filepath=str(Path(__file__).resolve().parents[1] / "chat_history.txt"),
    upload_file=True,
    proxies={},
    history_offset=10250,
    act=None,
)

def Main_Brain(text):
    response = ai.chat(text)
    rawdog_feedback = rawdog.main(response)
    if rawdog_feedback:
        print(rawdog_feedback)
        speak(rawdog_feedback)
        ai.chat(rawdog_feedback)

while True:
    x = input("::::")
    Main_Brain(x)
