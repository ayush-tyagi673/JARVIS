# J.A.R.V.I.S
A voice-controlled desktop assistant for Windows, built in Python.

## Features
- Wake word "Jarvis", speech-to-text and text-to-speech
- Open apps and websites, Google search, time/date, battery, volume, screenshot
- AI answers with the Gemini API, with short-term memory
- Notes and reminders
- Neon animated GUI (customtkinter), system tray, auto-start

## Setup
1. Install Python 3.12
2. `python -m venv venv` then `venv\Scripts\activate`
3. `pip install -r requirements.txt`
4. Create a `.env` file: `GEMINI_API_KEY=your_key_here`
5. Run `python gui.py`