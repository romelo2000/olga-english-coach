"""
Contexto — semantic word guessing game.

Olga picks a secret word from the user's vocabulary level.
The player guesses words; Olga rates semantic closeness 1-100.
Teaches synonyms, antonyms, and semantic relationships.

Powered by local Ollama model — no internet required.
"""

import tkinter as tk
from tkinter import ttk
import threading
import random
import json
import urllib.request
import time

from ui_theme import (
    BG, CARD_BG, CHAT_BG, CHAT_FG, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, ACCENT_HOVER, SUCCESS, WARNING, DANGER, BORDER,
    FONT_TITLE, FONT_HEADING, FONT_BODY, FONT_SMALL, FONT_MONO,
    is_dark,
)

# Word pools by level (words Olga can pick as secret)
_WORD_POOLS = {
    "B1": [
        "adventure", "challenge", "decision", "environment", "furniture",
        "generation", "holiday", "journey", "knowledge", "landscape",
        "memory", "occasion", "performance", "quality", "relationship",
        "situation", "tradition", "universe", "weather", "experience",
        "balance", "comfort", "danger", "effort", "fortune",
        "gather", "imagine", "journey", "listen", "manage",
        "natural", "official", "popular", "regular", "similar",
        "accept", "achieve", "compare", "depend", "explain",
        "future", "global", "honest", "independent", "necessary",
    ],
    "B2": [
        "accomplishment", "biodiversity", "consequence", "discrimination",
        "entrepreneur", "fundamental", "hypothesis", "implementation",
        "jurisdiction", "legitimate", "manipulate", "negotiate",
        "obligation", "perspective", "quantitative", "recommendation",
        "sustainable", "threshold", "unanimous", "vulnerable",
        "ambiguous", "comprehensive", "deteriorate", "elaborate",
        "feasible", "genuine", "hinder", "imply", "justify",
        "mitigate", "notion", "preliminary", "reluctant", "subsequent",
    ],
    "C1": [
        "abstraction", "benevolent", "circumvent", "dichotomy",
        "ephemeral", "fastidious", "gregarious", "heterogeneous",
        "idiosyncratic", "juxtapose", "lucid", "mellifluous",
        "nostalgia", "obfuscate", "paradigm", "quintessential",
        "recondite", "sycophant", "tacit", "ubiquitous",
        "vicarious", "wistful", "zealous", "ambivalent",
        "capricious", "deleterious", "effervescent", "fortuitous",
    ],
}


class ContextoGame:
    """Semantic word guessing game — guess the secret word by meaning closeness."""

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
        self.secret_word = ""
        self.guesses: list[tuple[str, int]] = []
        self.max_hints = 3
        self.hints_used = 0
        self.won = False
        self.start_time = time.time()

        pool = _WORD_POOLS.get(level, _WORD_POOLS["B1"])
        self.secret_word = random.choice(pool)

        self._build_ui()

    def _build_ui(self) -> None:
        self.win = tk.Toplevel(self.parent)
        self.win.title("🔍 Contexto — угадай слово по смыслу")
        self.win.geometry("520x600")
        self.win.resizable(True, True)
        self.win.transient(self.parent)
        self.win.grab_set()
        self.win.configure(bg=BG)

        # Header
        header = tk.Frame(self.win, bg=BG, padx=16, pady=12)
        header.pack(fill="x")
        tk.Label(header, text="🔍 Contexto", bg=BG, fg=ACCENT, font=FONT_TITLE).pack(side="left")
        info_label = tk.Label(
            header,
            text="Угадай слово по смыслу.\nOlga даст число 1-100 — насколько близко твоё слово.",
            bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL, justify="left",
        )
        info_label.pack(side="left", padx=(12, 0))

        # Input frame
        input_frame = tk.Frame(self.win, bg=BG, padx=16, pady=8)
        input_frame.pack(fill="x")
        self.entry = tk.Entry(input_frame, bg=CHAT_BG, fg=TEXT_PRIMARY, font=FONT_BODY,
                              relief="solid", borderwidth=1, width=25)
        self.entry.pack(side="left", padx=(0, 8))
        self.entry.bind("<Return>", lambda e: self._make_guess())
        self.entry.focus_set()

        guess_btn = tk.Button(
            input_frame, text="Угадать", bg=ACCENT, fg="white", font=FONT_BODY,
            relief="flat", cursor="hand2", command=self._make_guess,
        )
        guess_btn.pack(side="left", padx=(0, 4))

        self.hint_btn = tk.Button(
            input_frame, text=f"💡 Подсказка ({self.max_hints})", bg=CARD_BG, fg=TEXT_PRIMARY,
            font=FONT_SMALL, relief="flat", cursor="hand2", command=self._use_hint,
        )
        self.hint_btn.pack(side="left")

        # Guesses list (scrollable)
        list_frame = tk.Frame(self.win, bg=BG, padx=16, pady=8)
        list_frame.pack(fill="both", expand=True)

        tk.Label(list_frame, text="Твои догадки:", bg=BG, fg=TEXT_MUTED, font=FONT_SMALL).pack(anchor="w")

        self.guesses_canvas = tk.Canvas(list_frame, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.guesses_canvas.yview)
        self.guesses_inner = tk.Frame(self.guesses_canvas, bg=BG)
        self.guesses_inner.bind(
            "<Configure>",
            lambda e: self.guesses_canvas.configure(scrollregion=self.guesses_canvas.bbox("all")),
        )
        self.guesses_canvas.create_window((0, 0), window=self.guesses_inner, anchor="nw")
        self.guesses_canvas.configure(yscrollcommand=scrollbar.set)
        self.guesses_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Status
        self.status_label = tk.Label(self.win, text="", bg=BG, fg=TEXT_MUTED, font=FONT_SMALL)
        self.status_label.pack(fill="x", padx=16, pady=(0, 8))

        # Close button
        bottom = tk.Frame(self.win, bg=BG, padx=16, pady=8)
        bottom.pack(fill="x")
        tk.Button(bottom, text="Закрыть", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_SMALL,
                  relief="flat", cursor="hand2", command=self._close).pack(side="right")

    def _color_for_score(self, score: int) -> str:
        dark = is_dark()
        if score >= 90:
            return "#00ff88" if dark else "#008844"
        elif score >= 70:
            return "#88ff00" if dark else "#448800"
        elif score >= 50:
            return "#ffcc00" if dark else "#aa8800"
        elif score >= 30:
            return "#ff8800" if dark else "#cc6600"
        elif score >= 10:
            return "#ff4400" if dark else "#dd2200"
        else:
            return "#888888" if dark else "#555555"

    def _add_guess_row(self, word: str, score: int) -> None:
        row = tk.Frame(self.guesses_inner, bg=BG)
        row.pack(fill="x", pady=2)

        color = self._color_for_score(score)
        bar_width = max(2, int(score * 3))

        # Score number
        tk.Label(row, text=f"{score:>3}", bg=BG, fg=color, font=FONT_MONO, width=4).pack(side="left")

        # Word
        tk.Label(row, text=word, bg=BG, fg=TEXT_PRIMARY, font=FONT_BODY).pack(side="left", padx=(8, 8))

        # Score bar
        bar = tk.Frame(row, bg=color, width=bar_width, height=16)
        bar.pack(side="left", padx=(4, 0))
        bar.pack_propagate(False)

        # Scroll to bottom
        self.guesses_canvas.update_idletasks()
        self.guesses_canvas.yview_moveto(1.0)

    def _make_guess(self) -> None:
        if self.won:
            return
        word = self.entry.get().strip().lower()
        if not word:
            return
        if word in [g[0] for g in self.guesses]:
            self.status_label.configure(text="Это слово уже было — попробуй другое.")
            return

        self.entry.delete(0, "end")
        self.status_label.configure(text="Olga оценивает...")

        threading.Thread(target=self._score_guess, args=(word,), daemon=True).start()

    def _score_guess(self, word: str) -> None:
        try:
            score = self._get_semantic_score(word)
            self.guesses.append((word, score))
            self.win.after(0, lambda: self._on_guess_scored(word, score))
        except Exception as exc:
            self.win.after(0, lambda: self.status_label.configure(text=f"Ошибка: {exc}"))

    def _get_semantic_score(self, word: str) -> int:
        """Ask Ollama to rate semantic closeness 1-100."""
        prompt = f"""You are a semantic similarity engine.
The secret word is: "{self.secret_word}"
The player guessed: "{word}"

Rate how semantically close the guess is to the secret word on a scale of 1-100.
- 100 = exact match (same word)
- 80-99 = synonym or very closely related
- 50-79 = related concept (same category)
- 20-49 = distantly related
- 1-19 = unrelated

Respond with ONLY a number 1-100. No other text."""

        if self.ollama:
            try:
                model = getattr(self.ollama, "model", None)
                if not model:
                    # Try to get available models
                    models = self.ollama.list_models() if hasattr(self.ollama, "list_models") else []
                    if models:
                        model = models[0]
                    else:
                        return self._fallback_score(word)

                response = self.ollama.generate(model, prompt, use_cache=False)
                # Extract number from response
                text = response.strip()
                # Try to parse just the number
                for token in text.split():
                    try:
                        num = int(token)
                        if 1 <= num <= 100:
                            return num
                    except ValueError:
                        continue
                # Fallback: try to find any number in text
                import re
                numbers = re.findall(r'\d+', text)
                if numbers:
                    num = int(numbers[0])
                    return max(1, min(100, num))
                return self._fallback_score(word)
            except Exception:
                return self._fallback_score(word)
        else:
            return self._fallback_score(word)

    def _fallback_score(self, word: str) -> int:
        """Simple fallback scoring when no LLM available."""
        if word == self.secret_word:
            return 100
        # Simple character overlap heuristic
        common = set(word.lower()) & set(self.secret_word.lower())
        total = set(word.lower()) | set(self.secret_word.lower())
        base = int(len(common) / max(1, len(total)) * 60)
        # Bonus for same length
        if len(word) == len(self.secret_word):
            base += 10
        # Bonus for shared prefix
        shared_prefix = 0
        for a, b in zip(word, self.secret_word):
            if a == b:
                shared_prefix += 1
            else:
                break
        base += shared_prefix * 5
        return max(1, min(99, base))

    def _on_guess_scored(self, word: str, score: int) -> None:
        self._add_guess_row(word, score)

        if word.lower() == self.secret_word.lower() or score >= 95:
            self.won = True
            elapsed = int(time.time() - self.start_time)
            self.status_label.configure(
                text=f"🎉 Верно! Слово было «{self.secret_word}». Угадано за {len(self.guesses)} попыток, {elapsed}с.",
                fg=ACCENT,
            )
            self.entry.configure(state="disabled")
            if self.on_finish:
                self.on_finish(self.secret_word, len(self.guesses), elapsed)
        elif score >= 70:
            self.status_label.configure(text="🔥 Очень близко!", fg=SUCCESS if is_dark() else "#448800")
        elif score >= 50:
            self.status_label.configure(text="💡 Тепло — в правильном направлении", fg=WARNING if is_dark() else "#aa8800")
        elif score >= 30:
            self.status_label.configure(text="❄ Далеко — попробуй другое направление", fg="#ff8800" if is_dark() else "#cc6600")
        else:
            self.status_label.configure(text="🧊 Совсем далеко — подумай о другой теме", fg="#888888" if is_dark() else "#555555")

    def _use_hint(self) -> None:
        if self.hints_used >= self.max_hints or self.won:
            return
        self.hints_used += 1
        remaining = self.max_hints - self.hints_used
        self.hint_btn.configure(text=f"💡 Подсказка ({remaining})")

        # Give a hint: first letter + word length
        hint = f"Подсказка: начинается на «{self.secret_word[0].upper()}», {len(self.secret_word)} букв"
        if self.hints_used >= 2:
            # Second hint: category
            prompt = f"What category does the word '{self.secret_word}' belong to? Answer in one word (e.g. 'emotion', 'nature', 'abstract')."
            try:
                if self.ollama:
                    model = getattr(self.ollama, "model", "")
                    if model:
                        category = self.ollama.generate(model, prompt, use_cache=False).strip()
                        hint += f"\nКатегория: {category}"
            except Exception:
                pass
        if self.hints_used >= 3:
            # Third hint: a synonym
            prompt = f"Give one synonym for the word '{self.secret_word}'. Answer with just the synonym."
            try:
                if self.ollama:
                    model = getattr(self.ollama, "model", "")
                    if model:
                        synonym = self.ollama.generate(model, prompt, use_cache=False).strip()
                        hint += f"\nСиноним: {synonym}"
            except Exception:
                pass

        self.status_label.configure(text=hint, fg=TEXT_SECONDARY)

    def _close(self) -> None:
        if not self.won and not self.guesses:
            pass  # no penalty for not playing
        self.win.destroy()
