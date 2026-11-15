import logging
import math
import os
import queue
import random
import sys
import threading
import time
import tkinter as tk

import customtkinter as ctk

from config import WAKE_WORDS
from listener import listen
from speaker import speak
from commands import handle
from reminders import get_due

try:
    import pythoncom  # awaaz ke thread ke liye
except ImportError:
    pythoncom = None

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(
    filename=os.path.join(BASE_DIR, "jarvis.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

BG = "#05080f"
PANEL = "#0b1220"
TEXT = "#d7f6ff"
LISTEN_NOW = "__listen_now__"

STATES = {
    "standby":   {"label": "STANDBY",   "color": "#0fa3b8", "amp": 3,  "speed": 0.06, "spin": 0.6},
    "listening": {"label": "LISTENING", "color": "#00e5ff", "amp": 7,  "speed": 0.12, "spin": 1.6},
    "thinking":  {"label": "THINKING",  "color": "#ffb000", "amp": 4,  "speed": 0.20, "spin": 5.0},
    "speaking":  {"label": "SPEAKING",  "color": "#7df9ff", "amp": 12, "speed": 0.30, "spin": 2.4},
}


def hex_to_rgb(value):
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, v))) for v in rgb)


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def tray_image():
    img = Image.new("RGB", (64, 64), (5, 8, 15))
    draw = ImageDraw.Draw(img)
    draw.ellipse((6, 6, 58, 58), outline=(0, 229, 255), width=5)
    draw.ellipse((24, 24, 40, 40), fill=(0, 229, 255))
    return img


class JarvisApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("J.A.R.V.I.S")
        self.geometry("980x600")
        self.minsize(900, 560)
        self.configure(fg_color=BG)

        self.ui_queue = queue.Queue()   # worker -> GUI
        self.inbox = queue.Queue()      # GUI -> worker
        self.running = True

        self.mode = "standby"
        self.color = hex_to_rgb(STATES["standby"]["color"])
        self.t = 0.0
        self.spin = 0.0
        self.core_r = 44.0

        self.build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.tray = None
        self.start_tray()
        if "--hidden" in sys.argv and self.tray:
            self.after(600, self.withdraw)  # startup pe chupchap tray mein

        threading.Thread(target=self.worker, daemon=True).start()
        self.after(100, self.poll_ui)
        self.after(33, self.animate)

    # ---------------- Look ----------------
    def build_ui(self):
        left = ctk.CTkFrame(self, fg_color=BG)
        left.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        self.canvas = tk.Canvas(left, width=440, height=440, bg=BG, highlightthickness=0)
        self.canvas.pack(pady=(10, 0))

        self.status = ctk.CTkLabel(
            left, text="STANDBY", font=("Consolas", 20, "bold"), text_color="#0fa3b8"
        )
        self.status.pack(pady=(8, 0))
        ctk.CTkLabel(
            left, text='Say "Jarvis ..." or press MIC',
            font=("Consolas", 12), text_color="#5b7a85",
        ).pack()

        right = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12, width=400)
        right.pack(side="right", fill="y", padx=(0, 14), pady=14)
        right.pack_propagate(False)

        self.chat = ctk.CTkTextbox(
            right, fg_color=PANEL, text_color=TEXT, font=("Consolas", 13),
            wrap="word", state="disabled",
        )
        self.chat.pack(fill="both", expand=True, padx=10, pady=(10, 6))
        self.chat.tag_config("you", foreground="#7aa2ff")
        self.chat.tag_config("jarvis", foreground="#00e5ff")

        row = ctk.CTkFrame(right, fg_color=PANEL)
        row.pack(fill="x", padx=10, pady=(0, 10))
        self.entry = ctk.CTkEntry(
            row, placeholder_text="Type a command...",
            fg_color=BG, border_color="#0fa3b8", text_color=TEXT,
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", self.send_typed)
        ctk.CTkButton(
            row, text="MIC", width=60, fg_color="#0fa3b8",
            hover_color="#00e5ff", text_color="#021014", command=self.press_mic,
        ).pack(side="right")

    def set_state(self, state):
        self.mode = state
        cfg = STATES[state]
        self.status.configure(text=cfg["label"], text_color=cfg["color"])

    def log(self, who, text):
        tag = "you" if who == "You" else "jarvis"
        self.chat.configure(state="normal")
        self.chat.insert("end", f"{who}: {text}\n\n", tag)
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def animate(self):
        if not self.running:
            return
        # Window chhupi ho toh drawing band, battery bachti hai
        if not self.winfo_viewable():
            self.after(300, self.animate)
            return

        cfg = STATES[self.mode]
        self.color = mix(self.color, hex_to_rgb(cfg["color"]), 0.12)
        self.t += cfg["speed"]
        self.spin += cfg["spin"]

        if self.mode == "speaking":
            pulse = cfg["amp"] * (0.5 + 0.5 * math.sin(self.t * 3)) + random.uniform(0, cfg["amp"] * 0.5)
        else:
            pulse = cfg["amp"] * math.sin(self.t)
        self.core_r += (44 + pulse - self.core_r) * 0.35

        c = self.canvas
        c.delete("all")
        cx = cy = 220
        bg = hex_to_rgb(BG)
        accent = self.color

        for i in range(8, 0, -1):
            r = self.core_r + i * 8
            shade = rgb_to_hex(mix(bg, accent, 0.06 * (9 - i)))
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=shade, outline="")

        dim = rgb_to_hex(mix(bg, accent, 0.25))
        bright = rgb_to_hex(accent)
        for radius, width, speed_mult, segments in [(105, 3, 1.0, 3), (135, 2, -0.7, 4), (165, 3, 0.5, 5)]:
            c.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline=dim, width=1)
            step = 360 / segments
            for k in range(segments):
                c.create_arc(
                    cx - radius, cy - radius, cx + radius, cy + radius,
                    start=self.spin * speed_mult + k * step, extent=step * 0.55,
                    style="arc", outline=bright, width=width,
                )

        for i in range(60):
            angle = math.radians(i * 6 + self.spin * 0.2)
            inner = 188
            outer = inner + (9 if i % 5 == 0 else 4)
            c.create_line(
                cx + inner * math.cos(angle), cy + inner * math.sin(angle),
                cx + outer * math.cos(angle), cy + outer * math.sin(angle),
                fill=dim, width=1,
            )

        r = self.core_r
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill=rgb_to_hex(mix(accent, (255, 255, 255), 0.35)), outline="")
        r2 = r * 0.6
        c.create_oval(cx - r2, cy - r2, cx + r2, cy + r2, fill=BG, outline="")
        r3 = r * 0.25
        c.create_oval(cx - r3, cy - r3, cx + r3, cy + r3, fill=bright, outline="")

        self.after(33, self.animate)

    # ---------------- Tray ----------------
    def start_tray(self):
        if pystray is None:
            return
        try:
            menu = pystray.Menu(
                pystray.MenuItem(
                    "Show Jarvis", lambda icon, item: self.ui_queue.put(("show",)), default=True
                ),
                pystray.MenuItem("Quit", lambda icon, item: self.ui_queue.put(("quit_now",))),
            )
            self.tray = pystray.Icon("jarvis", tray_image(), "J.A.R.V.I.S", menu)
            self.tray.run_detached()
        except Exception:
            logging.exception("Tray icon start nahi hua")
            self.tray = None

    def show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    # ---------------- Buttons ----------------
    def press_mic(self):
        self.inbox.put(LISTEN_NOW)

    def send_typed(self, event=None):
        text = self.entry.get().strip().lower()
        if text:
            self.entry.delete(0, "end")
            self.inbox.put(text)

    def on_close(self):
        if self.tray:
            self.withdraw()      # X dabane par tray mein chhup jao, Jarvis chalta rahega
        else:
            self.quit_app()

    def quit_app(self):
        if not self.running:
            return
        self.running = False
        if self.tray:
            try:
                self.tray.stop()
            except Exception:
                pass
        self.destroy()

    def poll_ui(self):
        if not self.running:
            return
        try:
            while True:
                kind, *data = self.ui_queue.get_nowait()
                if kind == "state":
                    self.set_state(data[0])
                elif kind == "log":
                    self.log(data[0], data[1])
                elif kind == "show":
                    self.show_window()
                elif kind == "quit":
                    self.after(1200, self.quit_app)
                elif kind == "quit_now":
                    self.quit_app()
        except queue.Empty:
            pass
        if self.running:
            self.after(100, self.poll_ui)

    # ---------------- Jarvis ka dimaag (alag thread) ----------------
    def say(self, text):
        self.ui_queue.put(("log", "Jarvis", text))
        self.ui_queue.put(("state", "speaking"))
        speak(text)
        self.ui_queue.put(("state", "standby"))

    def process(self, command):
        self.ui_queue.put(("state", "thinking"))
        try:
            reply, should_exit = handle(command)
        except Exception:
            logging.exception("Command fail hua: %s", command)
            reply, should_exit = "Sorry, something went wrong with that command.", False
        self.say(reply)
        if should_exit:
            self.ui_queue.put(("quit",))
        return should_exit

    def hear_command(self):
        self.ui_queue.put(("state", "listening"))
        command = listen(timeout=6, phrase_limit=15)
        if command:
            self.ui_queue.put(("log", "You", command))
        else:
            self.ui_queue.put(("state", "standby"))
        return command

    def step(self):
        """Ek round. True return kare toh Jarvis band hoga."""
        for text in get_due():
            self.say(f"Reminder: {text}")

        try:
            item = self.inbox.get_nowait()
        except queue.Empty:
            item = None

        # MIC button dabaya
        if item == LISTEN_NOW:
            command = self.hear_command()
            for word in WAKE_WORDS:
                command = command.replace(word, "").strip()
            if not command:
                self.say("I did not hear anything")
                return False
            return self.process(command)

        # Type kiya hua command
        if item:
            self.ui_queue.put(("log", "You", item))
            return self.process(item)

        # Normal: wake word ka intezaar
        heard = listen(timeout=3, phrase_limit=15)
        if not heard:
            return False
        word = next((w for w in WAKE_WORDS if w in heard), None)
        if not word:
            return False

        self.ui_queue.put(("log", "You", heard))
        command = heard.split(word, 1)[1].strip()
        if not command:
            self.say("Yes Ayush?")
            command = self.hear_command()
            if not command:
                self.say("I did not hear anything")
                return False
        return self.process(command)

    def worker(self):
        if pythoncom:
            pythoncom.CoInitialize()
        try:
            self.say("Jarvis online. Say Jarvis to wake me up.")
        except Exception:
            logging.exception("Startup message fail hua")

        while self.running:
            try:
                if self.step():
                    break
            except Exception:
                logging.exception("Jarvis loop mein error")
                self.ui_queue.put(("state", "standby"))
                time.sleep(2)  # error ke baad thoda ruko, phir dobara chalo


if __name__ == "__main__":
    try:
        JarvisApp().mainloop()
    except Exception:
        logging.exception("Jarvis crash ho gaya")
        raise