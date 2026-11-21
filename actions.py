import datetime
import os
import re
import subprocess
import urllib.request
import webbrowser
from urllib.parse import quote_plus

import psutil
import pyautogui

import notes
import reminders

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

APPS = {
    "chrome": "start chrome",
    "vs code": "code",
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


def open_app(name: str) -> str:
    """Open a desktop app on the laptop. Supported apps: chrome, vs code, notepad, calculator, file explorer, settings."""
    name = name.lower().strip()
    if name in ("visual studio code", "vscode", "code"):
        name = "vs code"
    for key, cmd in APPS.items():
        if key in name:
            subprocess.Popen(cmd, shell=True)
            return f"Opened {key}."
    return f"Unknown app '{name}'. Supported apps: " + ", ".join(APPS)


def open_website(name: str) -> str:
    """Open a website. Known names: youtube, google, github, gmail, claude. A domain like example.com also works."""
    name = name.lower().strip()
    for key, url in SITES.items():
        if key in name:
            webbrowser.open(url)
            return f"Opened {key}."
    if "." in name and " " not in name:
        webbrowser.open(name if name.startswith("http") else f"https://{name}")
        return f"Opened {name}."
    return f"Unknown website '{name}'."


def play_youtube(query: str) -> str:
    """Search YouTube for a song or video and play the first result in the browser."""
    search_url = "https://www.youtube.com/results?search_query=" + quote_plus(query)
    try:
        request = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(request, timeout=8).read().decode("utf-8", errors="ignore")
        match = re.search(r'"videoId":"([\w-]{11})"', html)
        if match:
            webbrowser.open(f"https://www.youtube.com/watch?v={match.group(1)}")
            return f"Playing {query} on YouTube."
    except Exception:
        pass
    webbrowser.open(search_url)
    return f"Opened YouTube search results for {query}."


def search_google(query: str) -> str:
    """Search Google for the given query in the browser."""
    webbrowser.open(f"https://www.google.com/search?q={quote_plus(query)}")
    return f"Searching Google for {query}."


def get_time_and_date() -> str:
    """Get the current time and date."""
    return datetime.datetime.now().strftime("It is %I:%M %p on %A, %d %B %Y.")


def get_battery_status() -> str:
    """Get the laptop battery percentage and whether it is charging."""
    battery = psutil.sensors_battery()
    if battery is None:
        return "Battery information is not available."
    status = "charging" if battery.power_plugged else "not charging"
    return f"Battery is at {int(battery.percent)} percent and {status}."


def change_volume(direction: str) -> str:
    """Change the laptop volume. direction must be 'up', 'down' or 'mute'."""
    direction = direction.lower().strip()
    if direction == "up":
        for _ in range(5):
            pyautogui.press("volumeup")
        return "Volume increased."
    if direction == "down":
        for _ in range(5):
            pyautogui.press("volumedown")
        return "Volume decreased."
    if direction == "mute":
        pyautogui.press("volumemute")
        return "Mute toggled."
    return "direction must be up, down or mute."


def take_screenshot() -> str:
    """Take a screenshot of the screen and save it."""
    folder = os.path.join(BASE_DIR, "screenshots")
    os.makedirs(folder, exist_ok=True)
    name = datetime.datetime.now().strftime("shot_%Y%m%d_%H%M%S.png")
    pyautogui.screenshot(os.path.join(folder, name))
    return "Screenshot saved."


def save_note(text: str) -> str:
    """Save a short note for the user."""
    notes.save_note(text)
    return "Note saved."


def set_reminder(minutes: int, text: str) -> str:
    """Set a reminder that fires after the given number of minutes. 'text' says what to remind about."""
    minutes = max(1, int(minutes))
    reply = reminders.add_reminder(f"remind me in {minutes} minutes to {text}")
    return reply or "Could not set the reminder."