"""Word Battle — vocabulary quiz game with timer, streaks, and SRS integration."""

from __future__ import annotations

import random
import tkinter as tk
from tkinter import messagebox
from collections import Counter

from ui_theme import (
    BG, CARD_BG, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, ACCENT_HOVER, SUCCESS, WARNING, DANGER, BORDER,
    FONT_TITLE, FONT_HEADING, FONT_BODY, FONT_SMALL, FONT_MONO,
    make_button,
)
from worddb import get_db


class WordBattleGame:
    """A popup quiz game: pick the correct translation for each word.

    Modes:
      forward (default) — English word → pick Russian translation
      reverse           — Russian translation → pick English word
    """

    QUESTIONS_PER_GAME = 10
    SECONDS_PER_QUESTION = 15
    STARTING_LIVES = 3
    OPTIONS_COUNT = 4

    def __init__(self, parent: tk.Tk, level: str = "B1", on_finish=None, mode: str = "forward",
                 srs_words: list[dict] | None = None) -> None:
        self.parent = parent
        self.level = level
        self.base_level = level
        self.on_finish = on_finish
        self.mode = mode  # "forward" or "reverse"
        self.srs_words = srs_words or []  # SRS due words to prioritise

        self.score = 0
        self.lives = self.STARTING_LIVES
        self.streak = 0
        self.best_streak = 0
        self.question_num = 0
        self.time_left = self.SECONDS_PER_QUESTION
        self.current_word = None
        self.current_options = None
        self.current_answer = None
        self.wrong_words: list[str] = []
        self.timer_id = None
        self.answered = False
        self.correct_streak_for_level = 0

        self.win = tk.Toplevel(parent)
        self.win.title("Word Battle")
        self.win.configure(bg=BG)
        self.win.resizable(False, False)
        self.win.grab_set()
        self.win.protocol("WM_DELETE_WINDOW", self._close)

        self._build_ui()
        self._next_question()
        self.win.focus_force()

    def _build_ui(self) -> None:
        # ── Header ──
        header = tk.Frame(self.win, bg=BG, padx=20, pady=12)
        header.pack(fill="x")
        mode_text = "EN → RU" if self.mode == "forward" else "RU → EN"
        tk.Label(header, text=f"⚔️ Word Battle ({mode_text})", bg=BG, fg=TEXT_PRIMARY, font=FONT_TITLE).pack(side="left")
        self.level_label = tk.Label(header, text=f"Уровень: {self.level}", bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL)
        self.level_label.pack(side="right")

        # ── Stats bar ──
        stats = tk.Frame(self.win, bg=BG, padx=20, pady=4)
        stats.pack(fill="x")
        self.score_label = tk.Label(stats, text="Счёт: 0", bg=BG, fg=TEXT_PRIMARY, font=FONT_HEADING)
        self.score_label.pack(side="left")
        self.lives_label = tk.Label(stats, text="❤️❤️❤️", bg=BG, fg=TEXT_PRIMARY, font=FONT_HEADING)
        self.lives_label.pack(side="left", padx=(16, 0))
        self.streak_label = tk.Label(stats, text="Серия: 0", bg=BG, fg=TEXT_SECONDARY, font=FONT_BODY)
        self.streak_label.pack(side="left", padx=(16, 0))
        self.timer_label = tk.Label(stats, text=f"⏱ {self.SECONDS_PER_QUESTION}", bg=BG, fg=WARNING, font=FONT_HEADING)
        self.timer_label.pack(side="right")

        # ── Progress bar ──
        prog_frame = tk.Frame(self.win, bg=BG, padx=20)
        prog_frame.pack(fill="x")
        self.progress_bar = tk.Frame(prog_frame, bg=BORDER, height=4)
        self.progress_bar.pack(fill="x")
        self.progress_fill = tk.Frame(self.progress_bar, bg=ACCENT, height=4)
        self.progress_fill.place(x=0, y=0)

        # ── Question card ──
        q_card = tk.Frame(self.win, bg=CARD_BG, padx=24, pady=20)
        q_card.pack(fill="x", padx=20, pady=(12, 8))
        q_top = tk.Frame(q_card, bg=CARD_BG)
        q_top.pack(fill="x")
        self.question_num_label = tk.Label(q_top, text="", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL)
        self.question_num_label.pack(side="left")
        self.speak_btn = tk.Button(q_top, text="🔊", bg=CARD_BG, fg=TEXT_PRIMARY, relief="flat", borderwidth=0, font=FONT_BODY, cursor="hand2", command=self._speak_word)
        self.speak_btn.pack(side="right")
        self.word_label = tk.Label(q_card, text="", bg=CARD_BG, fg=TEXT_PRIMARY, font=("SF Pro Display", 28, "bold"))
        self.word_label.pack(anchor="w", pady=(8, 4))
        self.hint_label = tk.Label(q_card, text="", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL)
        self.hint_label.pack(anchor="w")

        # ── Options ──
        self.option_buttons: list[tk.Button] = []
        self.option_frame = tk.Frame(self.win, bg=BG, padx=20)
        self.option_frame.pack(fill="x", pady=(0, 8))
        for i in range(self.OPTIONS_COUNT):
            btn = tk.Button(
                self.option_frame, text="", bg=CARD_BG, fg=TEXT_PRIMARY,
                activebackground=BORDER, relief="flat", borderwidth=0,
                font=FONT_BODY, cursor="hand2", padx=16, pady=12,
                anchor="w", justify="left",
            )
            btn.pack(fill="x", pady=3)
            btn.bind("<Button-1>", lambda e, idx=i: self._answer(idx))
            self.option_buttons.append(btn)

        # ── Feedback ──
        self.feedback_label = tk.Label(self.win, text="", bg=BG, fg=TEXT_PRIMARY, font=FONT_BODY)
        self.feedback_label.pack(pady=(0, 8))

        # ── Footer ──
        footer = tk.Frame(self.win, bg=BG, padx=20, pady=8)
        footer.pack(fill="x")
        tk.Label(footer, text="Enter / 1-4 — выбор ответа", bg=BG, fg=TEXT_MUTED, font=FONT_SMALL).pack(side="left")
        make_button(footer, "🔄 Сменить режим", self._toggle_mode).pack(side="left", padx=(12, 0))
        make_button(footer, "Выйти", self._close).pack(side="right")

        # Keyboard shortcuts
        self.win.bind("1", lambda e: self._answer(0))
        self.win.bind("2", lambda e: self._answer(1))
        self.win.bind("3", lambda e: self._answer(2))
        self.win.bind("4", lambda e: self._answer(3))
        self.win.bind("<Return>", lambda e: self._on_enter())

    def _adjust_difficulty(self) -> None:
        """Adaptive difficulty: bump level after 3 correct in a row, drop after 2 wrong."""
        cefr_order = ["A1", "A2", "B1", "B2", "C1", "C2"]
        idx = cefr_order.index(self.level) if self.level in cefr_order else 2
        if self.correct_streak_for_level >= 3 and idx < 5:
            self.level = cefr_order[idx + 1]
            self.correct_streak_for_level = 0
        elif self.lives < self.STARTING_LIVES and idx > 0 and self.streak == 0:
            if self.correct_streak_for_level <= -2 and idx > 0:
                self.level = cefr_order[idx - 1]
                self.correct_streak_for_level = 0

    def _load_words(self) -> list[dict]:
        db = get_db()
        words = db.random_words(self.level, 40, category="vocab")
        if len(words) < self.OPTIONS_COUNT:
            words = db.random_words(self.level, 40)
        # Mix in SRS due words at ~30% rate
        if self.srs_words and random.random() < 0.30:
            srs_w = random.choice(self.srs_words)
            srs_entry = {"word": srs_w.get("front", ""),
                         "translation": srs_w.get("back", ""),
                         "cefr": self.level}
            if srs_entry["word"] and srs_entry["translation"]:
                words.insert(0, srs_entry)
        return words

    def _next_question(self) -> None:
        if self.question_num >= self.QUESTIONS_PER_GAME:
            self._game_over()
            return

        self.answered = False
        self.question_num += 1
        self.time_left = self.SECONDS_PER_QUESTION

        words = self._load_words()
        if len(words) < self.OPTIONS_COUNT:
            self.feedback_label.config(text="Недостаточно слов в базе для этого уровня.")
            self._close()
            return

        correct = random.choice(words)
        words.remove(correct)
        wrongs = random.sample(words, self.OPTIONS_COUNT - 1)

        self.current_word = correct
        if self.mode == "reverse":
            self.current_answer = correct["word"]
            self.current_options = [correct["word"]] + [w["word"] for w in wrongs]
        else:
            self.current_answer = correct["translation"]
            self.current_options = [correct["translation"]] + [w["translation"] for w in wrongs]
        random.shuffle(self.current_options)

        # UI
        self.question_num_label.config(text=f"Вопрос {self.question_num} из {self.QUESTIONS_PER_GAME}")
        if self.mode == "reverse":
            self.word_label.config(text=correct["translation"])
        else:
            self.word_label.config(text=correct["word"])
        hint_parts = []
        if self.mode == "reverse":
            if correct.get("ipa"):
                hint_parts.append(f"IPA: {correct['ipa']}")
            if correct.get("cefr"):
                hint_parts.append(f"[{correct['cefr']}]")
        else:
            if correct.get("ipa"):
                hint_parts.append(f"IPA: {correct['ipa']}")
            if correct.get("pos"):
                hint_parts.append(correct["pos"])
            if correct.get("cefr"):
                hint_parts.append(f"[{correct['cefr']}]")
        self.hint_label.config(text="  |  ".join(hint_parts))

        correct_idx = self.current_options.index(self.current_answer)
        for i, opt in enumerate(self.current_options):
            btn = self.option_buttons[i]
            btn.config(text=f"{i+1}.  {opt}", bg=CARD_BG, fg=TEXT_PRIMARY, state="normal")

        self.feedback_label.config(text="")
        self._update_progress()
        self._tick_timer()

    def _tick_timer(self) -> None:
        if self.answered:
            return
        self.timer_label.config(text=f"⏱ {self.time_left}")
        if self.time_left <= 5:
            self.timer_label.config(fg=DANGER)
        else:
            self.timer_label.config(fg=WARNING)

        if self.time_left <= 0:
            self._time_up()
            return

        self.time_left -= 1
        self.timer_id = self.win.after(1000, self._tick_timer)

    def _time_up(self) -> None:
        if self.answered:
            return
        self.answered = True
        self.lives -= 1
        self.streak = 0
        self.correct_streak_for_level -= 1
        self.wrong_words.append(self.current_word["word"])
        correct_idx = self.current_options.index(self.current_answer)
        self.option_buttons[correct_idx].config(bg=SUCCESS, fg="white")
        self.feedback_label.config(text=f"⏰ Время вышло! Правильно: {self.current_answer}", fg=DANGER)
        self._update_stats()
        self._adjust_difficulty()
        if self.lives <= 0:
            self.win.after(2000, self._game_over)
        else:
            self.win.after(2000, self._next_question)

    def _answer(self, idx: int) -> None:
        if self.answered or idx >= len(self.option_buttons):
            return
        self.answered = True
        if self.timer_id:
            self.win.after_cancel(self.timer_id)

        correct_idx = self.current_options.index(self.current_answer)
        selected = self.option_buttons[idx]

        if idx == correct_idx:
            points = 10 + self.streak * 2 + self.time_left
            self.score += points
            self.streak += 1
            self.correct_streak_for_level += 1
            if self.streak > self.best_streak:
                self.best_streak = self.streak
            selected.config(bg=SUCCESS, fg="white")
            streak_text = f"  🔥 Серия x{self.streak}!" if self.streak >= 3 else ""
            self.feedback_label.config(text=f"✅ Верно! +{points} очков{streak_text}", fg=SUCCESS)
        else:
            self.lives -= 1
            self.streak = 0
            self.correct_streak_for_level -= 1
            self.wrong_words.append(self.current_word["word"])
            selected.config(bg=DANGER, fg="white")
            self.option_buttons[correct_idx].config(bg=SUCCESS, fg="white")
            self.feedback_label.config(text=f"❌ Правильно: {self.current_answer}", fg=DANGER)

        for btn in self.option_buttons:
            btn.config(state="disabled")

        self._update_stats()
        self._adjust_difficulty()
        if self.lives <= 0:
            self.win.after(2000, self._game_over)
        else:
            self.win.after(2000, self._next_question)

    def _on_enter(self) -> None:
        if self.answered and self.question_num < self.QUESTIONS_PER_GAME and self.lives > 0:
            return
        if self.answered and self.lives <= 0:
            self._game_over()

    def _update_stats(self) -> None:
        self.score_label.config(text=f"Счёт: {self.score}")
        hearts = "❤️" * self.lives + "🖤" * (self.STARTING_LIVES - self.lives)
        self.lives_label.config(text=hearts)
        self.streak_label.config(text=f"Серия: {self.streak}")

    def _update_progress(self) -> None:
        pct = (self.question_num - 1) / self.QUESTIONS_PER_GAME * 100
        self.win.update_idletasks()
        w = self.progress_bar.winfo_width()
        if w <= 1:
            w = 400
        self.progress_fill.place(x=0, y=0, width=max(1, int(w * pct / 100)))

    def _game_over(self) -> None:
        if self.timer_id:
            try:
                self.win.after_cancel(self.timer_id)
            except Exception:
                pass

        for child in self.win.winfo_children():
            child.destroy()

        self.win.configure(bg=BG)
        frame = tk.Frame(self.win, bg=BG, padx=40, pady=40)
        frame.pack(fill="both", expand=True)

        is_win = self.lives > 0
        title = "🎉 Победа!" if is_win else "💀 Игра окончена"
        color = SUCCESS if is_win else DANGER
        tk.Label(frame, text=title, bg=BG, fg=color, font=FONT_TITLE).pack(pady=(0, 20))

        stats_lines = [
            f"Счёт: {self.score}",
            f"Лучшая серия: {self.best_streak}",
            f"Вопросов пройдено: {self.question_num}",
            f"Жизней осталось: {self.lives}",
        ]
        if self.wrong_words:
            stats_lines.append(f"Слов для повторения: {len(self.wrong_words)}")

        for line in stats_lines:
            tk.Label(frame, text=line, bg=BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(pady=4)

        if self.wrong_words:
            wrong_text = "Слова для повторения:\n" + ", ".join(self.wrong_words[:15])
            if len(self.wrong_words) > 15:
                wrong_text += f" ...и ещё {len(self.wrong_words) - 15}"
            tk.Label(frame, text=wrong_text, bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL, wraplength=450, justify="left").pack(pady=(16, 0))

        btn_row = tk.Frame(frame, bg=BG)
        btn_row.pack(pady=(24, 0))
        make_button(btn_row, "🔄 Играть снова", self._restart, accent=True).pack(side="left", padx=(0, 8))
        make_button(btn_row, "Закрыть", self._close).pack(side="left")

        if self.on_finish:
            self.on_finish(self.score, self.wrong_words)

    def _restart(self) -> None:
        self.score = 0
        self.lives = self.STARTING_LIVES
        self.streak = 0
        self.best_streak = 0
        self.question_num = 0
        self.wrong_words = []
        self.answered = False

        for child in self.win.winfo_children():
            child.destroy()
        self._build_ui()
        self._next_question()

    def _speak_word(self) -> None:
        if self.current_word and self.current_word.get("word"):
            try:
                import subprocess
                subprocess.Popen(["say", "-v", "Samantha", "-r", "175", self.current_word["word"]],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    def _toggle_mode(self) -> None:
        self.mode = "reverse" if self.mode == "forward" else "forward"
        self._restart()

    def _close(self) -> None:
        if self.timer_id:
            try:
                self.win.after_cancel(self.timer_id)
            except Exception:
                pass
        self.win.grab_release()
        self.win.destroy()
