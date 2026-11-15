import speech_recognition as sr
from config import LANGUAGE

recognizer = sr.Recognizer()
recognizer.pause_threshold = 1.2        # itni der chup rehne par hi sentence khatam maana jaye
recognizer.dynamic_energy_threshold = True

_calibrated = False


def _calibrate(source):
    """Mic ko sirf ek baar calibrate karo, har baar nahi."""
    global _calibrated
    if not _calibrated:
        print("Calibrating mic... thoda shant raho")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        _calibrated = True


def listen(timeout=5, phrase_limit=15):
    """Mic se sunta hai aur lowercase text return karta hai. Kuch na suna toh ''."""
    with sr.Microphone() as source:
        _calibrate(source)
        try:
            audio = recognizer.listen(
                source, timeout=timeout, phrase_time_limit=phrase_limit
            )
        except sr.WaitTimeoutError:
            return ""

    try:
        text = recognizer.recognize_google(audio, language=LANGUAGE)
        print(f"You: {text}")
        return text.lower()
    except sr.UnknownValueError:
        return ""
    except sr.RequestError:
        print("Internet problem: speech service se connect nahi ho paya")
        return ""