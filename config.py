import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

DEFAULTS = {
    "user_name": "Ayush",
    "wake_words": ["jarvis", "jarves", "travis"],
    "language": "en-IN",
    "speech_rate": 175,
    "ai_model": "gemini-3.5-flash-lite",
    "max_history": 9,
}


def _load():
    data = dict(DEFAULTS)
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            data.update(json.load(f))
    except FileNotFoundError:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULTS, f, indent=4)
    except Exception as error:
        print(f"settings.json padhne mein dikkat: {error}")
    return data


_settings = _load()

USER_NAME = _settings["user_name"]
WAKE_WORDS = _settings["wake_words"]
LANGUAGE = _settings["language"]
SPEECH_RATE = _settings["speech_rate"]
AI_MODEL = _settings["ai_model"]
MAX_HISTORY = _settings["max_history"]