import os
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NOTES_FILE = os.path.join(BASE_DIR, "notes.txt")


def save_note(text):
    stamp = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
    with open(NOTES_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {text}\n")


def read_notes(count=3):
    if not os.path.exists(NOTES_FILE):
        return []
    with open(NOTES_FILE, encoding="utf-8") as f:
        lines = f.read().splitlines()
    return [line.split("] ", 1)[-1] for line in lines[-count:]]