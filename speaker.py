import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import asyncio
import tempfile
import threading
import time

import edge_tts
import pygame
import pyttsx3

from config import SPEECH_RATE, VOICE

_lock = threading.Lock()
_mixer_ready = False


async def _save_speech(text, path):
    await edge_tts.Communicate(text, VOICE).save(path)


def _speak_natural(text):
    """Insaan jaisi awaaz (internet chahiye)."""
    global _mixer_ready
    if not _mixer_ready:
        pygame.mixer.init()
        _mixer_ready = True

    path = os.path.join(tempfile.gettempdir(), "jarvis_voice.mp3")
    asyncio.run(_save_speech(text, path))
    pygame.mixer.music.load(path)
    try:
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.05)
    finally:
        pygame.mixer.music.unload()


def _speak_offline(text):
    """Purani robot awaaz. Natural awaaz na chale toh yahi kaam aayegi."""
    engine = pyttsx3.init()
    engine.setProperty("rate", SPEECH_RATE)
    engine.say(text)
    engine.runAndWait()
    engine.stop()


def speak(text):
    print(f"Jarvis: {text}")
    with _lock:
        try:
            _speak_natural(text)
        except Exception as error:
            print(f"Natural voice fail hui, offline awaaz use ho rahi hai: {error}")
            try:
                _speak_offline(text)
            except Exception as error2:
                print(f"Offline awaaz bhi fail hui: {error2}")