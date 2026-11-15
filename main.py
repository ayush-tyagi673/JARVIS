from config import WAKE_WORDS
from listener import listen
from speaker import speak
from commands import handle
from reminders import get_due


def find_wake_word(heard):
    for word in WAKE_WORDS:
        if word in heard:
            return word
    return None


def main():
    speak("Jarvis online. Say Jarvis to wake me up.")
    while True:
        # Reminder ka time ho gaya ho toh bolo
        for text in get_due():
            speak(f"Reminder: {text}")

        heard = listen(timeout=5, phrase_limit=15)
        if not heard:
            continue

        word = find_wake_word(heard)
        if not word:
            continue

        # "jarvis open chrome" ek saath bola ho toh seedha command le lo
        command = heard.split(word, 1)[1].strip()
        if not command:
            speak("Yes Ayush?")
            command = listen(timeout=6, phrase_limit=15)
            if not command:
                speak("I did not hear anything")
                continue

        reply, should_exit = handle(command)
        speak(reply)
        if should_exit:
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nJarvis stopped.")