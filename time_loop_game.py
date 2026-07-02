"""Time Loop Language Game — stuck in one day, learn English to escape.

The player relives the same day repeatedly. Each loop, they understand
more English words and phrases. The goal is to reach 80%+ comprehension
of key dialogues and "break the loop."

Inspired by Groundhog Day: repetition = progression, not boredom.
"""

from __future__ import annotations

import json
import random
import re
import tkinter as tk
from tkinter import messagebox
from datetime import date
from collections import Counter

from ui_theme import (
    BG, CARD_BG, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, ACCENT_HOVER, SUCCESS, WARNING, DANGER, BORDER, CHAT_BG, CHAT_FG,
    FONT_TITLE, FONT_HEADING, FONT_BODY, FONT_SMALL, FONT_MONO,
    make_button, is_dark,
)

# ─── Scenario templates ───

LOOP_SCENARIOS = [
    {
        "id": "office_deadline",
        "icon": "🏢",
        "title": "Офис: дедлайн",
        "setting": "a busy office on Friday morning",
        "event": "the boss needs the quarterly report before noon, but the data is corrupted",
        "characters": ["the boss (Mr. Henderson)", "your coworker (Sarah)", "the IT guy (Tom)"],
        "key_phrases": [
            "We need to fix this before noon.",
            "The spreadsheet data is corrupted, I can't open it.",
            "I can restore the backup if you send me the file name.",
            "Don't worry, I'll handle it.",
            "This is critical — the client is waiting.",
        ],
        "good_outcome": "You fix the report in time and impress the boss.",
        "bad_outcome": "The report is late and the client is furious.",
        "loop_goal": "Understand all key dialogues and fix the report before noon.",
    },
    {
        "id": "cafe_misunderstanding",
        "icon": "☕",
        "title": "Кафе: недопонимание",
        "setting": "a cozy cafe during lunch rush",
        "event": "a customer is allergic to nuts but the barista keeps getting the order wrong",
        "characters": ["the barista (Emma)", "the customer (Mr. Park)", "the manager (Lisa)"],
        "key_phrases": [
            "I said no nuts — I'm allergic!",
            "Let me double-check your order, sir.",
            "This is the third time you got it wrong!",
            "I need to speak to the manager immediately.",
            "I apologize for the confusion, let me remake it.",
        ],
        "good_outcome": "You help resolve the situation and the customer leaves happy.",
        "bad_outcome": "The customer has an allergic reaction and the cafe gets sued.",
        "loop_goal": "Understand the allergy warning and prevent the crisis.",
    },
    {
        "id": "street_emergency",
        "icon": "🚦",
        "title": "Улица: экстренная ситуация",
        "setting": "a busy street corner in the morning",
        "event": "a pedestrian gets hit by a bike and people are panicking",
        "characters": ["a witness (Mrs. Chen)", "the bike rider (Jake)", "a passing nurse (Diana)"],
        "key_phrases": [
            "Call an ambulance! Someone is hurt!",
            "I didn't see him — he came out of nowhere!",
            "I'm a nurse, let me help. Does he have any allergies?",
            "Stay calm, help is on the way.",
            "Can you tell me your name? Squeeze my hand.",
        ],
        "good_outcome": "You help coordinate the emergency response and save the pedestrian.",
        "bad_outcome": "Confusion delays help and the pedestrian's condition worsens.",
        "loop_goal": "Understand the emergency instructions and help save the pedestrian.",
    },
    {
        "id": "airport_missed_flight",
        "icon": "✈️",
        "title": "Аэропорт: пропущенный рейс",
        "setting": "an airport terminal 30 minutes before boarding",
        "event": "your flight is delayed and the gate keeps changing, announcements are in English",
        "characters": ["the gate agent (Patricia)", "a fellow passenger (Marco)", "the ground crew (Steve)"],
        "key_phrases": [
            "Attention passengers: flight 227 has been moved to gate B14.",
            "Is this the right gate for the London flight?",
            "You need to hurry, boarding closes in 10 minutes.",
            "The gate has changed again — it's now at C7.",
            "Please proceed immediately to gate C7.",
        ],
        "good_outcome": "You find the right gate and board the flight.",
        "bad_outcome": "You miss the flight and are stranded.",
        "loop_goal": "Understand the gate changes and board the flight.",
    },
    {
        "id": "hotel_lost_key",
        "icon": "🏨",
        "title": "Отель: потерянный ключ",
        "setting": "a hotel lobby late at night",
        "event": "you lost your room key and the receptionist doesn't speak your language",
        "characters": ["the receptionist (Anna)", "the night guard (Victor)", "a helpful guest (Brian)"],
        "key_phrases": [
            "I'm sorry, I can't give you a key without ID.",
            "I lost my wallet too — everything was in my bag.",
            "Can you verify your identity another way?",
            "I saw someone with a bag like that near the elevator.",
            "Let me check the security cameras for you.",
        ],
        "good_outcome": "You prove your identity and get a new key.",
        "bad_outcome": "You spend the night in the lobby without access to your room.",
        "loop_goal": "Understand the verification process and get your room key.",
    },
]

# Words that are always "known" (common English)
COMMON_WORDS = set("""
the a an and or but if then else when where why how what who whom whose
is are was were be been being have has had do does did will would could
should may might must can shall to of in on at by for with from about into
through during before after above below up down out off over under again
further here there all any both each few more most other some such no not
only own same so than too very just now also well get got make made
go went gone come came take took see saw know knew think thought say said
want wanted like liked look looked find found tell told ask asked work worked
call called try tried need needed feel felt become became leave left put
mean meant keep kept let begin began seem seemed help helped show showed
run ran move moved live lived play played believe believed bring brought
happen happened write wrote sit sat stand stood lose lost pay paid meet met
include included continue continued set learn learned change changed lead
led understand understood watch watched follow followed stop stopped create
created speak spoke read allow allowed add added grow grew open opened walk
walked win won offer offered remember remembered love loved consider
considered appear appeared buy bought wait waited serve served die died
send sent expect expected build built stay stayed fall fell cut reach
reached remain remained person place time year day week month man woman
boy girl child people way thing part life world home hand eye face night
day morning evening door room house water food book car road name color
sound work money number problem question answer idea fact case point
good bad big small new old young long short high low near far right left
yes no hello hi bye please thanks thank sorry excuse
""".split())


def build_loop_generation_prompt(template: dict, level: str, error_hints: list[str]) -> str:
    """Build prompt for AI to generate a full time loop scenario."""
    chars = ", ".join(template["characters"])
    key_phrases = "\n".join(f'  "{p}"' for p in template["key_phrases"])
    hints = f"\nAdaptive: player struggles with {', '.join(error_hints)}." if error_hints else ""

    return f"""You are a game designer creating a "time loop" scenario for an English learning game.

SCENARIO TEMPLATE:
- Setting: {template['setting']}
- Event: {template['event']}
- Characters: {chars}
- Key phrases the player must learn to understand:
{key_phrases}

Player's English level: {level}.{hints}

Generate a JSON object:
{{
  "intro": "2-3 sentence scene description in English",
  "characters": [
    {{
      "name": "character name",
      "role": "their role",
      "dialogues": ["3-5 phrases this character says during the day, in English, at {level} level"]
    }}
  ],
  "key_vocabulary": ["8-12 important words from the dialogues that the player needs to learn"],
  "critical_moment": "the key moment where understanding English changes the outcome (English, 1-2 sentences)",
  "solution": "what the player must do/say to achieve the good outcome (English, 1 sentence)"
}}

Return ONLY the JSON."""


def parse_loop_json(raw: str) -> dict | None:
    """Extract and parse JSON from AI response."""
    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start:i + 1])
                except Exception:
                    try:
                        cleaned = raw[start:i + 1].replace("\n", " ").replace("'", '"')
                        return json.loads(cleaned)
                    except Exception:
                        return None
    return None


def generate_fallback_loop(template: dict, level: str) -> dict:
    """Generate a simple loop scenario without AI."""
    names = ["Alice", "Bob", "Carol"][:len(template["characters"])]
    characters = []
    for i, role in enumerate(template["characters"]):
        dialogues = []
        for phrase in template["key_phrases"][i * 2:(i + 1) * 2]:
            dialogues.append(phrase)
        while len(dialogues) < 3:
            dialogues.append(f"I think we should figure this out together.")
        characters.append({
            "name": names[i],
            "role": role,
            "dialogues": dialogues,
        })

    key_vocab = []
    for phrase in template["key_phrases"]:
        for word in phrase.split():
            clean = re.sub(r'[^a-zA-Z]', '', word.lower())
            if len(clean) >= 4 and clean not in COMMON_WORDS:
                key_vocab.append(clean)
    key_vocab = list(set(key_vocab))[:10]

    return {
        "intro": f"You are in {template['setting']}. {template['event'].capitalize()}.",
        "characters": characters,
        "key_vocabulary": key_vocab,
        "critical_moment": template["event"],
        "solution": template["loop_goal"],
    }


def apply_fog(text: str, known_words: set[str], fog_ratio: float = 0.2) -> tuple[str, float]:
    """Apply language fog to unknown words. Returns (fogged_text, comprehension_pct)."""
    if fog_ratio <= 0:
        return text, 100.0

    words = text.split()
    total = 0
    understood = 0
    result = []

    for word in words:
        clean = re.sub(r'[^a-zA-Z]', '', word.lower())
        if len(clean) < 3:
            result.append(word)
            total += 1
            understood += 1
            continue
        total += 1
        if clean in known_words or clean in COMMON_WORDS:
            result.append(word)
            understood += 1
        else:
            if random.random() < fog_ratio:
                result.append("▓" * min(len(clean), 8))
            else:
                result.append(word)
                understood += 1

    comprehension = (understood / total * 100) if total > 0 else 100.0
    return " ".join(result), comprehension


class TimeLoopGame:
    """Time Loop Language Game popup window."""

    MAX_LOOPS = 7
    BREAK_THRESHOLD = 80.0

    def __init__(
        self,
        parent: tk.Tk,
        ollama_client=None,
        level: str = "B1",
        error_patterns: dict | None = None,
        completed_loops: list[str] | None = None,
        on_finish=None,
        voice_toolkit=None,
    ) -> None:
        self.parent = parent
        self.ollama = ollama_client
        self.level = level
        self.error_patterns = error_patterns or {}
        self.completed_loops = completed_loops or []
        self.on_finish = on_finish
        self.voice = voice_toolkit

        self.current_scenario = None
        self.current_loop_data = None
        self.loop_number = 0
        self.learned_words: set[str] = set()
        self.loop_comprehension: list[float] = []
        self.loop_actions: list[str] = []
        self.current_char_index = 0
        self.dialogue_index = 0
        self.total_comprehension = 0.0
        self.broke_loop = False
        self.waiting_for_ai = False

        self.win = tk.Toplevel(parent)
        self.win.title("🔄 Time Loop Language")
        self.win.configure(bg=BG)
        self.win.geometry("800x700")
        self.win.resizable(True, True)
        self.win.minsize(750, 620)
        self.win.grab_set()
        self.win.protocol("WM_DELETE_WINDOW", self._close)

        self._build_scenario_selection()
        self.win.focus_force()

    def _has_ollama(self) -> bool:
        return self.ollama is not None and bool(getattr(self.ollama, "model", None))

    def _get_error_hints(self) -> list[str]:
        if not self.error_patterns:
            return []
        return [k for k, _ in sorted(self.error_patterns.items(), key=lambda x: x[1], reverse=True)[:2]]

    # ─── Scenario selection ───

    def _build_scenario_selection(self) -> None:
        for child in self.win.winfo_children():
            child.destroy()

        header = tk.Frame(self.win, bg=BG, padx=20, pady=12)
        header.pack(fill="x")
        tk.Label(header, text="🔄 Time Loop Language", bg=BG, fg=TEXT_PRIMARY, font=FONT_TITLE).pack()
        tk.Label(header, text="Застрял в одном дне. Каждый цикл — шанс понять больше.", bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack()

        content = tk.Frame(self.win, bg=BG, padx=20, pady=8)
        content.pack(fill="both", expand=True)

        for sc in LOOP_SCENARIOS:
            done = sc["id"] in self.completed_loops
            card = tk.Frame(content, bg=CARD_BG, padx=16, pady=12)
            card.pack(fill="x", pady=(0, 8))
            top = tk.Frame(card, bg=CARD_BG)
            top.pack(fill="x")
            mark = "✅" if done else "🔒"
            tk.Label(top, text=f"{sc['icon']} {sc['title']} {mark}", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(side="left")
            make_button(top, "Начать", lambda s=sc: self._start_loop(s), accent=True).pack(side="right")
            tk.Label(card, text=sc["setting"], bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL, wraplength=650, justify="left").pack(anchor="w", pady=(4, 2))
            tk.Label(card, text=f"🎯 {sc['loop_goal']}", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL, wraplength=650, justify="left").pack(anchor="w")

        footer = tk.Frame(self.win, bg=BG, padx=20, pady=8)
        footer.pack(fill="x")
        tk.Label(footer, text=f"Петель разорвано: {len(self.completed_loops)}", bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack(side="left")
        make_button(footer, "Закрыть", self._close).pack(side="right")

    # ─── Start loop ───

    def _start_loop(self, template: dict) -> None:
        for child in self.win.winfo_children():
            child.destroy()

        loading = tk.Frame(self.win, bg=BG, padx=40, pady=40)
        loading.pack(fill="both", expand=True)
        tk.Label(loading, text="🔄 Генерация петли времени...", bg=BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack()
        tk.Label(loading, text="Создаём день, который повторяется", bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack(pady=(8, 0))

        import threading
        thread = threading.Thread(target=self._generate_loop_worker, args=(template,), daemon=True)
        thread.start()

    def _generate_loop_worker(self, template: dict) -> None:
        try:
            hints = self._get_error_hints()
            loop_data = None

            if self._has_ollama():
                prompt = build_loop_generation_prompt(template, self.level, hints)
                response = self.ollama.generate(prompt, model=self.ollama.model)
                loop_data = parse_loop_json(response)

            if not loop_data:
                loop_data = generate_fallback_loop(template, self.level)

            self.current_scenario = template
            self.current_loop_data = loop_data
            self.loop_number = 1
            self.learned_words = set()
            self.loop_comprehension = []
            self.loop_actions = []
            self.broke_loop = False

            self.win.after(0, self._build_loop_ui)
        except Exception as exc:
            err = str(exc)
            self.win.after(0, lambda: self._gen_error(err))

    def _gen_error(self, error: str) -> None:
        for child in self.win.winfo_children():
            child.destroy()
        tk.Label(self.win, text=f"Ошибка: {error[:100]}", bg=BG, fg=DANGER, font=FONT_BODY).pack(pady=40)
        make_button(self.win, "← Назад", self._build_scenario_selection).pack()

    # ─── Loop UI ───

    def _build_loop_ui(self) -> None:
        sc = self.current_scenario
        data = self.current_loop_data
        for child in self.win.winfo_children():
            child.destroy()

        # Header
        header = tk.Frame(self.win, bg=BG, padx=16, pady=10)
        header.pack(fill="x")
        tk.Label(header, text=f"{sc['icon']} {sc['title']}", bg=BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(side="left")
        self.loop_label = tk.Label(header, text=f"🔄 Цикл {self.loop_number}/{self.MAX_LOOPS}", bg=BG, fg=WARNING, font=FONT_HEADING)
        self.loop_label.pack(side="right")

        # Comprehension bar
        comp_frame = tk.Frame(self.win, bg=BG, padx=16)
        comp_frame.pack(fill="x")
        self.comp_label = tk.Label(comp_frame, text="Понимание: 0%", bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL)
        self.comp_label.pack(side="left")
        self.comp_bar = tk.Canvas(comp_frame, width=300, height=12, bg=CHAT_BG, highlightthickness=0)
        self.comp_bar.pack(side="left", padx=(8, 0))
        self._update_comp_bar(0)

        # Intro
        intro_frame = tk.Frame(self.win, bg=BG, padx=16, pady=4)
        intro_frame.pack(fill="x")
        tk.Label(intro_frame, text=data["intro"], bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL, wraplength=700, justify="left").pack(anchor="w")

        # Input — packed FIRST with side=bottom so it's always visible
        input_frame = tk.Frame(self.win, bg=BG, padx=16, pady=8)
        input_frame.pack(side="bottom", fill="x")
        self.input_entry = tk.Entry(input_frame, bg=CHAT_BG, fg=CHAT_FG, relief="solid", borderwidth=1, font=FONT_BODY)
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.input_entry.bind("<Return>", self._on_respond)
        make_button(input_frame, "Ответить", self._on_respond_click).pack(side="left", padx=(0, 4))
        make_button(input_frame, "🔊 Голос", self._on_voice).pack(side="left", padx=(0, 4))
        make_button(input_frame, "▶ Дальше", self._next_dialogue).pack(side="left", padx=(0, 4))
        make_button(input_frame, "🔄 Новый цикл", self._restart_loop).pack(side="left")

        self.status_label = tk.Label(input_frame, text="", bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL)
        self.status_label.pack(side="left", padx=(8, 0))

        # Dialogue area — packed after input, fills remaining space
        dlg_frame = tk.Frame(self.win, bg=BG, padx=16, pady=8)
        dlg_frame.pack(fill="both", expand=True)
        self.dialogue_text = tk.Text(dlg_frame, wrap="word", bg=CHAT_BG, fg=CHAT_FG, font=FONT_BODY, relief="flat", height=10, padx=12, pady=12)
        self.dialogue_text.pack(fill="both", expand=True)
        self.dialogue_text.configure(state="disabled")
        self.dialogue_text.tag_config("npc", foreground="#4a9eff" if is_dark() else "#0066cc", font=("SF Pro Display", 12, "bold"))
        self.dialogue_text.tag_config("player", foreground="#50c878" if is_dark() else "#008844", font=("SF Pro Display", 12, "bold"))
        self.dialogue_text.tag_config("system", foreground=TEXT_MUTED, font=FONT_SMALL)
        self.dialogue_text.tag_config("learned", foreground=SUCCESS, font=FONT_SMALL)

        # Start the day
        self.current_char_index = 0
        self.dialogue_index = 0
        self._append_dialogue("system", f"📅 День начинается снова. Цикл {self.loop_number}.\n")
        self._append_dialogue("system", f"🎯 Цель: {self.current_scenario['loop_goal']}\n\n")
        self._show_next_dialogue()

    def _append_dialogue(self, tag: str, text: str) -> None:
        self.dialogue_text.configure(state="normal")
        self.dialogue_text.insert("end", text, tag)
        self.dialogue_text.configure(state="disabled")
        self.dialogue_text.see("end")

    def _show_next_dialogue(self) -> None:
        data = self.current_loop_data
        chars = data["characters"]

        if self.current_char_index >= len(chars):
            self._end_loop_day()
            return

        char = chars[self.current_char_index]
        if self.dialogue_index >= len(char["dialogues"]):
            self.current_char_index += 1
            self.dialogue_index = 0
            self._show_next_dialogue()
            return

        line = char["dialogues"][self.dialogue_index]
        fog_ratio = max(0.05, 0.35 - (self.loop_number - 1) * 0.05)
        fogged, comp = apply_fog(line, self.learned_words, fog_ratio)

        self._append_dialogue("npc", f"{char['name']} ({char['role']}):\n")
        self._append_dialogue("npc", f"  \"{fogged}\"\n\n")

        self.total_comprehension = comp
        self._update_comp_bar(comp)
        self.status_label.config(text=f"Понимание: {comp:.0f}%")

        # Track words from this dialogue
        for word in line.lower().split():
            clean = re.sub(r'[^a-zA-Z]', '', word)
            if len(clean) >= 4 and clean not in COMMON_WORDS:
                self.learned_words.add(clean)

        self.input_entry.focus_set()

    def _next_dialogue(self) -> None:
        self.dialogue_index += 1
        self._show_next_dialogue()

    def _on_respond(self, event=None) -> None:
        self._on_respond_click()

    def _on_respond_click(self) -> None:
        text = self.input_entry.get().strip()
        if not text:
            return
        self.input_entry.delete(0, "end")
        self._append_dialogue("player", f"Ты: {text}\n\n")
        self.loop_actions.append(text)

        # Simple AI response or fallback
        if self._has_ollama():
            self.waiting_for_ai = True
            self.input_entry.config(state="disabled")
            self.status_label.config(text="NPC думает...")
            import threading
            thread = threading.Thread(target=self._ai_response_worker, args=(text,), daemon=True)
            thread.start()
        else:
            self._fallback_response(text)

    def _ai_response_worker(self, player_text: str) -> None:
        try:
            data = self.current_loop_data
            char = data["characters"][self.current_char_index] if self.current_char_index < len(data["characters"]) else data["characters"][-1]
            prompt = (
                f"You are {char['name']}, the {char['role']}. "
                f"Setting: {self.current_scenario['setting']}. "
                f"Event: {self.current_scenario['event']}. "
                f"Player level: {self.level}. "
                f"The player said: \"{player_text}\". "
                f"Respond in character, 1-2 sentences, at {self.level} English level."
            )
            response = self.ollama.generate(prompt, model=self.ollama.model)
            self.win.after(0, lambda: self._handle_ai_response(response))
        except Exception as exc:
            err = str(exc)
            self.win.after(0, lambda: self._handle_ai_response(f"I see. {self._fallback_response_text()}"))

    def _fallback_response_text(self) -> str:
        options = [
            "That makes sense. Let's continue.",
            "I understand. We need to focus on the problem.",
            "Okay, let me think about that.",
            "Right. We should figure this out together.",
        ]
        return random.choice(options)

    def _fallback_response(self, player_text: str) -> None:
        resp = self._fallback_response_text()
        fogged, comp = apply_fog(resp, self.learned_words, max(0.05, 0.35 - (self.loop_number - 1) * 0.05))
        self._append_dialogue("npc", f"  \"{fogged}\"\n\n")
        self.total_comprehension = comp
        self._update_comp_bar(comp)

    def _handle_ai_response(self, response: str) -> None:
        self.waiting_for_ai = False
        self.input_entry.config(state="normal")
        self.status_label.config(text="")
        fogged, comp = apply_fog(response, self.learned_words, max(0.05, 0.35 - (self.loop_number - 1) * 0.05))
        self._append_dialogue("npc", f"  \"{fogged}\"\n\n")
        self.total_comprehension = comp
        self._update_comp_bar(comp)

    def _on_voice(self) -> None:
        if not self.voice:
            self.status_label.config(text="❌ Голосовой модуль недоступен")
            return
        self.status_label.config(text="🎤 Запись...")
        try:
            result = self.voice.transcribe("en-US", seconds=8)
            text = result.get("transcript", "") if isinstance(result, dict) else ""
            if text:
                self.input_entry.delete(0, "end")
                self.input_entry.insert(0, text)
                self.status_label.config(text="✅ Распознано")
            else:
                self.status_label.config(text="❌ Не расслышал")
        except Exception:
            self.status_label.config(text="❌ Ошибка")

    def _update_comp_bar(self, pct: float) -> None:
        self.comp_bar.delete("all")
        filled = int(pct / 100 * 296)
        color = SUCCESS if pct >= self.BREAK_THRESHOLD else (WARNING if pct >= 50 else DANGER)
        self.comp_bar.create_rectangle(2, 2, 2 + filled, 10, fill=color, outline="")
        self.comp_bar.create_rectangle(2, 2, 298, 10, outline=BORDER)
        self.comp_label.config(text=f"Понимание: {pct:.0f}%")

    # ─── End of loop day ───

    def _end_loop_day(self) -> None:
        avg_comp = self.total_comprehension
        self.loop_comprehension.append(avg_comp)

        self._append_dialogue("system", f"\n{'─' * 40}\n")
        self._append_dialogue("system", f"📅 Конец дня {self.loop_number}. Понимание: {avg_comp:.0f}%\n")

        # Show newly learned words
        new_words = [w for w in self.learned_words if len(w) >= 4 and w not in COMMON_WORDS]
        if new_words:
            self._append_dialogue("learned", f"📖 Слов в памяти: {len(new_words)}\n")
            sample = random.sample(new_words, min(8, len(new_words)))
            self._append_dialogue("learned", f"   {', '.join(sample)}\n")

        if avg_comp >= self.BREAK_THRESHOLD:
            self._break_loop()
        elif self.loop_number >= self.MAX_LOOPS:
            self._fail_loop()
        else:
            self._append_dialogue("system", f"\n🔄 День повторяется... Нажми «Новый цикл» для следующей попытки.\n")
            self.status_label.config(text=f"Цикл {self.loop_number} завершён. Понимание: {avg_comp:.0f}%")

    def _restart_loop(self) -> None:
        if self.waiting_for_ai:
            return
        self.loop_number += 1
        self.loop_actions = []
        self.total_comprehension = 0.0
        self.current_char_index = 0
        self.dialogue_index = 0

        # Clear dialogue area
        self.dialogue_text.configure(state="normal")
        self.dialogue_text.delete("1.0", "end")
        self.dialogue_text.configure(state="disabled")

        self.loop_label.config(text=f"🔄 Цикл {self.loop_number}/{self.MAX_LOOPS}")
        self._append_dialogue("system", f"📅 День {self.loop_number} начинается.\n")
        self._append_dialogue("system", f"🧠 Память сохранена: {len(self.learned_words)} слов\n\n")
        self._show_next_dialogue()

    def _break_loop(self) -> None:
        self.broke_loop = True
        self._append_dialogue("system", f"\n🎉 ПЕТЛЯ РАЗОРВАНА!\n")
        self._append_dialogue("system", f"Ты понял(а) {self.total_comprehension:.0f}% диалогов за {self.loop_number} циклов.\n")
        self._append_dialogue("system", f"📖 {self.current_loop_data.get('solution', 'Ты справился!')}\n\n")

        score = int(100 + (self.MAX_LOOPS - self.loop_number + 1) * 20 + len(self.learned_words) * 2)

        if self.on_finish:
            self.on_finish(self.current_scenario["id"], True, score, list(self.learned_words))

        # Result buttons
        result_frame = tk.Frame(self.win, bg=BG, padx=16, pady=12)
        result_frame.pack(fill="x")
        tk.Label(result_frame, text=f"⭐ Очки: {score}", bg=BG, fg=ACCENT, font=FONT_HEADING).pack(side="left")
        make_button(result_frame, "🔄 Новая петля", self._build_scenario_selection, accent=True).pack(side="right", padx=(0, 8))
        make_button(result_frame, "Закрыть", self._close).pack(side="right")

    def _fail_loop(self) -> None:
        self._append_dialogue("system", f"\n💀 Петля не разорвана за {self.MAX_LOOPS} циклов.\n")
        self._append_dialogue("system", f"Финальное понимание: {self.total_comprehension:.0f}%\n")
        self._append_dialogue("system", f"Нужно {self.BREAK_THRESHOLD:.0f}% для разрыва петли.\n\n")

        score = int(len(self.learned_words) * 2 + self.total_comprehension)

        if self.on_finish:
            self.on_finish(self.current_scenario["id"], False, score, list(self.learned_words))

        result_frame = tk.Frame(self.win, bg=BG, padx=16, pady=12)
        result_frame.pack(fill="x")
        tk.Label(result_frame, text=f"Очки: {score}", bg=BG, fg=TEXT_SECONDARY, font=FONT_HEADING).pack(side="left")
        make_button(result_frame, "🔄 Попробовать снова", self._build_scenario_selection, accent=True).pack(side="right", padx=(0, 8))
        make_button(result_frame, "Закрыть", self._close).pack(side="right")

    def _close(self) -> None:
        self.win.grab_release()
        self.win.destroy()
