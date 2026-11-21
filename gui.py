import datetime
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
import psutil

from config import AI_MODEL, VOICE, WAKE_WORDS
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

# ---------- Look ki settings (yahan se rang aur speed badal sakte ho) ----------
BG = "#03060c"
PANEL = "#08101c"
TEXT = "#d7f6ff"
CYAN = "#00e5ff"
ALERT = "#ff3b5c"
FRAME_MS = 33          # 33 = smooth (30 fps). Laptop atke toh 50 kar do
BOOT_FRAMES = 90       # boot animation ki lambai
W, H = 820, 680        # HUD canvas ka size
CX, CY = 500, 290      # orb ka center
LISTEN_NOW = "__listen_now__"

STATES = {
    "standby":   {"label": "STANDBY",   "color": "#0fa3b8", "amp": 3,  "speed": 0.06, "spin": 0.6},
    "listening": {"label": "LISTENING", "color": "#00e5ff", "amp": 7,  "speed": 0.12, "spin": 1.6},
    "thinking":  {"label": "THINKING",  "color": "#ffb000", "amp": 4,  "speed": 0.20, "spin": 5.0},
    "speaking":  {"label": "SPEAKING",  "color": "#7df9ff", "amp": 12, "speed": 0.30, "spin": 2.4},
}

BOOT_LINES = [
    "> BOOTING J.A.R.V.I.S CORE",
    "> LOADING VOICE MODULE ... OK",
    "> CONNECTING AI BRAIN ... OK",
    "> CALIBRATING MIC ... OK",
    "> ALL SYSTEMS ONLINE",
]


def hex_to_rgb(value):
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, v))) for v in rgb)


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


BG_RGB = hex_to_rgb(BG)
CYAN_RGB = hex_to_rgb(CYAN)


def chamfer(x1, y1, x2, y2, c=10):
    """Kate hue kono wala panel."""
    return [x1 + c, y1, x2 - c, y1, x2, y1 + c, x2, y2 - c,
            x2 - c, y2, x1 + c, y2, x1, y2 - c, x1, y1 + c]


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
        self.geometry("1200x720")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        self.ui_queue = queue.Queue()   # worker -> GUI
        self.inbox = queue.Queue()      # GUI -> worker
        self.running = True

        self.mode = "standby"
        self.color = hex_to_rgb(STATES["standby"]["color"])
        self.t = 0.0
        self.spin = 0.0
        self.core_r = 44.0
        self.frame = 0
        self.panels_drawn = False
        self.wave = [3.0] * 36
        self.stat_targets = {"CPU": 0.0, "RAM": 0.0, "BAT": 100.0}
        self.stat_vals = {"CPU": 0.0, "RAM": 0.0, "BAT": 100.0}

        self.build_ui()
        self.draw_static()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.tray = None
        self.start_tray()
        if "--hidden" in sys.argv and self.tray:
            self.after(600, self.withdraw)  # startup pe chupchap tray mein

        threading.Thread(target=self.worker, daemon=True).start()
        self.after(100, self.poll_ui)
        self.after(FRAME_MS, self.animate)

    # ---------------- Layout ----------------
    def build_ui(self):
        self.canvas = tk.Canvas(self, width=W, height=H, bg=BG, highlightthickness=0)
        self.canvas.pack(side="left", padx=(12, 6), pady=12)

        right = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=10, width=340)
        right.pack(side="right", fill="y", padx=(0, 12), pady=12)
        right.pack_propagate(False)

        ctk.CTkLabel(
            right, text="// COMMS LOG", font=("Consolas", 12, "bold"), text_color="#5b9aa8"
        ).pack(anchor="w", padx=14, pady=(12, 0))

        self.chat = ctk.CTkTextbox(
            right, fg_color=PANEL, text_color=TEXT, font=("Consolas", 13),
            wrap="word", state="disabled",
        )
        self.chat.pack(fill="both", expand=True, padx=8, pady=(6, 6))
        self.chat.tag_config("you", foreground="#7aa2ff")
        self.chat.tag_config("jarvis", foreground="#00e5ff")

        row = ctk.CTkFrame(right, fg_color=PANEL)
        row.pack(fill="x", padx=10, pady=(0, 12))
        self.entry = ctk.CTkEntry(
            row, placeholder_text="Type a command...",
            fg_color=BG, border_color="#0fa3b8", text_color=TEXT,
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", self.send_typed)
        ctk.CTkButton(
            row, text="MIC", width=56, fg_color="#0fa3b8",
            hover_color="#00e5ff", text_color="#021014", command=self.press_mic,
        ).pack(side="right")

    def set_state(self, state):
        self.mode = state

    def log(self, who, text):
        tag = "you" if who == "You" else "jarvis"
        self.chat.configure(state="normal")
        self.chat.insert("end", f"{who}: {text}\n\n", tag)
        self.chat.configure(state="disabled")
        self.chat.see("end")

    # ---------------- HUD: jo kabhi nahi badalta (ek baar draw) ----------------
    def draw_static(self):
        c = self.canvas
        grid = rgb_to_hex(mix(BG_RGB, CYAN_RGB, 0.07))
        mid = rgb_to_hex(mix(BG_RGB, CYAN_RGB, 0.40))

        for x in range(0, W, 40):
            c.create_line(x, 0, x, H, fill=grid, tags="static")
        for y in range(0, H, 40):
            c.create_line(0, y, W, y, fill=grid, tags="static")

        # corner brackets
        length = 30
        for x, y, dx, dy in [(8, 8, 1, 1), (W - 8, 8, -1, 1), (8, H - 8, 1, -1), (W - 8, H - 8, -1, -1)]:
            c.create_line(x, y, x + dx * length, y, fill=CYAN, width=2, tags="static")
            c.create_line(x, y, x, y + dy * length, fill=CYAN, width=2, tags="static")

        # title
        c.create_text(CX, 34, text="J . A . R . V . I . S", fill=CYAN,
                      font=("Consolas", 22, "bold"), tags="static")
        c.create_text(CX, 60, text="JUST A RATHER VERY INTELLIGENT SYSTEM", fill=mid,
                      font=("Consolas", 9), tags="static")
        c.create_line(CX - 220, 76, CX + 220, 76, fill=mid, tags="static")
        c.create_text(W - 52, 34, text="ONLINE", fill=mid, anchor="e",
                      font=("Consolas", 9, "bold"), tags="static")

    def draw_panels(self):
        """Boot khatam hone par left ke panels aate hain."""
        c = self.canvas
        mid = rgb_to_hex(mix(BG_RGB, CYAN_RGB, 0.40))

        def panel(x1, y1, x2, y2, title):
            c.create_polygon(chamfer(x1, y1, x2, y2), outline=mid, fill="", width=1, tags="static2")
            c.create_text(x1 + 14, y1 + 14, text=title, anchor="w", fill=mid,
                          font=("Consolas", 9, "bold"), tags="static2")

        panel(20, 95, 225, 265, "SYSTEM")
        panel(20, 285, 225, 395, "CLOCK")
        panel(20, 415, 225, 540, "CORE")

        for name, y in [("CPU", 140), ("RAM", 185), ("BAT", 230)]:
            c.create_text(35, y, text=name, anchor="w", fill=mid,
                          font=("Consolas", 9, "bold"), tags="static2")

        info = [("VOICE", VOICE.replace("Neural", "")), ("BRAIN", AI_MODEL), ("WAKE", WAKE_WORDS[0].upper())]
        for i, (label, value) in enumerate(info):
            y = 437 + i * 38
            c.create_text(35, y, text=label, anchor="w", fill=mid, font=("Consolas", 8), tags="static2")
            c.create_text(35, y + 15, text=value, anchor="w", fill=CYAN, font=("Consolas", 10, "bold"), tags="static2")

        c.create_text(CX, 542, text='SAY "JARVIS ..." OR PRESS MIC', fill=mid,
                      font=("Consolas", 9), tags="static2")

    # ---------------- HUD: jo har frame badalta hai ----------------
    def tick(self):
        cfg = STATES[self.mode]
        self.color = mix(self.color, hex_to_rgb(cfg["color"]), 0.12)
        self.t += cfg["speed"]
        self.spin += cfg["spin"]

        if self.mode == "speaking":
            pulse = cfg["amp"] * (0.5 + 0.5 * math.sin(self.t * 3)) + random.uniform(0, cfg["amp"] * 0.5)
        else:
            pulse = cfg["amp"] * math.sin(self.t)
        self.core_r += (44 + pulse - self.core_r) * 0.35

        if self.frame % 30 == 0:
            self.refresh_stats()

    def refresh_stats(self):
        try:
            self.stat_targets["CPU"] = psutil.cpu_percent(interval=None)
            self.stat_targets["RAM"] = psutil.virtual_memory().percent
            battery = psutil.sensors_battery()
            self.stat_targets["BAT"] = battery.percent if battery else 100.0
        except Exception:
            logging.exception("Stats padhne mein dikkat")

    def animate(self):
        if not self.running:
            return
        # Window chhupi ho toh drawing band, battery bachti hai
        if not self.winfo_viewable():
            self.after(300, self.animate)
            return

        self.frame += 1
        self.tick()
        self.canvas.delete("dyn")
        if self.frame <= BOOT_FRAMES:
            self.draw_boot()
        else:
            self.draw_hud()
        self.after(FRAME_MS, self.animate)

    def draw_boot(self):
        c = self.canvas
        p = self.frame / BOOT_FRAMES
        ease = 1 - (1 - p) ** 3
        self.draw_orb(ease)

        for i, text in enumerate(BOOT_LINES):
            shown = int((self.frame - i * 14) * 2)
            if shown > 0:
                c.create_text(32, 130 + i * 22, text=text[:shown], anchor="w",
                              fill=CYAN, font=("Consolas", 10), tags="dyn")

        # loading bar
        c.create_rectangle(CX - 150, 600, CX + 150, 608, outline=CYAN, tags="dyn")
        c.create_rectangle(CX - 150, 600, CX - 150 + 300 * p, 608, fill=CYAN, outline="", tags="dyn")

    def draw_hud(self):
        c = self.canvas
        if not self.panels_drawn:
            self.draw_panels()
            self.panels_drawn = True

        cfg = STATES[self.mode]
        bright = rgb_to_hex(self.color)
        dim = rgb_to_hex(mix(BG_RGB, self.color, 0.25))

        self.draw_orb(1.0)
        c.create_text(CX, 515, text=cfg["label"], fill=bright, font=("Consolas", 20, "bold"), tags="dyn")

        self.draw_stats(bright, dim)

        # clock
        now = datetime.datetime.now()
        c.create_text(122, 335, text=now.strftime("%H:%M:%S"), fill=bright,
                      font=("Consolas", 22, "bold"), tags="dyn")
        c.create_text(122, 372, text=now.strftime("%a %d %b %Y").upper(), fill=dim,
                      font=("Consolas", 9, "bold"), tags="dyn")

        self.draw_wave()

        # scanline
        y = (self.frame * 3) % H
        c.create_line(0, y, W, y, fill=rgb_to_hex(mix(BG_RGB, CYAN_RGB, 0.10)), tags="dyn")

        # blinking ONLINE light
        if (self.frame // 15) % 2 == 0:
            c.create_oval(W - 40, 30, W - 32, 38, fill="#00ff9c", outline="", tags="dyn")

    def draw_stats(self, bright, dim):
        c = self.canvas
        for name, y in [("CPU", 140), ("RAM", 185), ("BAT", 230)]:
            self.stat_vals[name] += (self.stat_targets[name] - self.stat_vals[name]) * 0.1
            v = self.stat_vals[name]
            hot = (v < 20) if name == "BAT" else (v > 85)
            col = ALERT if hot else bright
            c.create_rectangle(70, y - 6, 165, y + 6, outline=dim, tags="dyn")
            width = 95 * v / 100
            if width > 1:
                c.create_rectangle(70, y - 6, 70 + width, y + 6, fill=col, outline="", tags="dyn")
            c.create_text(212, y, text=f"{int(v)}%", anchor="e", fill=col,
                          font=("Consolas", 9, "bold"), tags="dyn")

    def draw_wave(self):
        c = self.canvas
        n = len(self.wave)
        base = 605
        for i in range(n):
            if self.mode == "speaking":
                env = 1 - abs(i - n / 2) / (n / 2) * 0.6
                target = 5 + random.uniform(3, 44) * env
            elif self.mode == "listening":
                target = 7 + 20 * abs(math.sin(self.t * 1.3 + i * 0.7)) * random.uniform(0.5, 1)
            elif self.mode == "thinking":
                target = 6 + 15 * (0.5 + 0.5 * math.sin(self.t * 2 - i * 0.45))
            else:
                target = 3 + 2 * math.sin(self.t * 4 + i * 0.5)
            self.wave[i] += (target - self.wave[i]) * 0.35
            h = max(1.0, self.wave[i])
            x = CX - (n - 1) * 7 + i * 14
            shade = rgb_to_hex(mix(mix(BG_RGB, self.color, 0.35), self.color, min(1.0, h / 45)))
            c.create_rectangle(x - 4, base - h, x + 4, base + h, fill=shade, outline="", tags="dyn")

    def draw_orb(self, s=1.0):
        """Orb: glow, radar sweep, ghoomte rings, dots, ticks aur core. s = size (boot mein 0 se 1)."""
        c = self.canvas
        accent = self.color
        bright = rgb_to_hex(accent)
        dim = rgb_to_hex(mix(BG_RGB, accent, 0.25))
        core = max(2.0, self.core_r * s)

        # glow
        for i in range(8, 0, -1):
            r = core + i * 8 * s
            c.create_oval(CX - r, CY - r, CX + r, CY + r,
                          fill=rgb_to_hex(mix(BG_RGB, accent, 0.06 * (9 - i))), outline="", tags="dyn")

        # radar sweep (peeche dhundhli hoti trail)
        for k in range(14):
            ang = math.radians(self.spin * 1.2 - k * 2.5)
            col = rgb_to_hex(mix(BG_RGB, accent, 0.6 * (1 - k / 14)))
            c.create_line(CX + 60 * s * math.cos(ang), CY + 60 * s * math.sin(ang),
                          CX + 165 * s * math.cos(ang), CY + 165 * s * math.sin(ang),
                          fill=col, width=2, tags="dyn")

        # ghoomte rings
        for radius, width, mult, segs in [(105, 3, 1.0, 3), (135, 2, -0.7, 4), (165, 3, 0.5, 5)]:
            rr = radius * s
            c.create_oval(CX - rr, CY - rr, CX + rr, CY + rr, outline=dim, width=1, tags="dyn")
            step = 360 / segs
            for k in range(segs):
                c.create_arc(CX - rr, CY - rr, CX + rr, CY + rr,
                             start=self.spin * mult + k * step, extent=step * 0.55,
                             style="arc", outline=bright, width=width, tags="dyn")

        # dots ring
        for i in range(24):
            ang = math.radians(i * 15 - self.spin * 0.8)
            x = CX + 150 * s * math.cos(ang)
            y = CY + 150 * s * math.sin(ang)
            c.create_oval(x - 2, y - 2, x + 2, y + 2,
                          fill=bright if i % 6 == 0 else dim, outline="", tags="dyn")

        # outer ticks
        for i in range(60):
            ang = math.radians(i * 6 + self.spin * 0.2)
            inner = 188 * s
            outer = inner + (9 if i % 5 == 0 else 4) * s
            c.create_line(CX + inner * math.cos(ang), CY + inner * math.sin(ang),
                          CX + outer * math.cos(ang), CY + outer * math.sin(ang),
                          fill=dim, tags="dyn")

        # core (arc reactor)
        c.create_oval(CX - core, CY - core, CX + core, CY + core,
                      fill=rgb_to_hex(mix(accent, (255, 255, 255), 0.35)), outline="", tags="dyn")
        r2 = core * 0.6
        c.create_oval(CX - r2, CY - r2, CX + r2, CY + r2, fill=BG, outline="", tags="dyn")
        r3 = core * 0.25
        c.create_oval(CX - r3, CY - r3, CX + r3, CY + r3, fill=bright, outline="", tags="dyn")

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