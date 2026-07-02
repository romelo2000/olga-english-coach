"""
Taboo Talks — word guessing game with AI.

Round 1: Olga describes a word (without saying it or 3 taboo words).
         The player guesses.
Round 2: The player describes a word. Olga guesses.

Powered by local Ollama model.
"""

import tkinter as tk
from tkinter import ttk
import threading
import random
import time

from ui_theme import (
    BG, CARD_BG, CHAT_BG, CHAT_FG, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, ACCENT_HOVER, SUCCESS, WARNING, DANGER, BORDER,
    FONT_TITLE, FONT_HEADING, FONT_BODY, FONT_SMALL,
    is_dark,
)

_WORD_DATA = {
    "B1": [
        ("adventure", ["exciting", "danger", "journey"]),
        ("kitchen", ["cook", "food", "room"]),
        ("weather", ["rain", "sun", "sky"]),
        ("holiday", ["vacation", "travel", "rest"]),
        ("memory", ["remember", "past", "brain"]),
        ("decision", ["choose", "option", "think"]),
        ("neighbor", ["live", "next", "house"]),
        ("healthy", ["good", "body", "food"]),
        ("meeting", ["talk", "work", "people"]),
        ("comfortable", ["relax", "soft", "easy"]),
        ("furniture", ["table", "chair", "home"]),
        ("experience", ["learn", "life", "do"]),
        ("tradition", ["family", "old", "custom"]),
        ("performance", ["show", "act", "stage"]),
        ("relationship", ["people", "connect", "love"]),
    ],
    "B2": [
        ("accomplishment", ["achieve", "success", "goal"]),
        ("negotiate", ["talk", "agree", "deal"]),
        ("perspective", ["view", "angle", "see"]),
        ("sustainable", ["environment", "long", "green"]),
        ("vulnerable", ["weak", "hurt", "open"]),
        ("comprehensive", ["complete", "all", "thorough"]),
        ("elaborate", ["detail", "explain", "complex"]),
        ("fundamental", ["basic", "core", "essential"]),
        ("legitimate", ["legal", "valid", "real"]),
        ("manipulate", ["control", "influence", "trick"]),
        ("reluctant", ["hesitate", "unwilling", "slow"]),
        ("subsequent", ["after", "follow", "next"]),
        ("threshold", ["limit", "boundary", "start"]),
        ("feasible", ["possible", "doable", "realistic"]),
        ("genuine", ["real", "authentic", "true"]),
    ],
    "C1": [
        ("ephemeral", ["brief", "temporary", "short"]),
        ("fastidious", ["careful", "precise", "fussy"]),
        ("gregarious", ["social", "outgoing", "friendly"]),
        ("juxtapose", ["compare", "contrast", "place"]),
        ("mellifluous", ["sweet", "sound", "flow"]),
        ("nostalgia", ["past", "memory", "longing"]),
        ("paradigm", ["model", "pattern", "example"]),
        ("ubiquitous", ["everywhere", "common", "present"]),
        ("capricious", ["changeable", "unpredictable", "fickle"]),
        ("deleterious", ["harmful", "damaging", "bad"]),
    ],
}


class TabooGame:
    """Taboo Talks — AI-powered word guessing game."""

    def __init__(
        self,
        parent: tk.Tk,
        ollama_client=None,
        level: str = "B1",
        on_finish=None,
    ) -> None:
        self.parent = parent
        self.ollama = ollama_client
        self.level = level
        self.on_finish = on_finish
        self.score = 0
        self.words_guessed = 0
        self.round_num = 0
        self.max_rounds = 6
        self.current_word = ""
        self.current_taboo = []
        self.round_role = "guesser"  # "guesser" = Olga describes, player guesses
        self.start_time = time.time()
        self.used_words = set()

        self._build_ui()
        self._next_round()

    def _build_ui(self) -> None:
        self.win = tk.Toplevel(self.parent)
        self.win.title("🤐 Taboo Talks")
        self.win.geometry("560x580")
        self.win.resizable(True, True)
        self.win.transient(self.parent)
        self.win.grab_set()
        self.win.configure(bg=BG)

        # Header
        header = tk.Frame(self.win, bg=BG, padx=16, pady=12)
        header.pack(fill="x")
        tk.Label(header, text="🤐 Taboo Talks", bg=BG, fg=ACCENT, font=FONT_TITLE).pack(side="left")
        self.score_label = tk.Label(header, text="Счёт: 0", bg=BG, fg=TEXT_SECONDARY, font=FONT_HEADING)
        self.score_label.pack(side="right")
        self.round_label = tk.Label(header, text="Раунд 1/6", bg=BG, fg=TEXT_MUTED, font=FONT_SMALL)
        self.round_label.pack(side="right", padx=(0, 12))

        # Role indicator
        self.role_label = tk.Label(self.win, text="", bg=BG, fg=ACCENT, font=FONT_HEADING)
        self.role_label.pack(fill="x", padx=16, pady=(0, 4))

        # Description area
        desc_card = tk.Frame(self.win, bg=CARD_BG, padx=16, pady=12)
        desc_card.pack(fill="x", padx=16, pady=(0, 8))
        tk.Label(desc_card, text="📖 Описание:", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL).pack(anchor="w")
        self.desc_text = tk.Text(desc_card, wrap="word", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_BODY,
                                 height=4, relief="flat", state="disabled")
        self.desc_text.pack(fill="x", pady=(4, 0))

        # Input
        input_frame = tk.Frame(self.win, bg=BG, padx=16, pady=8)
        input_frame.pack(fill="x")
        self.entry = tk.Entry(input_frame, bg=CHAT_BG, fg=TEXT_PRIMARY, font=FONT_BODY,
                              relief="solid", borderwidth=1, width=25)
        self.entry.pack(side="left", padx=(0, 8))
        self.entry.bind("<Return>", lambda e: self._submit_guess())
        self.entry.focus_set()

        self.submit_btn = tk.Button(
            input_frame, text="Ответить", bg=ACCENT, fg="white", font=FONT_BODY,
            relief="flat", cursor="hand2", command=self._submit_guess,
        )
        self.submit_btn.pack(side="left", padx=(0, 4))

        self.skip_btn = tk.Button(
            input_frame, text="Пропустить", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_SMALL,
            relief="flat", cursor="hand2", command=self._skip_round,
        )
        self.skip_btn.pack(side="left")

        # Status
        self.status_label = tk.Label(self.win, text="", bg=BG, fg=TEXT_MUTED, font=FONT_SMALL)
        self.status_label.pack(fill="x", padx=16, pady=(4, 8))

        # Close
        bottom = tk.Frame(self.win, bg=BG, padx=16, pady=8)
        bottom.pack(fill="x")
        tk.Button(bottom, text="Закрыть", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_SMALL,
                  relief="flat", cursor="hand2", command=self._close).pack(side="right")

    def _pick_word(self) -> tuple[str, list[str]] | None:
        pool = _WORD_DATA.get(self.level, _WORD_DATA["B1"])
        available = [(w, t) for w, t in pool if w not in self.used_words]
        if not available:
            return None
        choice = random.choice(available)
        self.used_words.add(choice[0])
        return choice

    def _next_round(self) -> None:
        self.round_num += 1
        if self.round_num > self.max_rounds:
            self._end_game()
            return

        self.round_label.configure(text=f"Раунд {self.round_num}/{self.max_rounds}")

        picked = self._pick_word()
        if not picked:
            self._end_game()
            return

        self.current_word, self.current_taboo = picked
        self.entry.delete(0, "end")
        self.entry.configure(state="normal")
        self.submit_btn.configure(state="normal")

        # Alternate roles: odd rounds = Olga describes, even = player describes
        if self.round_num % 2 == 1:
            self.round_role = "guesser"
            self.role_label.configure(text="🎯 Ольга описывает — ты угадываешь")
            self._generate_description()
        else:
            self.round_role = "describer"
            self.role_label.configure(text=f"🎤 Ты описываешь — Ольга угадывает\nЗагаданное слово: «{self.current_word}»")
            self.desc_text.configure(state="normal")
            self.desc_text.delete("1.0", "end")
            self.desc_text.insert("1.0", f"Опиши слово «{self.current_word}» не используя его и слова: {', '.join(self.current_taboo)}")
            self.desc_text.configure(state="disabled")
            self.status_label.configure(text="Напиши описание в поле ниже и нажми «Ответить»")

    def _generate_description(self) -> None:
        """Ask Olga to describe the word without saying it or taboo words."""
        self.desc_text.configure(state="normal")
        self.desc_text.delete("1.0", "end")
        self.desc_text.insert("1.0", "Olga готовит описание...")
        self.desc_text.configure(state="disabled")
        self.status_label.configure(text="Olga думает...")

        prompt = f"""You are playing Taboo. Describe the word "{self.current_word}" without saying it.
Do NOT use these taboo words: {', '.join(self.current_taboo)}.
Do NOT use translations or the word itself.
Give a clear description in 2-3 sentences at {self.level} English level.
The player needs to guess the word from your description."""

        threading.Thread(target=self._fetch_description, args=(prompt,), daemon=True).start()

    def _fetch_description(self, prompt: str) -> None:
        try:
            if self.ollama:
                model = getattr(self.ollama, "model", None)
                if not model:
                    models = self.ollama.list_models() if hasattr(self.ollama, "list_models") else []
                    if models:
                        model = models[0]
                if model:
                    response = self.ollama.generate(model, prompt, use_cache=False)
                else:
                    response = self._fallback_description()
            else:
                response = self._fallback_description()
            self.win.after(0, lambda: self._show_description(response))
        except Exception as exc:
            self.win.after(0, lambda: self._show_description(self._fallback_description()))

    def _fallback_description(self) -> str:
        word = self.current_word
        return f"This is something you can find in everyday life. It is related to {word[:3]}... Can you guess what it is?"

    def _show_description(self, text: str) -> None:
        self.desc_text.configure(state="normal")
        self.desc_text.delete("1.0", "end")
        self.desc_text.insert("1.0", text.strip())
        self.desc_text.configure(state="disabled")
        self.status_label.configure(text="Напиши свой ответ в поле ниже")
        self.entry.focus_set()

    def _submit_guess(self) -> None:
        guess = self.entry.get().strip().lower()
        if not guess:
            return
        self.entry.delete(0, "end")

        if self.round_role == "guesser":
            # Player guesses the word
            if guess == self.current_word.lower():
                self.score += 10
                self.words_guessed += 1
                self.score_label.configure(text=f"Счёт: {self.score}")
                self.status_label.configure(text=f"✅ Верно! +10 очков. Слово: {self.current_word}", fg=SUCCESS)
                self.win.after(1500, self._next_round)
            else:
                self.status_label.configure(text=f"❌ Не совсем. Попробуй ещё раз или пропусти.", fg=ACCENT)
        else:
            # Player describes, Olga guesses
            self._ollama_guess(guess)

    def _ollama_guess(self, description: str) -> None:
        """Ask Olga to guess the word from the player's description."""
        self.status_label.configure(text="Olga угадывает...")
        self.entry.configure(state="disabled")
        self.submit_btn.configure(state="disabled")

        prompt = f"""The player described a word: "{description}"
The word was: "{self.current_word}"
Did the player describe it well without using the word itself or these taboo words: {', '.join(self.current_taboo)}?

If the description is good (player avoided the word and taboo words), respond: "CORRECT: <your guess>"
If the player used the word or a taboo word, respond: "FOUL: <which word was used>"
Keep it short."""

        threading.Thread(target=self._fetch_ollama_guess, args=(prompt, description), daemon=True).start()

    def _fetch_ollama_guess(self, prompt: str, description: str) -> None:
        try:
            if self.ollama:
                model = getattr(self.ollama, "model", None)
                if not model:
                    models = self.ollama.list_models() if hasattr(self.ollama, "list_models") else []
                    if models:
                        model = models[0]
                if model:
                    response = self.ollama.generate(model, prompt, use_cache=False)
                else:
                    response = "CORRECT: " + self.current_word
            else:
                response = "CORRECT: " + self.current_word

            # Check if description was valid
            desc_lower = description.lower()
            used_taboo = [t for t in self.current_taboo if t.lower() in desc_lower]
            used_word = self.current_word.lower() in desc_lower

            if used_word or used_taboo:
                result = f"🚫 Olga заметила запрещённое слово! Слово было: {self.current_word}"
            else:
                self.score += 10
                self.words_guessed += 1
                self.score_label.configure(text=f"Счёт: {self.score}")
                result = f"✅ Olga угадала: {self.current_word}! +10 очков"

            self.win.after(0, lambda: self._on_ollama_guessed(result))
        except Exception:
            self.win.after(0, lambda: self._on_ollama_guessed(f"✅ Слово: {self.current_word}! +10 очков"))

    def _on_ollama_guessed(self, result: str) -> None:
        self.status_label.configure(text=result, fg=TEXT_SECONDARY)
        self.win.after(1800, self._next_round)

    def _skip_round(self) -> None:
        self.status_label.configure(text=f"Слово было: {self.current_word}", fg=TEXT_MUTED)
        self.win.after(1000, self._next_round)

    def _end_game(self) -> None:
        self.entry.configure(state="disabled")
        self.submit_btn.configure(state="disabled")
        self.skip_btn.configure(state="disabled")
        self.role_label.configure(text="🏁 Игра окончена!")
        self.desc_text.configure(state="normal")
        self.desc_text.delete("1.0", "end")
        elapsed = int(time.time() - self.start_time)
        self.desc_text.insert("1.0", f"Счёт: {self.score}\nУгадано слов: {self.words_guessed}\nВремя: {elapsed}с")
        self.desc_text.configure(state="disabled")
        self.status_label.configure(text="Спасибо за игру!", fg=ACCENT)
        if self.on_finish:
            self.on_finish(self.score, self.words_guessed)

    def _close(self) -> None:
        self.win.destroy()
