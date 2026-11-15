import pyttsx3
from config import SPEECH_RATE


def speak(text):
    print(f"Jarvis: {text}")
    engine = pyttsx3.init()  # har baar naya engine, taaki hang na ho
    engine.setProperty("rate", SPEECH_RATE)
    engine.say(text)
    engine.runAndWait()
    engine.stop()