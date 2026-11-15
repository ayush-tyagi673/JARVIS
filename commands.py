import os
import re
import datetime
import subprocess
import webbrowser
from urllib.parse import quote_plus

import psutil
import pyautogui

import brain
import notes
import reminders

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

APPS = {
    "chrome": "start chrome",
    "vs code": "code",
    "visual studio code": "code",
    "notepad": "notepad",
    "calculator": "calc",
    "file explorer": "explorer",
    "settings": "start ms-settings:",
}

SITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "claude": "https://claude.ai",
}

TIME_WORDS = ["what time", "current time", "the time", "time kya", "samay"]
DATE_WORDS = ["what date", "today's date", "current date", "what day", "aaj ki date", "tarikh"]
NOTE_PATTERN = re.compile(
    r"(?:take a note|save this note|save note|make a note|note down|note this|note kar)\s*(?:that|ki)?\s*(.*)"
)
AI_STARTERS = ("ask ", "explain ", "tell me about ", "who is ", "why ", "how ")


def handle(command):
    """command lekar (reply_text, exit_flag) return karta hai."""

    # Band karna
    if any(w in command for w in ["exit", "quit", "goodbye", "bye", "band karo"]):
        return "Goodbye Ayush. Take care.", True

    # Reminder (pehle check hota hai, taaki baaki words se na takraye)
    if "remind me" in command:
        reply = reminders.add_reminder(command)
        return reply or "Say it like: remind me in 10 minutes to drink water", False

    # Notes
    note_match = NOTE_PATTERN.search(command)
    if note_match:
        text = note_match.group(1).strip()
        if not text:
            return "Say it like: take a note buy protein powder", False
        notes.save_note(text)
        return "Note saved", False
    if "read my notes" in command or "read notes" in command or "show notes" in command:
        saved = notes.read_notes()
        if not saved:
            return "You have no notes yet", False
        return "Your last notes are. " + ". ".join(saved), False

    # AI ki memory saaf karna
    if "forget everything" in command or "reset memory" in command or "clear memory" in command:
        brain.reset()
        return "Memory cleared", False

    # Time aur date
    if any(w in command for w in TIME_WORDS):
        return datetime.datetime.now().strftime("It is %I:%M %p"), False
    if any(w in command for w in DATE_WORDS):
        return datetime.datetime.now().strftime("Today is %A, %d %B %Y"), False

    # Battery
    if "battery" in command:
        battery = psutil.sensors_battery()
        if battery is None:
            return "I cannot read the battery on this device", False
        status = "charging" if battery.power_plugged else "not charging"
        return f"Battery is at {int(battery.percent)} percent and {status}", False

    # Volume
    if "volume up" in command or "increase volume" in command:
        for _ in range(5):
            pyautogui.press("volumeup")
        return "Volume increased", False
    if "volume down" in command or "decrease volume" in command:
        for _ in range(5):
            pyautogui.press("volumedown")
        return "Volume decreased", False
    if "mute" in command:
        pyautogui.press("volumemute")
        return "Done", False

    # Screenshot
    if "screenshot" in command:
        folder = os.path.join(BASE_DIR, "screenshots")
        os.makedirs(folder, exist_ok=True)
        name = datetime.datetime.now().strftime("shot_%Y%m%d_%H%M%S.png")
        pyautogui.screenshot(os.path.join(folder, name))
        return "Screenshot saved", False

    # AI se sawaal (ask / explain / why / how se shuru ho toh)
    if command.startswith(AI_STARTERS):
        question = command[4:].strip() if command.startswith("ask ") else command
        return brain.ask(question), False

    # Google search
    if "search" in command:
        query = command.split("search", 1)[1]
        for filler in ["on google", "google", "for"]:
            query = query.replace(filler, "")
        query = query.strip()
        if not query:
            return "What should I search for?", False
        webbrowser.open(f"https://www.google.com/search?q={quote_plus(query)}")
        return f"Searching for {query}", False

    # Websites aur apps kholna
    if "open" in command or "kholo" in command or "start" in command:
        for name, url in SITES.items():
            if name in command:
                webbrowser.open(url)
                return f"Opening {name}", False
        for name, cmd in APPS.items():
            if name in command:
                subprocess.Popen(cmd, shell=True)
                return f"Opening {name}", False
        return "I do not know that app yet", False

    # Baaki sab kuch AI ko bhej do
    return brain.ask(command), False