"""Language Survival Game — survive in the world where English is your only weapon.

Scenarios immerse the player in high-stakes situations (airport, bar, job interview,
apocalypse) where they must use English to progress. NPC responses are generated
by the local Ollama model. Timer pressure, consequences, and adaptive difficulty
based on the player's error patterns.
"""

from __future__ import annotations

import json
import random
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

# ─── Scenario definitions ───

SCENARIOS = [
    {
        "id": "airport_lost_baggage",
        "title": "✈️ Аэропорт: потерянный багаж",
        "icon": "✈️",
        "description": "Ты прилетел в Лондон. Багажа нет на ленте. Нужно решить проблему у стойки.",
        "goal": "Найди свой багаж, не разозлив персонал.",
        "npc_role": "You are a busy, slightly irritated airport customer service agent at Heathrow. You deal with hundreds of people daily. Be brief, professional, but impatient. If the player is rude, you refuse to help. If they are polite and clear, you help them.",
        "npc_greeting": "Next! How can I help you?",
        "success_keywords": ["baggage", "luggage", "lost", "missing", "claim", "tag", "receipt"],
        "fail_if_rude": True,
        "max_turns": 6,
        "timer_seconds": 26,
    },
    {
        "id": "bar_small_talk",
        "title": "🍺 Бар: знакомство",
        "icon": "🍺",
        "description": "Ты в баре в Нью-Йорке. Рядом сидит интересный человек. Начни разговор.",
        "goal": "Заведи разговор и поддержи его минимум 5 реплик.",
        "npc_role": "You are a friendly stranger at a bar in NYC. You're open to conversation but will lose interest if the player can't keep small talk going. Be casual, use slang, react naturally.",
        "npc_greeting": "*looks up from drink* Oh, hey there. You alone tonight?",
        "success_keywords": ["hello", "hi", "name", "from", "work", "live", "drink", "nice", "good"],
        "fail_if_rude": False,
        "max_turns": 5,
        "timer_seconds": 20,
    },
    {
        "id": "job_interview",
        "title": "💼 Собеседование на работу",
        "icon": "💼",
        "description": "Собеседование на позицию в международной компании. HR говорит только по-английски.",
        "goal": "Пройди собеседование, ответь на 5 вопросов HR.",
        "npc_role": "You are a professional HR manager conducting a job interview. Ask standard interview questions one at a time. Evaluate answers: if the player gives vague answers, ask follow-up. If they are specific and confident, move to the next question. Be professional but not cold.",
        "npc_greeting": "Good morning! Thank you for coming in today. Let's start — tell me a bit about yourself.",
        "success_keywords": ["experience", "skills", "team", "project", "work", "year", "company", "learn", "challenge"],
        "fail_if_rude": True,
        "max_turns": 5,
        "timer_seconds": 39,
    },
    {
        "id": "apocalypse_survivor",
        "title": "☢️ Апокалипсис: переговоры с выжившими",
        "icon": "☢️",
        "description": "После катастрофы ты встретил группу выживших. Они не пускают тебя в убежище.",
        "goal": "Убеди выживших пустить тебя в убежище. Докажи свою полезность.",
        "npc_role": "You are the leader of a survivor group in a post-apocalyptic world. You are suspicious of strangers. The player must convince you they are useful and not a threat. Be tough but fair. If they are aggressive, you kick them out. If they offer skills or resources, you consider letting them in.",
        "npc_greeting": "*raises weapon* Stop right there. Who are you? Why should we let you in?",
        "success_keywords": ["help", "skill", "doctor", "medic", "food", "water", "engineer", "fight", "safe", "trust", "useful"],
        "fail_if_rude": True,
        "max_turns": 5,
        "timer_seconds": 26,
    },
    {
        "id": "restaurant_problem",
        "title": "🍽️ Ресторан: проблема с заказом",
        "icon": "🍽️",
        "description": "Ты в ресторане. Официант принёс не то, что ты заказывал. Нужно решить проблему.",
        "goal": "Реши проблему с заказом вежливо, но твёрдо.",
        "npc_role": "You are a waiter in a busy restaurant. You brought the wrong dish. If the player is rude, you get defensive. If they are polite but clear, you fix the mistake. Be busy and slightly stressed.",
        "npc_greeting": "Here you go — the fish and chips. Enjoy!",
        "success_keywords": ["order", "wrong", "ordered", "different", "change", "mistake", "sorry", "excuse", "actually"],
        "fail_if_rude": True,
        "max_turns": 4,
        "timer_seconds": 20,
    },
    {
        "id": "doctor_visit",
        "title": "🏥 У врача: опиши симптомы",
        "icon": "🏥",
        "description": "Ты у врача в англоязычной стране. Нужно описать свои симптомы.",
        "goal": "Опиши симптомы так, чтобы врач понял и назначил лечение.",
        "npc_role": "You are a doctor seeing a patient who speaks English as a second language. Ask about symptoms, duration, pain level. Be patient but need clear answers to diagnose. Ask one question at a time.",
        "npc_greeting": "Hello, I'm Dr. Miller. What brings you in today?",
        "success_keywords": ["pain", "hurt", "fever", "headache", "stomach", "throat", "cough", "days", "week", "feel", "sick", "dizzy", "nausea"],
        "fail_if_rude": False,
        "max_turns": 5,
        "timer_seconds": 33,
    },
]


def build_npc_prompt(scenario: dict, player_level: str, error_hints: list[str], turn: int, max_turns: int) -> str:
    """Build the system prompt for the NPC AI."""
    hints = ""
    if error_hints:
        hints = f"\n\nADAPTIVE: The player tends to struggle with: {', '.join(error_hints)}. Naturally incorporate these into your dialogue to give them more practice."

    return (
        f"{scenario['npc_role']}\n\n"
        f"Player's English level: {player_level}.\n"
        f"This is turn {turn} of {max_turns}.\n"
        f"Respond IN CHARACTER as the NPC. Keep responses short (1-3 sentences).\n"
        f"React to what the player says. If they make grammar mistakes, understand them anyway "
        f"but stay in character. If they are rude, react accordingly.\n"
        f"At the very end of your response, on a new line, add:\n"
        f"[RATING: X/10] where X is how well the player handled this interaction (1=terrible, 10=perfect).\n"
        f"[DONE] if the scenario goal is achieved or failed beyond recovery.{hints}"
    )


def extract_rating(text: str) -> int:
    """Extract [RATING: X/10] from NPC response."""
    import re
    m = re.search(r'\[RATING:\s*(\d+)\s*/\s*10\]', text)
    return int(m.group(1)) if m else 0


def is_done(text: str) -> bool:
    return "[DONE]" in text


def clean_npc_text(text: str) -> str:
    """Remove metadata tags from NPC response for display."""
    import re
    text = re.sub(r'\[RATING:\s*\d+\s*/\s*10\]', '', text)
    text = text.replace("[DONE]", "")
    return text.strip()


class SurvivalGame:
    """Language Survival Game popup window."""

    def __init__(
        self,
        parent: tk.Tk,
        ollama_client=None,
        level: str = "B1",
        error_patterns: dict | None = None,
        completed_scenes: list[str] | None = None,
        on_finish=None,
        voice_toolkit=None,
    ) -> None:
        self.parent = parent
        self.ollama = ollama_client
        self.level = level
        self.error_patterns = error_patterns or {}
        self.completed_scenes = completed_scenes or []
        self.on_finish = on_finish
        self.voice = voice_toolkit

        self.current_scenario = None
        self.turn = 0
        self.ratings: list[int] = []
        self.player_words: list[str] = []
        self.timer_id = None
        self.time_left = 0
        self.waiting_for_npc = False

        self.win = tk.Toplevel(parent)
        self.win.title("Language Survival Game")
        self.win.configure(bg=BG)
        self.win.geometry("760x680")
        self.win.resizable(True, True)
        self.win.minsize(700, 600)
        self.win.grab_set()
        self.win.protocol("WM_DELETE_WINDOW", self._close)

        self._build_scene_selection()
        self.win.focus_force()

    def _get_error_hints(self) -> list[str]:
        """Get error hints for adaptive NPC dialogue."""
        if not self.error_patterns:
            return []
        top = sorted(self.error_patterns.items(), key=lambda x: x[1], reverse=True)[:2]
        return [k for k, _ in top]

    # ─── Scene selection screen ───

    def _build_scene_selection(self) -> None:
        for child in self.win.winfo_children():
            child.destroy()

        header = tk.Frame(self.win, bg=BG, padx=20, pady=12)
        header.pack(fill="x")
        tk.Label(header, text="🌍 Language Survival Game", bg=BG, fg=TEXT_PRIMARY, font=FONT_TITLE).pack()
        tk.Label(header, text="Выживи в мире, где без английского — ты труп.", bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack()

        scroll = tk.Frame(self.win, bg=BG, padx=20, pady=8)
        scroll.pack(fill="both", expand=True)

        for scenario in SCENARIOS:
            done = scenario["id"] in self.completed_scenes
            card = tk.Frame(scroll, bg=CARD_BG, padx=16, pady=12)
            card.pack(fill="x", pady=(0, 8))
            card.bind("<Enter>", lambda e, c=card: c.config(bg=BORDER))
            card.bind("<Leave>", lambda e, c=card: c.config(bg=CARD_BG))

            top = tk.Frame(card, bg=CARD_BG)
            top.pack(fill="x")
            mark = "✅" if done else "🔒"
            tk.Label(top, text=f"{scenario['icon']} {scenario['title']} {mark}", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(side="left")
            make_button(top, "Играть", lambda s=scenario: self._start_scene(s)).pack(side="right")

            tk.Label(card, text=scenario["description"], bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL, wraplength=600, justify="left").pack(anchor="w", pady=(4, 2))
            tk.Label(card, text=f"🎯 {scenario['goal']}", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL, wraplength=600, justify="left").pack(anchor="w")

        footer = tk.Frame(self.win, bg=BG, padx=20, pady=8)
        footer.pack(fill="x")
        completed = len(self.completed_scenes)
        tk.Label(footer, text=f"Пройдено: {completed} из {len(SCENARIOS)} сцен", bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack(side="left")
        make_button(footer, "Закрыть", self._close).pack(side="right")

    # ─── Scene gameplay screen ───

    def _start_scene(self, scenario: dict) -> None:
        self.current_scenario = scenario
        self.turn = 0
        self.ratings = []
        self.player_words = []
        self.waiting_for_npc = False

        for child in self.win.winfo_children():
            child.destroy()

        # Header
        header = tk.Frame(self.win, bg=BG, padx=16, pady=10)
        header.pack(fill="x")
        tk.Label(header, text=f"{scenario['icon']} {scenario['title']}", bg=BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(side="left")
        self.scene_timer_label = tk.Label(header, text="", bg=BG, fg=WARNING, font=FONT_HEADING)
        self.scene_timer_label.pack(side="right")
        self.scene_turn_label = tk.Label(header, text="", bg=BG, fg=TEXT_MUTED, font=FONT_SMALL)
        self.scene_turn_label.pack(side="right", padx=(0, 12))

        # Goal banner
        goal_frame = tk.Frame(self.win, bg=BG, padx=16)
        goal_frame.pack(fill="x")
        tk.Label(goal_frame, text=f"🎯 {scenario['goal']}", bg=BG, fg=ACCENT, font=FONT_SMALL).pack(anchor="w")

        # Input area — packed FIRST with side=bottom so it's always visible
        input_frame = tk.Frame(self.win, bg=BG, padx=16, pady=8)
        input_frame.pack(side="bottom", fill="x")
        self.input_entry = tk.Entry(input_frame, bg=CHAT_BG, fg=CHAT_FG, relief="solid", borderwidth=1, font=FONT_BODY)
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.input_entry.bind("<Return>", self._on_submit)
        make_button(input_frame, "Отправить", self._on_submit_click).pack(side="left", padx=(0, 4))
        make_button(input_frame, "🔊 Голос", self._on_voice_input).pack(side="left", padx=(0, 4))
        make_button(input_frame, "⏭ Пропустить", self._skip_scene).pack(side="left")

        # Footer
        footer = tk.Frame(self.win, bg=BG, padx=16, pady=4)
        footer.pack(side="bottom", fill="x")
        self.status_label = tk.Label(footer, text="", bg=BG, fg=TEXT_MUTED, font=FONT_SMALL)
        self.status_label.pack(anchor="w")

        # Dialogue area — packed after input, fills remaining space
        dlg_frame = tk.Frame(self.win, bg=BG, padx=16, pady=8)
        dlg_frame.pack(fill="both", expand=True)
        self.dialogue_text = tk.Text(dlg_frame, wrap="word", bg=CHAT_BG, fg=CHAT_FG, font=FONT_BODY, relief="flat", borderwidth=0, padx=12, pady=12)
        self.dialogue_text.pack(fill="both", expand=True)
        self.dialogue_text.configure(state="disabled")

        # Tag styles
        _dark = is_dark()
        self.dialogue_text.tag_config("npc", foreground="#4a9eff" if _dark else "#0066cc", font=("SF Pro Display", 13, "bold"))
        self.dialogue_text.tag_config("player", foreground="#50c878" if _dark else "#008844", font=("SF Pro Display", 13, "bold"))
        self.dialogue_text.tag_config("system", foreground=TEXT_MUTED, font=FONT_SMALL)
        self.dialogue_text.tag_config("rating", foreground=WARNING, font=FONT_SMALL)

        # Footer (back to scenes button)
        footer2 = tk.Frame(self.win, bg=BG, padx=16, pady=4)
        footer2.pack(side="bottom", fill="x")
        make_button(footer2, "← К сценам", self._back_to_scenes).pack(side="left")

        # Start with NPC greeting
        self._append_dialogue("npc", f"NPC: {scenario['npc_greeting']}\n\n")
        self.turn = 1
        self._update_turn_label()
        self._start_timer(scenario["timer_seconds"])
        self.input_entry.focus_set()

    def _append_dialogue(self, tag: str, text: str) -> None:
        self.dialogue_text.configure(state="normal")
        self.dialogue_text.insert("end", text, tag)
        self.dialogue_text.configure(state="disabled")
        self.dialogue_text.see("end")

    def _update_turn_label(self) -> None:
        if self.current_scenario:
            self.scene_turn_label.config(text=f"Реплика {self.turn}/{self.current_scenario['max_turns']}")

    def _start_timer(self, seconds: int) -> None:
        self.time_left = seconds
        self._tick_timer()

    def _tick_timer(self) -> None:
        if self.waiting_for_npc:
            return
        self.scene_timer_label.config(text=f"⏱ {self.time_left}")
        if self.time_left <= 5:
            self.scene_timer_label.config(fg=DANGER)
        else:
            self.scene_timer_label.config(fg=WARNING)

        if self.time_left <= 0:
            self._time_up()
            return

        self.time_left -= 1
        self.timer_id = self.win.after(1000, self._tick_timer)

    def _time_up(self) -> None:
        if self.waiting_for_npc:
            return
        self._append_dialogue("system", "\n⏰ Время вышло! NPC теряет терпение...\n\n")
        self._send_to_npc("...*silence*...")

    def _on_submit(self, event=None) -> None:
        self._on_submit_click()

    def _on_submit_click(self) -> None:
        if self.waiting_for_npc:
            return
        text = self.input_entry.get().strip()
        if not text:
            return
        if self.timer_id:
            try:
                self.win.after_cancel(self.timer_id)
            except Exception:
                pass

        self.input_entry.delete(0, "end")
        self._append_dialogue("player", f"Ты: {text}\n\n")
        self.player_words.extend(text.lower().split())
        self._send_to_npc(text)

    def _on_voice_input(self) -> None:
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
            self.status_label.config(text="❌ Ошибка записи")

    def _send_to_npc(self, player_text: str) -> None:
        self.waiting_for_npc = True
        self.status_label.config(text="NPC думает...")
        self.input_entry.config(state="disabled")

        import threading
        thread = threading.Thread(target=self._npc_response_worker, args=(player_text,), daemon=True)
        thread.start()

    def _npc_response_worker(self, player_text: str) -> None:
        try:
            hints = self._get_error_hints()
            system_prompt = build_npc_prompt(
                self.current_scenario, self.level, hints,
                self.turn, self.current_scenario["max_turns"],
            )
            full_prompt = f"{system_prompt}\n\nPlayer says: \"{player_text}\"\n\nRespond as NPC:"

            if self.ollama and self.ollama.model:
                response = self.ollama.generate(full_prompt, model=self.ollama.model)
            else:
                response = self._fallback_npc_response(player_text)

            self.win.after(0, lambda: self._handle_npc_response(response))
        except Exception as exc:
            err_msg = str(exc)
            self.win.after(0, lambda: self._handle_npc_response(f"Error: {err_msg}"))

    def _fallback_npc_response(self, player_text: str) -> str:
        """Simple fallback when no Ollama model is available."""
        text = player_text.lower()
        scenario = self.current_scenario
        keywords = scenario["success_keywords"]

        if any(kw in text for kw in keywords):
            rating = 7
            responses = [
                "Alright, I understand. Let me help you with that.",
                "Okay, that makes sense. Let's see what we can do.",
                "Sure, I can help. Just a moment.",
            ]
        elif len(text.split()) < 3:
            rating = 3
            responses = [
                "I'm sorry, could you be more specific?",
                "I need more details than that. Can you explain?",
                "Pardon? Could you say that again, more clearly?",
            ]
        else:
            rating = 5
            responses = [
                "Hmm, I'm not sure I follow. Could you rephrase?",
                "I think I understand, but let me ask you something else.",
                "Okay... let's move on. What else?",
            ]

        resp = random.choice(responses)
        return f"{resp}\n[RATING: {rating}/10]"

    def _handle_npc_response(self, raw_response: str) -> None:
        self.waiting_for_npc = False
        self.input_entry.config(state="normal")
        self.status_label.config(text="")

        rating = extract_rating(raw_response)
        if rating:
            self.ratings.append(rating)

        done = is_done(raw_response)
        clean = clean_npc_text(raw_response)

        if "Error:" in raw_response:
            self._append_dialogue("system", f"⚠️ {raw_response}\n\n")
        else:
            self._append_dialogue("npc", f"NPC: {clean}\n")
            if rating:
                self._append_dialogue("rating", f"[Оценка: {rating}/10]\n\n")
            else:
                self._append_dialogue("npc", "\n")

        if done or self.turn >= self.current_scenario["max_turns"]:
            self._scene_complete()
        else:
            self.turn += 1
            self._update_turn_label()
            self._start_timer(self.current_scenario["timer_seconds"])
            self.input_entry.focus_set()

    def _scene_complete(self) -> None:
        if self.timer_id:
            try:
                self.win.after_cancel(self.timer_id)
            except Exception:
                pass

        avg_rating = sum(self.ratings) / len(self.ratings) if self.ratings else 0
        passed = avg_rating >= 5.0

        self._append_dialogue("system", "\n" + "─" * 50 + "\n")
        if passed:
            self._append_dialogue("system", f"🎉 СЦЕНА ПРОЙДЕНА! Средняя оценка: {avg_rating:.1f}/10\n")
        else:
            self._append_dialogue("system", f"💀 СЦЕНА ПРОВАЛЕНА. Средняя оценка: {avg_rating:.1f}/10\n")
        self._append_dialogue("system", f"Слов использовано: {len(self.player_words)}\n")

        if self.on_finish:
            self.on_finish(self.current_scenario["id"], passed, avg_rating, self.player_words)

        # Show result buttons
        result_frame = tk.Frame(self.win, bg=BG, padx=16, pady=12)
        result_frame.pack(fill="x")
        if passed:
            make_button(result_frame, "→ Следующая сцена", self._next_scene, accent=True).pack(side="left", padx=(0, 8))
        make_button(result_frame, "🔄 Заново", lambda: self._start_scene(self.current_scenario)).pack(side="left", padx=(0, 8))
        make_button(result_frame, "← К сценам", self._back_to_scenes).pack(side="left")

    def _next_scene(self) -> None:
        current_idx = SCENARIOS.index(self.current_scenario) if self.current_scenario in SCENARIOS else 0
        next_idx = (current_idx + 1) % len(SCENARIOS)
        self._start_scene(SCENARIOS[next_idx])

    def _skip_scene(self) -> None:
        if self.timer_id:
            try:
                self.win.after_cancel(self.timer_id)
            except Exception:
                pass
        self._back_to_scenes()

    def _back_to_scenes(self) -> None:
        if self.timer_id:
            try:
                self.win.after_cancel(self.timer_id)
            except Exception:
                pass
        self._build_scene_selection()

    def _close(self) -> None:
        if self.timer_id:
            try:
                self.win.after_cancel(self.timer_id)
            except Exception:
                pass
        self.win.grab_release()
        self.win.destroy()
