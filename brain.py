import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from config import AI_MODEL, MAX_HISTORY

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

_api_key = os.getenv("GEMINI_API_KEY")
_client = genai.Client(api_key=_api_key) if _api_key else None
_history = []

SYSTEM_PROMPT = (
    "You are JARVIS, a voice assistant for Ayush, a BTech CSE student preparing for GATE. "
        "Your answers are read aloud, so keep them to ONE or TWO short sentences, under 30 words, unless Ayush asks for detail. "
    "No markdown, no bullet points, no emojis. "
    "If Ayush speaks Hinglish, reply in Hinglish using English letters. "
    "For coding or GATE doubts, explain simply with one small example."
)


def ask(question):
    if _client is None:
        return "AI key is not set. Please add GEMINI_API_KEY in the dot env file."

    _history.append(types.Content(role="user", parts=[types.Part(text=question)]))
    try:
        response = _client.models.generate_content(
            model=AI_MODEL,
            contents=_history[-MAX_HISTORY:],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
            ),
        )
        answer = (response.text or "").strip() or "I have no answer for that."
    except Exception as error:
        _history.pop()
        print(f"AI error: {error}")
        return "I could not reach the AI right now."

    _history.append(types.Content(role="model", parts=[types.Part(text=answer)]))
    return answer


def reset():
    _history.clear()