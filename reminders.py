import re
import datetime

_reminders = []  # (due_time, text)

UNITS = {"second": 1, "sec": 1, "minute": 60, "min": 60, "hour": 3600}
PATTERN = re.compile(
    r"remind me (?:in|after) (\d+)\s*(second|sec|minute|min|hour)s?\s*(?:to|about)?\s*(.*)"
)


def add_reminder(command):
    match = PATTERN.search(command)
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    text = match.group(3).strip() or "your reminder"
    due = datetime.datetime.now() + datetime.timedelta(seconds=amount * UNITS[unit])
    _reminders.append((due, text))
    plural = "" if amount == 1 else "s"
    return f"Okay, I will remind you in {amount} {unit}{plural}"


def get_due():
    now = datetime.datetime.now()
    due_now = [text for due, text in _reminders if due <= now]
    _reminders[:] = [(due, text) for due, text in _reminders if due > now]
    return due_now