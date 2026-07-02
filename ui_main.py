"""Tabbed UI for Olga English Coach.

Tabs:
  1. Dashboard — overview, daily goal, streak, recommended lesson
  2. Learn — grammar curriculum, vocabulary sets, SRS review
  3. Practice — chat with AI, voice input/output
  4. Progress — statistics, charts, speaking review, error patterns
"""

from __future__ import annotations

import json
import logging
import queue
import random
import re
import threading
import time
import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import messagebox, ttk

import customtkinter as ctk

from ui_theme import (
    BG, CARD_BG, ACCENT, ACCENT_HOVER, ACCENT_LIGHT,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    SUCCESS, WARNING, DANGER, BORDER, CHART_COLORS, BUTTON_IDLE_BG,
    FONT_TITLE, FONT_HEADING, FONT_BODY, FONT_SMALL, FONT_MONO,
    apply_theme, make_card, make_button, make_label, make_progress_bar,
    toggle_dark_mode, is_dark, CHAT_BG, CHAT_FG,
    save_theme_pref, load_theme_pref, set_theme_pref_path,
)
from coach import (
    COACH_NAME, START_COMMAND, MODE_PROMPTS, LEVEL_HINTS,
    CoachSettings, Coach, analyze_speaking, extract_speakable_text, count_errors,
    build_diglot_prompt,
)
from course import (
    CourseManager, SKILLS, SKILL_RU, PRACTICE_RU,
)
from curriculum import (
    CEFR_LEVELS, CEFR_CAN_DO,
    grammar_for_level, vocabulary_for_level, functions_for_level,
    all_vocab_cards_for_level, grammar_point_by_id,
)
from ollama_client import OllamaClient, DEFAULT_MODEL_SUGGESTIONS
from srs import SRSManager, SRSCard, quality_from_rating
from voice_toolkit import VoiceToolkit
from license_manager import LicenseManager
from analytics import UsageTracker
import ollama_installer as ollama_inst
import updater
from app_paths import get_resources_dir, get_user_data_dir

USER_LEVELS = ["B1", "B2", "C1", "C2"]

logger = logging.getLogger("olga.ui")


class OllamaGameAdapter:
    """Wrapper that exposes .model and .generate() for game modules.
    Games expect ollama_client.model and ollama_client.generate(prompt, model=...).
    OllamaClient doesn't have .model, so we wrap it with the current model from UI."""

    def __init__(self, client: OllamaClient, model_var: tk.StringVar) -> None:
        self._client = client
        self._model_var = model_var

    @property
    def model(self) -> str:
        return self._model_var.get().strip()

    def generate(self, *args, use_cache: bool = False, **kwargs) -> str:
        """Generate text. Supports both calling conventions:
        - generate(model, prompt)  — old style (positional)
        - generate(prompt, model=...) — new style
        """
        if len(args) >= 2:
            # generate(model, prompt) — old style
            m = args[0]
            prompt = args[1]
        elif len(args) == 1:
            # generate(prompt) — with model in kwargs or fallback
            prompt = args[0]
            m = kwargs.get("model", "")
        else:
            prompt = kwargs.get("prompt", "")
            m = kwargs.get("model", "")
        m = m or self.model
        if not m:
            raise RuntimeError("Нет выбранной модели Ollama")
        return self._client.generate(m, prompt, use_cache=use_cache)

    def list_models(self) -> list[str]:
        return self._client.list_models()


class EnglishCoachUI:
    def __init__(self, root) -> None:
        self.root = root
        self.root.title(f"{COACH_NAME} • English Coach")
        self.root.geometry("1700x1000")
        self.root.minsize(1400, 850)

        self.runtime_root = get_resources_dir()
        self.data_root = get_user_data_dir()
        set_theme_pref_path(self.data_root / "theme_pref.json")
        load_theme_pref()
        apply_theme(self.root)
        self.client = OllamaClient()
        self.voice = VoiceToolkit(self.runtime_root, self.data_root)
        self.course = CourseManager(self.data_root)
        self.coach = Coach(self.client)
        self.chat_history_path = self.data_root / "chat_history.json"
        self.license = LicenseManager(self.data_root)
        self.analytics = UsageTracker(self.data_root)
        self.analytics.track_launch()
        self._session_start = time.time()

        self.models: list[str] = []
        self.response_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.pending_voice_input = False
        self.last_voice_analysis: dict | None = None
        self.is_generating = False
        self.session_start_time: float = 0.0
        self.current_grammar_point_id = ""
        self.current_vocab_theme = ""
        self.current_practice_type = "dialogue"

        self.status_var = tk.StringVar(value="Проверяю Ollama...")
        self._ollama_ok = False           # track connection state for reconnect
        self._reconnect_pending = False   # avoid duplicate reconnect loops
        self.model_var = tk.StringVar()
        self.model_var.trace_add("write", lambda *_: self.client.invalidate_cache())
        self.ollama = OllamaGameAdapter(self.client, self.model_var)
        self.mode_var = tk.StringVar(value="Диалог")
        self.level_var = tk.StringVar(value=self.course.level)
        self.topic_var = tk.StringVar(value="Путешествия, работа, everyday English")
        self.voice_input_var = tk.StringVar(value="en-US")
        self.voice_output_var = tk.BooleanVar(value=True)
        self.concise_var = tk.BooleanVar(value=True)
        self.tts_voice_var = tk.StringVar(value="Samantha")  # default EN voice A
        self.tts_voice2_var = tk.StringVar(value="Daniel")   # default EN voice B (dialogues)
        self.tts_rate_var = tk.IntVar(value=175)

        try:
            self._build_ui()
            self._apply_theme_to_widgets(self.root)
            self._refresh_all()
            self.coach.load_history(self.chat_history_path)
            self._restore_chat_from_history()
            self._install_trackpad_scroll()
            self.root.after(150, self._poll_queue)
            self.root.after(300, lambda: self._apply_theme_to_widgets(self.root))
            self.root.after(2000, self._cleanup_srs)
            self.root.after(5000, self._schedule_daily_reminder)
            self.root.after(10000, lambda: updater.check_and_prompt(self.root, auto=True))
            # License check first, then Ollama install, then bootstrap
            self.root.after(100, self._check_license_and_start)
            if self.course.needs_placement_test():
                self.root.after(2000, self._show_placement_test)
            elif not self.course.state.get("onboarding_done", False):
                self.root.after(2500, self._start_onboarding_tour)
        except Exception as exc:
            self._show_fallback_ui(exc)

    def _show_fallback_ui(self, exc: Exception) -> None:
        from coach import COACH_NAME
        log_path = self.data_root / "startup-error.log"
        import traceback
        log_path.write_text("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)), encoding="utf-8")
        for child in self.root.winfo_children():
            child.destroy()
        self.root.configure(bg=BG)
        frame = tk.Frame(self.root, bg=BG, padx=28, pady=28)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text=f"{COACH_NAME} English Coach: ошибка запуска", bg=BG, fg=TEXT_PRIMARY, font=FONT_TITLE, justify="left").pack(anchor="w", pady=(0, 12))
        tk.Label(frame, text=f"Лог сохранён в:\n{log_path}", bg=BG, fg=TEXT_SECONDARY, font=FONT_BODY, justify="left").pack(anchor="w")

    def _restore_chat_from_history(self) -> None:
        if not self.coach.conversation_history:
            return
        self._append_chat("system", "Восстановлен предыдущий диалог.\n\n")
        for role, text in self.coach.conversation_history:
            if role == "user":
                self._append_chat("user", f"Вы:\n{text}\n\n")
            else:
                self._append_chat("assistant", f"{COACH_NAME}:\n{text}\n\n")

    # ─── UI Construction ───

    @staticmethod
    def _bind_scroll(canvas: tk.Canvas, scroll_frame: tk.Frame) -> None:
        """Bind mousewheel scrolling — global approach that works with CTk widgets."""
        def _on_wheel(event):
            # Only scroll if the canvas actually needs scrolling
            if canvas.yview() != (0.0, 1.0):
                canvas.yview_scroll(int(-event.delta / 120), "units")

        # Bind directly on canvas
        canvas.bind("<MouseWheel>", _on_wheel)

        # Also bind on all children recursively — works for tk widgets
        def _bind_recursive(widget):
            try:
                widget.bind("<MouseWheel>", _on_wheel)
            except Exception:
                pass
            try:
                for child in widget.winfo_children():
                    _bind_recursive(child)
            except Exception:
                pass

        # Bind immediately and rebind after children are created
        _bind_recursive(scroll_frame)
        canvas.after(300, lambda: _bind_recursive(scroll_frame))

        # Also use bind_all as fallback — check if mouse is over this canvas
        def _on_global_wheel(event):
            try:
                x, y = event.x_root, event.y_root
                cx = canvas.winfo_rootx()
                cy = canvas.winfo_rooty()
                cw = canvas.winfo_width()
                ch = canvas.winfo_height()
                if cx <= x <= cx + cw and cy <= y <= cy + ch:
                    if canvas.yview() != (0.0, 1.0):
                        canvas.yview_scroll(int(-event.delta / 120), "units")
            except Exception:
                pass

        canvas.bind_all("<MouseWheel>", _on_global_wheel, add="+")

        # Ensure scroll_frame width matches canvas width
        def _on_canvas_config(event):
            canvas.itemconfig("all", width=event.width)
        canvas.bind("<Configure>", _on_canvas_config)

    def _install_trackpad_scroll(self) -> None:
        """Install native macOS trackpad scroll via pyobjc NSEvent monitor."""
        cg_ok = False
        try:
            import trackpad_scroll as ts
            cg_ok = ts.install_monitor(self.root)
            if cg_ok:
                logger.info("Native trackpad scroll monitor installed")
            else:
                logger.warning("Trackpad scroll CGEventTap failed to install")
        except Exception as e:
            logger.warning("Trackpad scroll not available: %s", e)
        # Register canvases after layout settles — try multiple times
        self.root.after(300, self._register_scroll_canvases)
        self.root.after(1500, self._register_scroll_canvases)

    def _register_scroll_canvases(self) -> None:
        """Register all CTkScrollableFrame canvases after layout is complete."""
        try:
            import trackpad_scroll as ts
            # Don't clear — just add any new canvases
            registered = set(id(c) for c in ts._canvases)
            for sf in [getattr(self, "_sf_dashboard", None),
                       getattr(self, "_sf_games", None),
                       getattr(self, "_sf_learn", None),
                       getattr(self, "_sf_progress", None),
                       getattr(self, "_sf_stories", None)]:
                if sf is not None:
                    try:
                        canvas = sf._parent_canvas
                        if canvas is not None and id(canvas) not in registered:
                            ts.register_scrollable(sf)
                            registered.add(id(canvas))
                    except Exception:
                        pass
            # Set current tab as active scroll target
            self._update_active_scroll_canvas()
            # Bind MouseWheel fallback only once
            if not getattr(self, "_mousewheel_bound", False):
                self.root.bind_all("<MouseWheel>", self._on_global_mousewheel, add="+")
                self._mousewheel_bound = True
            logger.info("Scroll canvases registered: %d, active=%s",
                        len(ts._canvases),
                        ts._active_canvas[0] if ts._active_canvas else None)
        except Exception as e:
            logger.warning("Canvas registration failed: %s", e)

    def _on_global_mousewheel(self, event) -> None:
        """Global MouseWheel handler — scrolls the active tab's canvas."""
        try:
            import trackpad_scroll as ts
            # Use active canvas from trackpad_scroll, or find it
            canvas = None
            if ts._active_canvas and ts._active_canvas[0].winfo_exists():
                canvas = ts._active_canvas[0]
            if canvas is None:
                # Fall back to finding canvas for current tab
                idx = self.notebook.index(self.notebook.select())
                sf_map = {
                    0: getattr(self, "_sf_dashboard", None),
                    1: getattr(self, "_sf_learn", None),
                    3: getattr(self, "_sf_games", None),
                    4: getattr(self, "_sf_progress", None),
                    5: getattr(self, "_sf_stories", None),
                }
                sf = sf_map.get(idx)
                if sf is not None:
                    canvas = sf._parent_canvas
            if canvas is None or not canvas.winfo_exists():
                return
            delta = event.delta
            if delta == 0:
                return
            # macOS: delta can be large (trackpad pixels) or ±1 (mouse wheel)
            if abs(delta) < 10:
                units = -int(delta)
            else:
                units = -int(delta / 30)
            if units != 0:
                canvas.yview_scroll(units, "units")
        except Exception:
            pass

    def _build_ui(self) -> None:
        container = tk.Frame(self.root, bg=BG, padx=12, pady=12)
        container.pack(fill="both", expand=True)

        header = tk.Frame(container, bg=BG)
        header.pack(fill="x", pady=(0, 8))
        tk.Label(header, text=f"{COACH_NAME} • English Coach", bg=BG, fg=TEXT_PRIMARY, font=FONT_TITLE).pack(side="left")
        status_label = tk.Label(header, textvariable=self.status_var, bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL)
        status_label.pack(side="right")

        self.notebook = ttk.Notebook(container)
        self.notebook.pack(fill="both", expand=True)

        self.dashboard_frame = tk.Frame(self.notebook, bg=BG)
        self.learn_frame = tk.Frame(self.notebook, bg=BG)
        self.practice_frame = tk.Frame(self.notebook, bg=BG)
        self.games_frame = tk.Frame(self.notebook, bg=BG)
        self.progress_frame = tk.Frame(self.notebook, bg=BG)
        self.stories_frame = tk.Frame(self.notebook, bg=BG)
        self.flashcards_frame = tk.Frame(self.notebook, bg=BG)
        self.diglot_frame = tk.Frame(self.notebook, bg=BG)

        self.notebook.add(self.dashboard_frame, text="🏠  Главная")
        self.notebook.add(self.learn_frame, text="📚  Учить")
        self.notebook.add(self.practice_frame, text="💬  Практика")
        self.notebook.add(self.games_frame, text="🎮  Игры")
        self.notebook.add(self.progress_frame, text="📊  Прогресс")
        self.notebook.add(self.stories_frame, text="📖  Рассказы")
        self.notebook.add(self.flashcards_frame, text="🃏  Карточки")
        self.notebook.add(self.diglot_frame, text="🧵  Diglot Weave")
        self.notebook.bind("<<NotebookTabChanged>>",
                           lambda e: self._update_active_scroll_canvas())

        self._build_dashboard()
        self._build_learn()
        self._build_practice()
        self._build_games()
        self._build_progress()
        self._build_stories()
        self._build_flashcards()
        self._build_diglot()

        # Keyboard shortcuts for tab switching
        self.root.bind("<Command-1>", lambda e: self._switch_to_tab(0))
        self.root.bind("<Command-2>", lambda e: self._switch_to_tab(1))
        self.root.bind("<Command-3>", lambda e: self._switch_to_tab(2))
        self.root.bind("<Command-4>", lambda e: self._switch_to_tab(3))
        self.root.bind("<Command-5>", lambda e: self._switch_to_tab(4))
        self.root.bind("<Command-6>", lambda e: self._switch_to_tab(5))
        self.root.bind("<Command-7>", lambda e: self._switch_to_tab(6))
        self.root.bind("<Command-8>", lambda e: self._switch_to_tab(7))

        # Restore window geometry
        self._restore_window_geometry()

    def _build_dashboard(self) -> None:
        frame = self.dashboard_frame
        scroll_frame = ctk.CTkScrollableFrame(frame, fg_color=BG, scrollbar_button_color=BORDER,
                                              scrollbar_button_hover_color=ACCENT)
        scroll_frame.pack(fill="both", expand=True, padx=0, pady=0)
        self._sf_dashboard = scroll_frame

        # ── Welcome card ──
        welcome = make_card(scroll_frame, padx=16, pady=16)
        welcome.pack(fill="x", pady=(0, 8))
        welcome_content = tk.Frame(welcome, bg=CARD_BG)
        welcome_content.pack(fill="x")

        # Olga avatar
        avatar_path = self.runtime_root / "assets" / "olga_avatar.png"
        if avatar_path.exists():
            try:
                from PIL import Image, ImageTk
                img = Image.open(str(avatar_path))
                img.thumbnail((80, 80))
                self._olga_avatar = ImageTk.PhotoImage(img)
                tk.Label(welcome_content, image=self._olga_avatar, bg=CARD_BG).pack(side="left", padx=(0, 12))
            except Exception:
                pass

        text_frame = tk.Frame(welcome_content, bg=CARD_BG)
        text_frame.pack(side="left", fill="x", expand=True)
        tk.Label(text_frame, text=f"Привет! Я {COACH_NAME}, твой AI-репетитор английского.", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        tk.Label(text_frame, text="Весь диалог остаётся на этом Mac — ничего не уходит в облако.", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL).pack(anchor="w", pady=(4, 0))
        make_button(text_frame, "💬 Начать разговор с Ольгой", self._quick_start_chat, accent=True).pack(anchor="w", pady=(8, 0))

        # ── XP / Weekly goal card ──
        xp_card = make_card(scroll_frame, padx=16, pady=12)
        xp_card.pack(fill="x", pady=(0, 8))
        xp_top = tk.Frame(xp_card, bg=CARD_BG)
        xp_top.pack(fill="x")
        tk.Label(xp_top, text="⚡ XP за неделю", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(side="left")
        self.xp_total_label = tk.Label(xp_top, text="", bg=CARD_BG, fg=ACCENT, font=("SF Pro Display", 18, "bold"))
        self.xp_total_label.pack(side="right")
        # Progress bar
        self.xp_bar_bg = tk.Frame(xp_card, bg=BORDER, height=12)
        self.xp_bar_bg.pack(fill="x", pady=(8, 4))
        self.xp_bar_fill = tk.Frame(self.xp_bar_bg, bg=ACCENT, height=12)
        self.xp_bar_fill.place(x=0, y=0)
        self.xp_goal_label = tk.Label(xp_card, text="", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL)
        self.xp_goal_label.pack(anchor="w")
        self.xp_today_label = tk.Label(xp_card, text="", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL)
        self.xp_today_label.pack(anchor="w", pady=(2, 0))

        # ── Word of the Day card ──
        wotd_card = make_card(scroll_frame, padx=16, pady=16)
        wotd_card.pack(fill="x", pady=(0, 8))
        tk.Label(wotd_card, text="📖 Слово дня", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        self.wotd_word_label = tk.Label(wotd_card, text="", bg=CARD_BG, fg=TEXT_PRIMARY, font=("SF Pro Display", 22, "bold"))
        self.wotd_word_label.pack(anchor="w", pady=(8, 2))
        self.wotd_ipa_label = tk.Label(wotd_card, text="", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_MONO)
        self.wotd_ipa_label.pack(anchor="w")
        self.wotd_translation_label = tk.Label(wotd_card, text="", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_BODY)
        self.wotd_translation_label.pack(anchor="w", pady=(2, 4))
        self.wotd_example_label = tk.Label(wotd_card, text="", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL, wraplength=700, justify="left")
        self.wotd_example_label.pack(anchor="w", pady=(0, 8))
        wotd_btn_row = tk.Frame(wotd_card, bg=CARD_BG)
        wotd_btn_row.pack(fill="x")
        make_button(wotd_btn_row, "🔊 Произнести", self._speak_wotd).pack(side="left", padx=(0, 4))
        make_button(wotd_btn_row, "➕ В повторение", self._add_wotd_to_srs).pack(side="left")

        # ── Idiom of the Day card ──
        idiom_card = make_card(scroll_frame, padx=16, pady=16)
        idiom_card.pack(fill="x", pady=(0, 8))
        tk.Label(idiom_card, text="🇬🇧 Идиома дня", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        self.idiom_text_label = tk.Label(idiom_card, text="", bg=CARD_BG, fg=TEXT_PRIMARY, font=("SF Pro Display", 18, "bold"), wraplength=700, justify="left")
        self.idiom_text_label.pack(anchor="w", pady=(8, 2))
        self.idiom_trans_label = tk.Label(idiom_card, text="", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_BODY, wraplength=700, justify="left")
        self.idiom_trans_label.pack(anchor="w", pady=(2, 2))
        self.idiom_example_label = tk.Label(idiom_card, text="", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL, wraplength=700, justify="left")
        self.idiom_example_label.pack(anchor="w", pady=(2, 8))
        idiom_btn_row = tk.Frame(idiom_card, bg=CARD_BG)
        idiom_btn_row.pack(fill="x")
        make_button(idiom_btn_row, "🔊", self._speak_idiom).pack(side="left", padx=(0, 4))
        make_button(idiom_btn_row, "➕ В повторение", self._add_idiom_to_srs).pack(side="left")

        # ── Daily Challenge card ──
        challenge_card = make_card(scroll_frame, padx=16, pady=16)
        challenge_card.pack(fill="x", pady=(0, 8))
        challenge_header = tk.Frame(challenge_card, bg=CARD_BG)
        challenge_header.pack(fill="x")
        tk.Label(challenge_header, text="🎯 Задание дня", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(side="left")
        self.challenge_status_label = tk.Label(challenge_header, text="", bg=CARD_BG, fg=SUCCESS, font=FONT_SMALL)
        self.challenge_status_label.pack(side="right")
        self.challenge_category_label = tk.Label(challenge_card, text="", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL)
        self.challenge_category_label.pack(anchor="w", pady=(4, 2))
        self.challenge_text_label = tk.Label(challenge_card, text="", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_BODY, wraplength=700, justify="left")
        self.challenge_text_label.pack(anchor="w", pady=(2, 8))
        challenge_btn_row = tk.Frame(challenge_card, bg=CARD_BG)
        challenge_btn_row.pack(fill="x")
        make_button(challenge_btn_row, "Начать", self._start_daily_challenge, accent=True).pack(side="left", padx=(0, 4))
        make_button(challenge_btn_row, "✅ Выполнено", self._complete_daily_challenge).pack(side="left")

        # ── Streak card (moved below actions for compact layout) ──
        streak_card = make_card(scroll_frame, padx=16, pady=12)
        streak_card.pack(fill="x", pady=(0, 8))
        streak_top = tk.Frame(streak_card, bg=CARD_BG)
        streak_top.pack(fill="x")
        self.dash_streak_num = tk.Label(streak_top, text="🔥 0", bg=CARD_BG, fg=ACCENT,
                                        font=("SF Pro Display", 24, "bold"))
        self.dash_streak_num.pack(side="left")
        streak_right = tk.Frame(streak_top, bg=CARD_BG)
        streak_right.pack(side="left", padx=(12, 0))
        tk.Label(streak_right, text="дней подряд", bg=CARD_BG, fg=TEXT_PRIMARY,
                 font=FONT_HEADING).pack(anchor="w")
        self.dash_streak_sub = tk.Label(streak_right, text="", bg=CARD_BG, fg=TEXT_SECONDARY,
                                        font=FONT_SMALL)
        self.dash_streak_sub.pack(anchor="w")
        # 7-day dot grid
        dots_frame = tk.Frame(streak_card, bg=CARD_BG)
        dots_frame.pack(anchor="w", pady=(8, 0))
        self._streak_dots = []
        for i in range(7):
            col = tk.Frame(dots_frame, bg=CARD_BG)
            col.pack(side="left", padx=4)
            dot = tk.Frame(col, bg=BORDER, width=18, height=18)
            dot.pack()
            dot.pack_propagate(False)
            lbl = tk.Label(col, text="", bg=CARD_BG, fg=TEXT_MUTED, font=("SF Pro Text", 9))
            lbl.pack()
            self._streak_dots.append((dot, lbl))

        # ── Daily status card ──
        status_card = make_card(scroll_frame, padx=16, pady=16)
        status_card.pack(fill="x", pady=(0, 8))
        tk.Label(status_card, text="Статус курса", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        self.dash_level_label = tk.Label(status_card, text="", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_BODY)
        self.dash_level_label.pack(anchor="w", pady=(8, 2))
        self.dash_streak_label = tk.Label(status_card, text="", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL)
        self.dash_streak_label.pack(anchor="w", pady=2)
        self.dash_goal_label = tk.Label(status_card, text="", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_BODY)
        self.dash_goal_label.pack(anchor="w", pady=2)
        self.dash_progress_label = tk.Label(status_card, text="", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_BODY)
        self.dash_progress_label.pack(anchor="w", pady=(2, 8))
        self.dash_progress_bar = tk.Frame(status_card, bg=BORDER, height=8)
        self.dash_progress_bar.pack(fill="x", pady=(0, 8))
        self.dash_progress_fill = tk.Frame(self.dash_progress_bar, bg=ACCENT, height=8)
        self.dash_progress_fill.place(x=0, y=0)

        # ── Skill bars card ──
        skills_card = make_card(scroll_frame, padx=16, pady=16)
        skills_card.pack(fill="x", pady=(0, 8))
        tk.Label(skills_card, text="Навыки", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        self.skill_bars: dict[str, tk.Frame] = {}
        self.skill_labels: dict[str, tk.Label] = {}
        for skill in SKILLS:
            row = tk.Frame(skills_card, bg=CARD_BG)
            row.pack(fill="x", pady=(6, 0))
            tk.Label(row, text=SKILL_RU[skill], bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL, width=14, anchor="w").pack(side="left")
            bar_bg = tk.Frame(row, bg=BORDER, height=8)
            bar_bg.pack(side="left", fill="x", expand=True, padx=(4, 8))
            fill = tk.Frame(bar_bg, bg=ACCENT, height=8)
            fill.place(x=0, y=0)
            self.skill_bars[skill] = fill
            val_label = tk.Label(row, text="0%", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_SMALL, width=5)
            val_label.pack(side="right")
            self.skill_labels[skill] = val_label

        # ── Recommended lesson card ──
        rec_card = make_card(scroll_frame, padx=16, pady=16)
        rec_card.pack(fill="x", pady=(0, 8))
        tk.Label(rec_card, text="Рекомендация от Ольги", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        self.dash_rec_label = tk.Label(rec_card, text="", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_BODY, wraplength=700, justify="left")
        self.dash_rec_label.pack(anchor="w", pady=(8, 8))
        make_button(rec_card, "Начать рекомендованный урок", self._start_recommended_lesson, accent=True).pack(anchor="w", pady=(0, 4))
        make_button(rec_card, "🔀 Смешанная сессия (interleaving)", self._start_interleaved_session).pack(anchor="w")

        # ── Quick actions card ──
        actions_card = make_card(scroll_frame, padx=16, pady=16)
        actions_card.pack(fill="x", pady=(0, 8))
        actions_header = tk.Frame(actions_card, bg=CARD_BG)
        actions_header.pack(fill="x", pady=(0, 8))
        tk.Label(actions_header, text="Быстрые действия", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(side="left")
        self.actions_level_label = tk.Label(actions_header, text="", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL)
        self.actions_level_label.pack(side="right")

        # Core buttons (always visible) — 6 most important
        core_row = tk.Frame(actions_card, bg=CARD_BG)
        core_row.pack(fill="x", pady=(0, 4))
        make_button(core_row, "💬 Диалог", lambda: self._quick_practice("Диалог", "dialogue"), accent=True).pack(side="left", padx=(0, 4))
        make_button(core_row, "📝 Письмо", lambda: self._quick_practice("Письмо", "writing_task")).pack(side="left", padx=(0, 4))
        make_button(core_row, "🎭 Ролевая игра", lambda: self._quick_practice("Ролевая игра", "roleplay")).pack(side="left", padx=(0, 4))
        make_button(core_row, "📖 Чтение", lambda: self._quick_practice("Чтение", "reading_task")).pack(side="left", padx=(0, 4))
        make_button(core_row, "🗣 Аудирование", lambda: self._quick_practice("Диалог-аудирование", "dialogue_listening")).pack(side="left", padx=(0, 4))
        make_button(core_row, "🎭 Дебат", self._start_debate).pack(side="left")

        # Advanced buttons (hidden by default, shown via "Ещё →")
        self.advanced_actions_frame = tk.Frame(actions_card, bg=CARD_BG)
        # Not packed initially — toggled by "Ещё →" button

        adv_row1 = tk.Frame(self.advanced_actions_frame, bg=CARD_BG)
        adv_row1.pack(fill="x", pady=(0, 4))
        make_button(adv_row1, "🎤 Спикинг-дрилл", lambda: self._quick_practice("Собеседник", "speaking_drill")).pack(side="left", padx=(0, 4))
        make_button(adv_row1, "📐 Грамматика", lambda: self._quick_practice("Упражнение", "grammar_exercise")).pack(side="left", padx=(0, 4))
        make_button(adv_row1, "🔁 Повторить слова", lambda: self._start_vocab_review()).pack(side="left", padx=(0, 4))
        make_button(adv_row1, "✏️ Диктант", lambda: self._quick_practice("Диктант", "dictation")).pack(side="left", padx=(0, 4))
        make_button(adv_row1, "🗣 Shadowing", lambda: self._quick_practice("Shadowing", "shadowing")).pack(side="left")
        adv_row2 = tk.Frame(self.advanced_actions_frame, bg=CARD_BG)
        adv_row2.pack(fill="x", pady=(0, 4))
        make_button(adv_row2, "🔤 Minimal Pairs", lambda: self._quick_practice("Minimal Pairs", "minimal_pairs")).pack(side="left", padx=(0, 4))
        make_button(adv_row2, "🔗 Collocations", lambda: self._quick_practice("Collocation Drill", "collocation_drill")).pack(side="left", padx=(0, 4))
        make_button(adv_row2, "🔍 Найди ошибку", lambda: self._quick_practice("Error Correction", "error_correction")).pack(side="left", padx=(0, 4))
        make_button(adv_row2, "🔄 Трансформация", lambda: self._quick_practice("Sentence Transformation", "sentence_transformation")).pack(side="left", padx=(0, 4))
        make_button(adv_row2, "⚡ Phrasal Verbs", lambda: self._quick_practice("Phrasal Verbs", "phrasal_verbs")).pack(side="left")
        adv_row3 = tk.Frame(self.advanced_actions_frame, bg=CARD_BG)
        adv_row3.pack(fill="x")
        make_button(adv_row3, "📝 Dictogloss", lambda: self._quick_practice("Dictogloss", "dictogloss")).pack(side="left", padx=(0, 4))
        make_button(adv_row3, "🌊 Input Flood", lambda: self._quick_practice("Input Flood", "input_flood")).pack(side="left", padx=(0, 4))
        make_button(adv_row3, "🎯 Pushed Output", lambda: self._quick_practice("Pushed Output", "pushed_output")).pack(side="left", padx=(0, 4))
        make_button(adv_row3, "💬 Lexical Chunks", lambda: self._quick_practice("Lexical Chunks", "lexical_chunks")).pack(side="left", padx=(0, 4))
        make_button(adv_row3, "🔄 Task Repetition", lambda: self._quick_practice("Task Repetition", "task_repetition")).pack(side="left")

        # Toggle button for advanced actions
        self._advanced_visible = False
        self.advanced_toggle_btn = make_button(actions_card, "Ещё →", self._toggle_advanced_actions)
        self.advanced_toggle_btn.pack(anchor="w", pady=(4, 0))

        # ── Settings card ──
        settings_card = make_card(scroll_frame, padx=16, pady=16)
        settings_card.pack(fill="x", pady=(0, 8))
        tk.Label(settings_card, text="Настройки", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w", pady=(0, 8))

        settings_row = tk.Frame(settings_card, bg=CARD_BG)
        settings_row.pack(fill="x", pady=(0, 4))
        tk.Label(settings_row, text="Модель", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL, width=10, anchor="w").pack(side="left")
        self.model_combo = self._make_option_menu(settings_row, self.model_var, DEFAULT_MODEL_SUGGESTIONS, width=20)
        self.model_combo.pack(side="left", padx=(4, 8))
        tk.Label(settings_row, text="Уровень", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL, width=8, anchor="w").pack(side="left")
        self.level_menu = self._make_option_menu(settings_row, self.level_var, USER_LEVELS, width=6)
        self.level_menu.pack(side="left", padx=(4, 8))
        make_button(settings_row, "Применить", self._apply_level).pack(side="left")

        goal_row = tk.Frame(settings_card, bg=CARD_BG)
        goal_row.pack(fill="x", pady=(4, 0))
        make_button(goal_row, "Цель 7 дней", lambda: self._set_goal(7)).pack(side="left", padx=(0, 4))
        make_button(goal_row, "Цель 30 дней", lambda: self._set_goal(30)).pack(side="left", padx=(0, 4))
        make_button(goal_row, "Цель 90 дней", lambda: self._set_goal(90)).pack(side="left", padx=(0, 4))
        self.theme_btn = make_button(goal_row, "☀ Светлая" if is_dark() else "🌙 Тёмная", self._toggle_theme)
        self.theme_btn.pack(side="left", padx=(0, 4))
        make_button(goal_row, "📤 CSV", self._export_csv).pack(side="left", padx=(0, 4))
        make_button(goal_row, "📄 PDF", self._export_pdf_report).pack(side="left")

        # ── License row ──
        lic = self.license
        lic_row = tk.Frame(settings_card, bg=CARD_BG)
        lic_row.pack(fill="x", pady=(8, 0))
        if lic.is_activated:
            lic_label_text = f"✅ Лицензия активирована"
            make_button(lic_row, lic_label_text, lambda: None).pack(side="left")
        else:
            days = lic.trial_days_left
            if days > 0:
                lic_label_text = f"⏳ Пробный период: {days} дн."
            else:
                lic_label_text = "❌ Пробный период окончен"
            tk.Label(lic_row, text=lic_label_text, bg=CARD_BG, fg=TEXT_SECONDARY,
                     font=FONT_SMALL).pack(side="left")
            make_button(lic_row, "Активировать", self._show_license_activation, accent=True).pack(side="left", padx=(8, 0))

        # ── Data export/import row ──
        data_row = tk.Frame(settings_card, bg=CARD_BG)
        data_row.pack(fill="x", pady=(4, 0))
        make_button(data_row, "💾 Резервная копия", self._export_data).pack(side="left", padx=(0, 4))
        make_button(data_row, "📥 Восстановить", self._import_data).pack(side="left", padx=(0, 4))
        make_button(data_row, "❓ Помощь", self._show_help).pack(side="left")

    def _build_games(self) -> None:
        frame = self.games_frame
        scroll_frame = ctk.CTkScrollableFrame(frame, fg_color=BG, scrollbar_button_color=BORDER,
                                              scrollbar_button_hover_color=ACCENT)
        scroll_frame.pack(fill="both", expand=True, padx=0, pady=0)
        self._sf_games = scroll_frame

        # ── Games header ──
        header_card = make_card(scroll_frame, padx=16, pady=16)
        header_card.pack(fill="x", pady=(0, 8))
        tk.Label(header_card, text="🎮 Игры", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_TITLE).pack(anchor="w")
        tk.Label(header_card, text="Учись, играя. Каждая игра адаптируется под твой уровень.", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_BODY).pack(anchor="w", pady=(4, 0))

        # ── Word Battle ──
        wb_card = make_card(scroll_frame, padx=16, pady=16)
        wb_card.pack(fill="x", pady=(0, 8))
        tk.Label(wb_card, text="⚔️ Word Battle", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        tk.Label(wb_card, text="Переведи слово быстрее таймера. Очки за скорость и точность. Режимы: EN→RU и RU→EN.", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_BODY, wraplength=700, justify="left").pack(anchor="w", pady=(4, 4))
        wb_scores = self.course.game_high_scores()
        if wb_scores:
            best = wb_scores[0]
            self.wb_progress_label = tk.Label(wb_card, text=f"Рекорд: {best['score']} очков | Правильно: {best['correct']} | Ошибок: {best['wrong']} | Игр: {len(wb_scores)}", bg=CARD_BG, fg=ACCENT, font=FONT_SMALL)
        else:
            self.wb_progress_label = tk.Label(wb_card, text="Пока нет игр — начни первую!", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL)
        self.wb_progress_label.pack(anchor="w", pady=(0, 8))
        make_button(wb_card, "Начать Word Battle", self._start_word_battle, accent=True).pack(anchor="w")

        # ── Survival Game ──
        sv_card = make_card(scroll_frame, padx=16, pady=16)
        sv_card.pack(fill="x", pady=(0, 8))
        tk.Label(sv_card, text="🌍 Language Survival", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        tk.Label(sv_card, text="Выживи в англоязычной стране. Выбери правильную фразу в реальной ситуации.", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_BODY, wraplength=700, justify="left").pack(anchor="w", pady=(4, 4))
        sv_scenes = self.course.survival_game_progress()
        sv_history = self.course.state.get("survival_history", [])
        if sv_scenes or sv_history:
            self.sv_progress_label = tk.Label(sv_card, text=f"Пройдено сцен: {len(sv_scenes)} | Сыграно: {len(sv_history)}", bg=CARD_BG, fg=ACCENT, font=FONT_SMALL)
        else:
            self.sv_progress_label = tk.Label(sv_card, text="Пока нет игр — начни первую!", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL)
        self.sv_progress_label.pack(anchor="w", pady=(0, 8))
        make_button(sv_card, "Начать Survival", self._start_survival_game, accent=True).pack(anchor="w")

        # ── Detective Game ──
        dt_card = make_card(scroll_frame, padx=16, pady=16)
        dt_card.pack(fill="x", pady=(0, 8))
        tk.Label(dt_card, text="🕵️ Language Detective", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        tk.Label(dt_card, text="Расследуй дело. Допрашивай NPC на английском, собери улики, найди виновного.", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_BODY, wraplength=700, justify="left").pack(anchor="w", pady=(4, 4))
        dt_solved = self.course.detective_game_progress()
        dt_history = self.course.state.get("detective_history", [])
        if dt_solved or dt_history:
            self.dt_progress_label = tk.Label(dt_card, text=f"Раскрыто дел: {len(dt_solved)} | Расследований: {len(dt_history)}", bg=CARD_BG, fg=ACCENT, font=FONT_SMALL)
        else:
            self.dt_progress_label = tk.Label(dt_card, text="Пока нет игр — начни первую!", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL)
        self.dt_progress_label.pack(anchor="w", pady=(0, 8))
        make_button(dt_card, "Начать Detective", self._start_detective_game, accent=True).pack(anchor="w")

        # ── Time Loop Game ──
        tl_card = make_card(scroll_frame, padx=16, pady=16)
        tl_card.pack(fill="x", pady=(0, 8))
        tk.Label(tl_card, text="🔄 Time Loop Language", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        tk.Label(tl_card, text="Застрял во временной петле. Каждый день понимаешь больше английского. Разорви петлю!", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_BODY, wraplength=700, justify="left").pack(anchor="w", pady=(4, 4))
        tl_broken = self.course.time_loop_progress()
        tl_history = self.course.state.get("time_loop_history", [])
        if tl_broken or tl_history:
            self.tl_progress_label = tk.Label(tl_card, text=f"Разорвано петель: {len(tl_broken)} | Попыток: {len(tl_history)}", bg=CARD_BG, fg=ACCENT, font=FONT_SMALL)
        else:
            self.tl_progress_label = tk.Label(tl_card, text="Пока нет игр — начни первую!", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL)
        self.tl_progress_label.pack(anchor="w", pady=(0, 8))
        make_button(tl_card, "Начать Time Loop", self._start_time_loop_game, accent=True).pack(anchor="w")

        # ── Contexto Game ──
        ctx_card = make_card(scroll_frame, padx=16, pady=16)
        ctx_card.pack(fill="x", pady=(0, 8))
        tk.Label(ctx_card, text="🔍 Contexto", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        tk.Label(ctx_card, text="Угадай слово по смыслу. Olga даёт число 1-100 — насколько близко твоё слово. Учит синонимы и семантику.", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_BODY, wraplength=700, justify="left").pack(anchor="w", pady=(4, 8))
        make_button(ctx_card, "Начать Contexto", self._start_contexto_game, accent=True).pack(anchor="w")

        # ── Taboo Talks Game ──
        tb_card = make_card(scroll_frame, padx=16, pady=16)
        tb_card.pack(fill="x", pady=(0, 8))
        tk.Label(tb_card, text="🤐 Taboo Talks", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        tk.Label(tb_card, text="Olga описывает слово не называя его. Ты угадываешь. Потом наоборот — ты описываешь, Olga угадывает.", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_BODY, wraplength=700, justify="left").pack(anchor="w", pady=(4, 8))
        make_button(tb_card, "Начать Taboo Talks", self._start_taboo_game, accent=True).pack(anchor="w")

    def _build_learn(self) -> None:
        frame = self.learn_frame
        scroll_frame = ctk.CTkScrollableFrame(frame, fg_color=BG, scrollbar_button_color=BORDER,
                                              scrollbar_button_hover_color=ACCENT)
        scroll_frame.pack(fill="both", expand=True, padx=0, pady=0)
        self._sf_learn = scroll_frame

        # ── SRS Review card ──
        srs_card = make_card(scroll_frame, padx=16, pady=16)
        srs_card.pack(fill="x", pady=(0, 8))
        tk.Label(srs_card, text="Интервальное повторение (SM-2)", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        self.srs_status_label = tk.Label(srs_card, text="", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_BODY)
        self.srs_status_label.pack(anchor="w", pady=(8, 4))
        self.srs_detail_label = tk.Label(srs_card, text="", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL)
        self.srs_detail_label.pack(anchor="w", pady=(0, 8))
        make_button(srs_card, "Начать повторение", self._start_vocab_review, accent=True).pack(anchor="w", pady=(0, 4))
        story_row = tk.Frame(srs_card, bg=CARD_BG)
        story_row.pack(fill="x")
        make_button(story_row, "⚔️ Word Battle", self._start_word_battle).pack(side="left", padx=(0, 4))
        make_button(story_row, "📖 AI-рассказ", lambda: self._switch_to_tab(5)).pack(side="left", padx=(0, 4))
        make_button(story_row, "🕸 Knowledge Graph", self._start_vocab_graph).pack(side="left")

        # ── Word search card ──
        search_card = make_card(scroll_frame, padx=16, pady=16)
        search_card.pack(fill="x", pady=(0, 8))
        tk.Label(search_card, text="Поиск слов в базе", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        search_row = tk.Frame(search_card, bg=CARD_BG)
        search_row.pack(fill="x", pady=(8, 4))
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(search_row, textvariable=self.search_var, bg=CHAT_BG, fg=CHAT_FG, relief="solid", borderwidth=1, font=FONT_BODY, width=30)
        search_entry.pack(side="left", padx=(0, 8))
        search_entry.bind("<Return>", self._on_word_search)
        make_button(search_row, "Найти", self._on_word_search).pack(side="left")
        self.search_result_label = tk.Label(search_card, text="", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL, wraplength=700, justify="left")
        self.search_result_label.pack(anchor="w", pady=(4, 0))

        # ── SRS Review area (hidden until review starts) ──
        self.srs_review_card = make_card(scroll_frame, padx=16, pady=16)
        self.srs_review_card.pack(fill="x", pady=(0, 8))
        self.srs_review_card.pack_forget()
        srs_word_row = tk.Frame(self.srs_review_card, bg=CARD_BG)
        srs_word_row.pack(fill="x", pady=(8, 4))
        self.srs_word_label = tk.Label(srs_word_row, text="", bg=CARD_BG, fg=TEXT_PRIMARY, font=("SF Pro Display", 24, "bold"))
        self.srs_word_label.pack(side="left")
        make_button(srs_word_row, "🔊", self._speak_srs_word).pack(side="left", padx=(10, 0))
        self.srs_translation_label = tk.Label(self.srs_review_card, text="", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_BODY)
        self.srs_translation_label.pack(anchor="w", pady=(0, 4))
        self.srs_example_label = tk.Label(self.srs_review_card, text="", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL, wraplength=700, justify="left")
        self.srs_example_label.pack(anchor="w", pady=(0, 8))
        rating_row = tk.Frame(self.srs_review_card, bg=CARD_BG)
        rating_row.pack(fill="x")
        make_button(rating_row, "Снова", lambda: self._rate_card("again")).pack(side="left", padx=(0, 4))
        make_button(rating_row, "Трудно", lambda: self._rate_card("hard")).pack(side="left", padx=(0, 4))
        make_button(rating_row, "Норм", lambda: self._rate_card("good")).pack(side="left", padx=(0, 4))
        make_button(rating_row, "Легко", lambda: self._rate_card("easy")).pack(side="left")
        make_button(rating_row, "🧠 Мнемоника", self._generate_mnemonic).pack(side="left", padx=(12, 0))
        self.srs_mnemonic_label = tk.Label(self.srs_review_card, text="", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL, wraplength=700, justify="left")
        self.srs_mnemonic_label.pack(anchor="w", pady=(8, 0))
        self.srs_review_session: list[SRSCard] = []
        self.srs_review_index = 0

        # ── Grammar curriculum card ──
        grammar_card = make_card(scroll_frame, padx=16, pady=16)
        grammar_card.pack(fill="x", pady=(0, 8))
        tk.Label(grammar_card, text="Грамматика", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        self.grammar_progress_label = tk.Label(grammar_card, text="", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL)
        self.grammar_progress_label.pack(anchor="w", pady=(4, 8))
        self.grammar_container = tk.Frame(grammar_card, bg=CARD_BG)
        self.grammar_container.pack(fill="x")

        # ── Vocabulary sets card ──
        vocab_card = make_card(scroll_frame, padx=16, pady=16)
        vocab_card.pack(fill="x", pady=(0, 8))
        tk.Label(vocab_card, text="Словарные наборы", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        self.vocab_container = tk.Frame(vocab_card, bg=CARD_BG)
        self.vocab_container.pack(fill="x", pady=(8, 0))

        # ── Functions card ──
        func_card = make_card(scroll_frame, padx=16, pady=16)
        func_card.pack(fill="x", pady=(0, 8))
        tk.Label(func_card, text="Функциональный язык", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        self.func_container = tk.Frame(func_card, bg=CARD_BG)
        self.func_container.pack(fill="x", pady=(8, 0))

    def _build_practice(self) -> None:
        frame = self.practice_frame

        # ── Controls bar ──
        controls = make_card(frame, padx=12, pady=10)
        controls.pack(fill="x", pady=(0, 8))
        ctrl_row = tk.Frame(controls, bg=CARD_BG)
        ctrl_row.pack(fill="x")
        tk.Label(ctrl_row, text="Режим", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack(side="left")
        self.mode_menu = self._make_option_menu(ctrl_row, self.mode_var, list(MODE_PROMPTS.keys()), width=14)
        self.mode_menu.pack(side="left", padx=(4, 12))
        tk.Label(ctrl_row, text="Тема", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack(side="left")
        tk.Entry(ctrl_row, textvariable=self.topic_var, bg=CHAT_BG, fg=CHAT_FG, relief="solid", borderwidth=1, width=30).pack(side="left", padx=(4, 12))
        tk.Label(ctrl_row, text="Микрофон", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack(side="left")
        self.voice_menu = self._make_option_menu(ctrl_row, self.voice_input_var, ["en-US", "ru-RU"], width=8)
        self.voice_menu.pack(side="left", padx=(4, 12))
        tk.Label(ctrl_row, text="Голос A", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack(side="left")
        self._make_option_menu(ctrl_row, self.tts_voice_var,
                               ["Samantha", "Karen", "Daniel", "Milena", "Fred", "Kathy"], width=10).pack(side="left", padx=(4, 8))
        tk.Label(ctrl_row, text="Голос B", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack(side="left")
        self._make_option_menu(ctrl_row, self.tts_voice2_var,
                               ["Daniel", "Karen", "Samantha", "Milena", "Fred", "Kathy"], width=10).pack(side="left", padx=(4, 12))
        tk.Checkbutton(ctrl_row, text="Озвучивать", variable=self.voice_output_var, bg=CARD_BG, fg=TEXT_PRIMARY, selectcolor=CHAT_BG, activebackground=CARD_BG).pack(side="left", padx=(0, 8))
        tk.Checkbutton(ctrl_row, text="Коротко", variable=self.concise_var, bg=CARD_BG, fg=TEXT_PRIMARY, selectcolor=CHAT_BG, activebackground=CARD_BG).pack(side="left")

        # ── Quick prompts ──
        quick = tk.Frame(frame, bg=BG)
        quick.pack(fill="x", pady=(0, 8))
        for title, prompt in [
            ("Разговор", "Давай начнём разговорную практику."),
            ("Исправить", "Исправь мой английский текст и объясни ошибки."),
            ("Грамматика", "Объясни это правило английского с примерами."),
            ("Упражнение", "Сделай для меня небольшое упражнение."),
            ("Интервью", "Проведи интервью на английском."),
            ("Чтение", "Дай мне короткий текст для чтения с вопросами."),
        ]:
            make_button(quick, title, lambda p=prompt: self._fill_prompt(p)).pack(side="left", padx=(0, 4))

        # ── Chat area ──
        chat_card = make_card(frame, padx=12, pady=10)
        chat_card.pack(fill="both", expand=True, pady=(0, 8))
        self.chat = tk.Text(
            chat_card, wrap="word", bg=CHAT_BG, fg=CHAT_FG,
            font=FONT_BODY, padx=12, pady=12, relief="flat", borderwidth=0,
            height=20, state="disabled",
        )
        self.chat.pack(fill="both", expand=True)
        self.chat.tag_configure("user", foreground="#0066cc" if not is_dark() else "#4a9eff", font=("SF Pro Text", 12, "bold"))
        self.chat.tag_configure("assistant", foreground="#8B4513" if not is_dark() else "#d4a574", font=("SF Pro Text", 12))
        self.chat.tag_configure("system", foreground=TEXT_MUTED, font=FONT_SMALL)

        # ── Hint chips (shown when chat is empty) ──
        self.hint_chips_frame = tk.Frame(chat_card, bg=CHAT_BG)
        self.hint_chips_frame.pack(fill="x", padx=12, pady=(8, 4))
        hint_label = tk.Label(self.hint_chips_frame, text="💡 Попробуйте:", bg=CHAT_BG, fg=TEXT_MUTED, font=FONT_SMALL)
        hint_label.pack(anchor="w", pady=(0, 4))
        chips_row = tk.Frame(self.hint_chips_frame, bg=CHAT_BG)
        chips_row.pack(fill="x")
        hint_prompts = [
            ("💬 Tell me about your day", "Tell me about your day."),
            ("✏️ Correct my mistakes", "Correct my mistakes and explain the errors."),
            ("📖 Practice past tense", "Let's practice past tense. Give me sentences to convert."),
            ("🎭 Roleplay: job interview", "Let's do a roleplay — you're the interviewer, I'm the candidate."),
            ("❓ Quiz me", "Quiz me on English grammar and vocabulary."),
            ("➡️ Дальше?", "Дальше?"),
        ]
        for chip_text, chip_prompt in hint_prompts:
            def _on_chip(p=chip_prompt):
                self._fill_prompt(p)
                self.input.focus_set()
            make_button(chips_row, chip_text, _on_chip).pack(side="left", padx=(0, 6), pady=2)

        # ── Typing indicator ──
        self.typing_label = tk.Label(chat_card, text="", bg=CHAT_BG, fg=TEXT_MUTED, font=FONT_SMALL, anchor="w")
        self.typing_label.pack(fill="x", padx=(12, 0), pady=(0, 4))

        # ── Quick replies ──
        self.quick_replies_frame = tk.Frame(chat_card, bg=CHAT_BG)
        self.quick_replies_frame.pack(fill="x", padx=(8, 8), pady=(0, 4))

        # ── Context menu for chat ──
        self.chat.bind("<Button-3>", self._show_chat_context_menu)

        # ── Input area ──
        input_card = make_card(frame, padx=12, pady=10)
        input_card.pack(fill="x")
        self.input = tk.Text(
            input_card, height=3, wrap="word", bg=CHAT_BG, fg=CHAT_FG,
            font=FONT_BODY, padx=12, pady=12, relief="flat", borderwidth=0,
        )
        self.input.pack(fill="x", pady=(0, 8))
        self.input.bind("<Return>", self._on_send_shortcut)
        self.input.bind("<Command-Return>", self._on_send_shortcut)
        self.input.bind("<Shift-Return>", lambda e: None)
        self.input.insert("1.0", START_COMMAND)

        actions = tk.Frame(input_card, bg=CARD_BG)
        actions.pack(fill="x")
        self.send_btn = make_button(actions, "Отправить", self.send_message, accent=True)
        self.send_btn.pack(side="left")
        self.stop_gen_btn = make_button(actions, "⏹ Стоп генерация", self._stop_generation)
        self.stop_gen_btn.pack(side="left", padx=(6, 0))
        make_button(actions, "🎤 Говорить 12 сек", self.record_voice).pack(side="left", padx=(6, 0))
        make_button(actions, "⏹ Стоп", self._stop_speaking).pack(side="left", padx=(6, 0))
        make_button(actions, "🐢", lambda: self._speak_last_response(120)).pack(side="left", padx=(6, 0))
        make_button(actions, "🔊", lambda: self._speak_last_response(175)).pack(side="left", padx=(2, 0))
        make_button(actions, "⚡", lambda: self._speak_last_response(220)).pack(side="left", padx=(2, 0))
        make_button(actions, "🔍", self._open_chat_search).pack(side="right", padx=(0, 4))
        make_button(actions, "❓ Викторина", self._generate_quiz).pack(side="right", padx=(0, 4))
        make_button(actions, "💾 Сохранить", self._export_chat).pack(side="right", padx=(0, 4))
        make_button(actions, "📊 Отчёт", self._generate_feedback_report).pack(side="right", padx=(0, 4))
        make_button(actions, "Очистить", self.clear_chat).pack(side="right")
        make_button(actions, "📥 Скачать модель", self._pull_model_dialog).pack(side="right", padx=(0, 6))
        make_button(actions, "Обновить модели", self.refresh_models).pack(side="right", padx=(0, 6))

    def _open_chat_search(self) -> None:
        """Open a floating search bar to find text in chat history."""
        try:
            if hasattr(self, "_chat_search_win") and self._chat_search_win.winfo_exists():
                self._chat_search_win.lift()
                return
        except Exception:
            pass
        win = tk.Toplevel(self.root)
        win.title("Поиск в чате")
        win.geometry("400x56")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        self._chat_search_win = win
        frame = tk.Frame(win, bg=BG, padx=8, pady=8)
        frame.pack(fill="both", expand=True)
        var = tk.StringVar()
        entry = tk.Entry(frame, textvariable=var, font=FONT_BODY, bg=CARD_BG, fg=TEXT_PRIMARY,
                         relief="flat", bd=1)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        entry.focus_set()
        self._search_pos = "1.0"
        def _search(event=None):
            q = var.get().strip()
            if not q:
                return
            self.chat.tag_remove("search_hl", "1.0", "end")
            self.chat.tag_configure("search_hl", background="#f5c842", foreground="black")
            pos = self.chat.search(q, self._search_pos, nocase=True, stopindex="end")
            if not pos:
                pos = self.chat.search(q, "1.0", nocase=True, stopindex="end")
            if pos:
                end = f"{pos}+{len(q)}c"
                self.chat.tag_add("search_hl", pos, end)
                self.chat.see(pos)
                self._search_pos = end
        entry.bind("<Return>", _search)
        make_button(frame, "Найти", _search).pack(side="left")
        win.protocol("WM_DELETE_WINDOW", lambda: (
            self.chat.tag_remove("search_hl", "1.0", "end"), win.destroy()))

    def _build_progress(self) -> None:
        frame = self.progress_frame
        scroll_frame = ctk.CTkScrollableFrame(frame, fg_color=BG, scrollbar_button_color=BORDER,
                                              scrollbar_button_hover_color=ACCENT)
        scroll_frame.pack(fill="both", expand=True, padx=0, pady=0)
        self._sf_progress = scroll_frame

        # ── Overview card ──
        overview = make_card(scroll_frame, padx=16, pady=16)
        overview.pack(fill="x", pady=(0, 8))
        tk.Label(overview, text="Общая статистика", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        self.stats_overview_label = tk.Label(overview, text="", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_BODY, justify="left")
        self.stats_overview_label.pack(anchor="w", pady=(8, 4))
        self.stats_secondary_label = tk.Label(overview, text="", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL, justify="left")
        self.stats_secondary_label.pack(anchor="w")

        # ── Heatmap card (GitHub-style) ──
        heatmap_card = make_card(scroll_frame, padx=16, pady=16)
        heatmap_card.pack(fill="x", pady=(0, 8))
        tk.Label(heatmap_card, text="🔥 Карта активности (13 недель)", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w", pady=(0, 8))
        self.heatmap_frame = tk.Frame(heatmap_card, bg=CARD_BG)
        self.heatmap_frame.pack(fill="x")
        # Legend
        legend_row = tk.Frame(heatmap_card, bg=CARD_BG)
        legend_row.pack(anchor="e", pady=(8, 0))
        tk.Label(legend_row, text="меньше", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL).pack(side="left", padx=(0, 4))
        for i, col in enumerate([BORDER, "#2d4a2d", "#4a8c4a", "#6bcf6b", "#2dd42d"]):
            cell = tk.Label(legend_row, text="  ", bg=col, width=2, height=1, relief="flat")
            cell.pack(side="left", padx=1)
        tk.Label(legend_row, text="больше", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL).pack(side="left", padx=(4, 0))

        # ── Activity chart card ──
        activity_card = make_card(scroll_frame, padx=16, pady=16)
        activity_card.pack(fill="x", pady=(0, 8))
        tk.Label(activity_card, text="Активность за 7 дней", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w", pady=(0, 8))
        self.activity_canvas = tk.Text(activity_card, height=8, wrap="none", bg=CHAT_BG, fg=CHAT_FG, font=FONT_MONO, relief="flat", borderwidth=0)
        self.activity_canvas.pack(fill="x")
        self.activity_canvas.configure(state="disabled")

        # ── Minutes chart card ──
        minutes_card = make_card(scroll_frame, padx=16, pady=16)
        minutes_card.pack(fill="x", pady=(0, 8))
        tk.Label(minutes_card, text="Минуты за 7 дней", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w", pady=(0, 8))
        self.minutes_canvas = tk.Text(minutes_card, height=8, wrap="none", bg=CHAT_BG, fg=CHAT_FG, font=FONT_MONO, relief="flat", borderwidth=0)
        self.minutes_canvas.pack(fill="x")
        self.minutes_canvas.configure(state="disabled")

        # ── Error analytics card ──
        error_card = make_card(scroll_frame, padx=16, pady=16)
        error_card.pack(fill="x", pady=(0, 8))
        tk.Label(error_card, text="🔍 Анализ ошибок", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w", pady=(0, 8))
        self.error_canvas = tk.Text(error_card, height=8, wrap="word", bg=CHAT_BG, fg=CHAT_FG, font=FONT_MONO, relief="flat", borderwidth=0)
        self.error_canvas.pack(fill="x")
        self.error_canvas.configure(state="disabled")

        # ── Recent sessions card ──
        sessions_card = make_card(scroll_frame, padx=16, pady=16)
        sessions_card.pack(fill="x", pady=(0, 8))
        tk.Label(sessions_card, text="Последние сессии", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w", pady=(0, 8))
        self.session_list = tk.Text(sessions_card, height=10, wrap="word", bg=CHAT_BG, fg=CHAT_FG, font=FONT_MONO, relief="flat", borderwidth=0)
        self.session_list.pack(fill="x")
        self.session_list.configure(state="disabled")

        # ── Speaking review card ──
        speaking_card = make_card(scroll_frame, padx=16, pady=16)
        speaking_card.pack(fill="x", pady=(0, 8))
        tk.Label(speaking_card, text="Speaking Review", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        self.speaking_summary_label = tk.Label(speaking_card, text="", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_BODY, justify="left")
        self.speaking_summary_label.pack(anchor="w", pady=(8, 4))
        self.speaking_metrics_label = tk.Label(speaking_card, text="", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL, justify="left")
        self.speaking_metrics_label.pack(anchor="w", pady=(0, 4))
        self.speaking_avg_label = tk.Label(speaking_card, text="", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_BODY, justify="left")
        self.speaking_avg_label.pack(anchor="w", pady=(4, 8))
        tk.Label(speaking_card, text="Последний транскрипт", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack(anchor="w")
        self.review_transcript = tk.Text(speaking_card, height=4, wrap="word", bg=CHAT_BG, fg=CHAT_FG, font=FONT_MONO, relief="flat", borderwidth=0)
        self.review_transcript.pack(fill="x")
        self.review_transcript.configure(state="disabled")
        tk.Label(speaking_card, text="История", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack(anchor="w", pady=(8, 4))
        self.speaking_history = tk.Text(speaking_card, height=8, wrap="word", bg=CHAT_BG, fg=CHAT_FG, font=FONT_MONO, relief="flat", borderwidth=0)
        self.speaking_history.pack(fill="x")
        self.speaking_history.configure(state="disabled")

        # ── Error patterns card ──
        error_card = make_card(scroll_frame, padx=16, pady=16)
        error_card.pack(fill="x", pady=(0, 8))
        tk.Label(error_card, text="Анализ ошибок", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w", pady=(0, 8))
        self.error_patterns_label = tk.Label(error_card, text="", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_BODY, justify="left")
        self.error_patterns_label.pack(anchor="w")

        # ── Word Battle scores card ──
        game_card = make_card(scroll_frame, padx=16, pady=16)
        game_card.pack(fill="x", pady=(0, 8))
        tk.Label(game_card, text="⚔️ Рекорды Word Battle", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w", pady=(0, 8))
        self.game_scores_label = tk.Label(game_card, text="", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL, justify="left")
        self.game_scores_label.pack(anchor="w")

        # ── Survival Game progress card ──
        survival_card = make_card(scroll_frame, padx=16, pady=16)
        survival_card.pack(fill="x", pady=(0, 8))
        tk.Label(survival_card, text="🌍 Language Survival Game", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w", pady=(0, 8))
        self.survival_progress_label = tk.Label(survival_card, text="", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL, justify="left")
        self.survival_progress_label.pack(anchor="w")

        # ── Detective Game progress card ──
        detective_card = make_card(scroll_frame, padx=16, pady=16)
        detective_card.pack(fill="x", pady=(0, 8))
        tk.Label(detective_card, text="🕵️ Language Detective", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w", pady=(0, 8))
        self.detective_progress_label = tk.Label(detective_card, text="", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL, justify="left")
        self.detective_progress_label.pack(anchor="w")

        # ── Time Loop progress card ──
        timeloop_card = make_card(scroll_frame, padx=16, pady=16)
        timeloop_card.pack(fill="x", pady=(0, 8))
        tk.Label(timeloop_card, text="🔄 Time Loop Language", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w", pady=(0, 8))
        self.timeloop_progress_label = tk.Label(timeloop_card, text="", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL, justify="left")
        self.timeloop_progress_label.pack(anchor="w")

        # ── Badges card ──
        badges_card = make_card(scroll_frame, padx=16, pady=16)
        badges_card.pack(fill="x", pady=(0, 8))
        tk.Label(badges_card, text="🏆 Достижения", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w", pady=(0, 8))
        self.badges_label = tk.Label(badges_card, text="", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_BODY, justify="left")
        self.badges_label.pack(anchor="w")

        # ── Error journal card ──
        journal_card = make_card(scroll_frame, padx=16, pady=16)
        journal_card.pack(fill="x", pady=(0, 8))
        tk.Label(journal_card, text="📋 Журнал ошибок", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w", pady=(0, 8))
        self.error_journal_label = tk.Label(journal_card, text="", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_BODY, justify="left")
        self.error_journal_label.pack(anchor="w")

        # ── Weekly summary button ──
        summary_card = make_card(scroll_frame, padx=16, pady=16)
        summary_card.pack(fill="x", pady=(0, 8))
        make_button(summary_card, "📊 Недельный отчёт", self._show_weekly_summary).pack(anchor="w")

    # ─── Helpers ───

    def _make_option_menu(self, parent, variable, values, width=14):
        initial = variable.get().strip()
        if not initial and values:
            variable.set(values[0])
        option = tk.OptionMenu(parent, variable, *(values or [""]))
        option.configure(width=width, bg=CHAT_BG, fg=CHAT_FG, highlightthickness=1, relief="solid", borderwidth=1, font=FONT_BODY)
        option["menu"].configure(bg=CHAT_BG, fg=CHAT_FG)
        return option

    def _set_option_menu_values(self, option, variable, values):
        menu = option["menu"]
        menu.delete(0, "end")
        for value in values:
            menu.add_command(label=value, command=lambda selected=value: variable.set(selected))
        if values and variable.get() not in values:
            variable.set(values[0])

    def _append_chat(self, tag: str, text: str) -> None:
        self.chat.configure(state="normal")
        self.chat.insert("end", text, tag)
        self.chat.configure(state="disabled")
        self.chat.see("end")
        # Hide hint chips once chat has content
        if hasattr(self, "hint_chips_frame"):
            self.hint_chips_frame.pack_forget()

    def _fill_prompt(self, text: str) -> None:
        self.input.delete("1.0", "end")
        self.input.insert("1.0", text)
        self.input.focus_set()

    def _on_send_shortcut(self, event) -> str:
        self.send_message()
        return "break"

    def _show_typing(self) -> None:
        self._typing_dots = 0
        self._typing_active = True
        self._animate_typing()

    def _animate_typing(self) -> None:
        if not getattr(self, "_typing_active", False):
            return
        dots = "." * (self._typing_dots % 3 + 1)
        self.typing_label.configure(text=f"Ольга печатает{dots}")
        self._typing_dots += 1
        self.root.after(500, self._animate_typing)

    def _hide_typing(self) -> None:
        self._typing_active = False
        self.typing_label.configure(text="")

    def _notify_response_ready(self) -> None:
        """Play a subtle sound if the Practice tab is not active."""
        try:
            current_tab = self.notebook.index(self.notebook.select())
            if current_tab != 2:  # Practice tab index
                import subprocess
                subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def _show_quick_replies(self, response: str) -> None:
        for child in self.quick_replies_frame.winfo_children():
            child.destroy()
        replies = []
        r_lower = response.lower()
        if "?" in response:
            replies.append("Yes, I think so.")
            replies.append("Could you explain more?")
            replies.append("Can you give an example?")
        if "exercise" in r_lower or "задан" in r_lower or "fill" in r_lower:
            replies.append("Дай ответ")
            replies.append("Подсказка?")
        if "correct" in r_lower or "исправ" in r_lower or "ошибк" in r_lower:
            replies.append("Попробую ещё раз")
            replies.append("Объясни подробнее")
        if not replies:
            replies = ["Продолжим", "Следующее задание", "Повторим"]
        for reply in replies[:4]:
            make_button(self.quick_replies_frame, reply, lambda r=reply: self._fill_prompt(r)).pack(side="left", padx=(0, 4))

    def _show_chat_context_menu(self, event) -> None:
        try:
            self.chat.configure(state="normal")
            index = self.chat.index(f"@{event.x},{event.y}")
            line_start = f"{index} linestart"
            line_end = f"{index} lineend"
            word_start = self.chat.search(r'\S', index, backwards=True, stopindex=line_start)
            word_end = self.chat.search(r'\s', index, forwards=True, stopindex=line_end)
            if not word_start:
                word_start = line_start
            if not word_end:
                word_end = line_end
            selected = self.chat.get(word_start, word_end).strip().strip(".,!?;:\"'()")
            self.chat.configure(state="disabled")
            if not selected or len(selected) < 2:
                return
            menu = tk.Menu(self.root, tearoff=0, bg=CARD_BG, fg=TEXT_PRIMARY, activebackground=ACCENT, activeforeground="white", borderwidth=0)
            menu.add_command(label=f"🔊 Произнести \"{selected}\"", command=lambda: self._speak_word(selected))
            menu.add_command(label=f"📖 Перевести \"{selected}\"", command=lambda: self._translate_word(selected))
            menu.add_command(label=f"➕ В повторение \"{selected}\"", command=lambda: self._add_word_to_srs(selected))
            menu.tk_popup(event.x_root, event.y_root)
        except Exception:
            pass

    def _speak_word(self, word: str) -> None:
        if self.voice:
            self.voice.speak(word, "en")
        else:
            try:
                import subprocess
                subprocess.Popen(["say", "-v", "Samantha", "-r", "175", word], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    def _translate_word(self, word: str) -> None:
        try:
            from worddb import get_db
            db = get_db()
            results = db.search(word, limit=1)
            if results:
                w = results[0]
                msg = f"{w['word']} — {w.get('translation', '?')}"
                if w.get('ipa'):
                    msg += f" [{w['ipa']}]"
                if w.get('cefr'):
                    msg += f" ({w['cefr']})"
                self._append_chat("system", f"📖 {msg}\n\n")
            else:
                self._append_chat("system", f"📖 Слово \"{word}\" не найдено в базе.\n\n")
        except Exception:
            self._append_chat("system", f"📖 Не удалось найти перевод для \"{word}\".\n\n")

    def _add_word_to_srs(self, word: str) -> None:
        level = self.course.level
        card_id = f"vocab:{level}:{word.lower()}"
        if card_id in self.course.srs.cards:
            messagebox.showinfo("Слово", f"\"{word}\" уже в повторении.")
            return
        try:
            from worddb import get_db
            db = get_db()
            results = db.search(word, limit=1)
            if results:
                w = results[0]
                from srs import SRSCard
                self.course.srs.cards[card_id] = SRSCard(
                    word=w["word"],
                    translation=w.get("translation", ""),
                    example=w.get("example", ""),
                    ipa=w.get("ipa", ""),
                    collocations="",
                )
                self.course._save_srs()
                self._append_chat("system", f"➕ Слово \"{word}\" добавлено в повторение.\n\n")
            else:
                messagebox.showinfo("Слово", f"\"{word}\" не найдено в базе слов.")
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось добавить слово: {exc}")

    def _current_settings(self) -> CoachSettings:
        return CoachSettings(
            model=self.model_var.get().strip(),
            mode=self.mode_var.get().strip(),
            level=self.level_var.get().strip(),
            topic=self.topic_var.get().strip(),
            concise=self.concise_var.get(),
            practice_type=self.current_practice_type,
        )

    def _switch_to_tab(self, index: int) -> None:
        self.notebook.select(index)
        self._update_active_scroll_canvas(index)

    def _update_active_scroll_canvas(self, index: int | None = None) -> None:
        """Tell trackpad_scroll which canvas is currently visible."""
        try:
            import trackpad_scroll as ts
            if index is None:
                index = self.notebook.index(self.notebook.select())
            sf_map = {
                0: getattr(self, "_sf_dashboard", None),
                1: getattr(self, "_sf_learn", None),
                3: getattr(self, "_sf_games", None),
                4: getattr(self, "_sf_progress", None),
                5: getattr(self, "_sf_stories", None),
            }
            sf = sf_map.get(index)
            if sf is not None:
                ts.set_active_canvas(sf)
        except Exception:
            pass

    def _restore_window_geometry(self) -> None:
        import json
        geom_path = self.data_root / "window_geometry.json"
        if geom_path.exists():
            try:
                data = json.loads(geom_path.read_text(encoding="utf-8"))
                self.root.geometry(data.get("geometry", "1100x750"))
            except Exception:
                self.root.geometry("1100x750")
        else:
            self.root.geometry("1100x750")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _save_window_geometry(self) -> None:
        import json
        geom_path = self.data_root / "window_geometry.json"
        try:
            geom = self.root.geometry()
            geom_path.write_text(json.dumps({"geometry": geom}), encoding="utf-8")
        except Exception:
            pass

    def _show_toast(self, title: str, message: str, duration_ms: int = 3500) -> None:
        """Show a brief overlay toast notification inside the app window."""
        try:
            toast = tk.Toplevel(self.root)
            toast.overrideredirect(True)
            toast.attributes("-topmost", True)
            toast.attributes("-alpha", 0.93)
            rw = self.root.winfo_width()
            rx = self.root.winfo_rootx()
            ry = self.root.winfo_rooty()
            tw, th = 360, 64
            tx = rx + rw - tw - 24
            ty = ry + 24
            toast.geometry(f"{tw}x{th}+{tx}+{ty}")
            frame = tk.Frame(toast, bg=ACCENT, padx=14, pady=10)
            frame.pack(fill="both", expand=True)
            tk.Label(frame, text=title, bg=ACCENT, fg="white",
                     font=FONT_HEADING).pack(anchor="w")
            tk.Label(frame, text=message, bg=ACCENT, fg="white",
                     font=FONT_SMALL, wraplength=320).pack(anchor="w")
            toast.after(duration_ms, toast.destroy)
            # Fade out last 500ms
            def _fade(alpha=0.93):
                try:
                    if alpha > 0.05:
                        toast.attributes("-alpha", alpha)
                        toast.after(40, lambda: _fade(alpha - 0.05))
                    else:
                        toast.destroy()
                except Exception:
                    pass
            toast.after(duration_ms - 500, _fade)
        except Exception:
            pass

    def _send_macos_notification(self, title: str, body: str) -> None:
        """Send a macOS system notification via osascript (no extra deps)."""
        try:
            import subprocess
            script = f'display notification "{body}" with title "{title}" sound name "Glass"'
            subprocess.Popen(["osascript", "-e", script],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def _check_daily_reminder(self) -> None:
        """Send a macOS notification if daily goal not yet met today."""
        try:
            if not self.course.daily_goal_met():
                streak = self.course.streak_days()
                if streak > 0:
                    msg = f"Серия {streak} дней под угрозой! Позанимайся сегодня."
                else:
                    msg = "Не забудь про сегодняшнюю практику английского!"
                self._send_macos_notification(f"{COACH_NAME} напоминает", msg)
        except Exception:
            pass

    def _on_close(self) -> None:
        self._save_window_geometry()
        try:
            self._autosave_chat()
        except Exception:
            pass
        try:
            self.course._save_srs()
        except Exception:
            pass
        try:
            import trackpad_scroll as ts
            ts.remove_monitor()
        except Exception:
            pass
        logger.info("Application closed by user")
        try:
            duration = time.time() - self._session_start
            self.analytics.track_session_duration(duration)
        except Exception:
            pass
        self.root.destroy()

    # ─── License & Ollama Setup ───

    def _check_license_and_start(self) -> None:
        """Check license status, then Ollama, then bootstrap.
        License never blocks the app on this machine."""
        lic = self.license
        if lic.is_activated:
            self._check_ollama_and_start()
            return
        if lic.is_trial_active:
            days = lic.trial_days_left
            if days <= 3:
                self._append_chat("system",
                    f"⏳ Пробный период: осталось {days} дн. "
                    f"Активируйте лицензию в Настройках.\n\n")
        else:
            self._append_chat("system",
                "💡 Лицензия не активирована, но приложение работает без ограничений.\n\n")
        self._check_ollama_and_start()

    def _check_ollama_and_start(self) -> None:
        """Check if Ollama is installed; if not, show install dialog.
        Runs checks in a background thread to avoid blocking the main thread
        (which would break scroll and UI responsiveness)."""
        self.status_var.set("Проверяю Ollama...")
        def _worker():
            installed = ollama_inst.is_ollama_installed()
            running = ollama_inst.is_ollama_running() if installed else False
            if installed and running:
                self.root.after(0, self._bootstrap)
                return
            if installed and not running:
                self.root.after(0, lambda: self.status_var.set("Запускаю Ollama..."))
                ok, _ = ollama_inst.launch_ollama()
                if ok:
                    self.root.after(0, self._bootstrap)
                    return
            # Not installed or launch failed — show dialog on main thread
            self.root.after(0, self._show_ollama_install_dialog)

        threading.Thread(target=_worker, daemon=True).start()

    def _show_ollama_install_dialog(self) -> None:
        """Show Ollama installation dialog with progress."""
        win = tk.Toplevel(self.root)
        win.title("Установка Ollama")
        win.geometry("500x380")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        win.configure(bg=BG)

        tk.Label(win, text="🤖", bg=BG, fg=ACCENT, font=("SF Pro Display", 40)).pack(pady=(20, 4))
        tk.Label(win, text="Установка Ollama", bg=BG, fg=TEXT_PRIMARY,
                 font=FONT_HEADING).pack()
        tk.Label(win, text="Ольга использует локальную AI-модель Ollama.\n"
                           "Нажмите «Установить» — всё произойдёт автоматически.\n"
                           "Размер: ~250 МБ. Потребуется интернет.",
                 bg=BG, fg=TEXT_SECONDARY, font=FONT_BODY,
                 justify="center", wraplength=440).pack(pady=(8, 12))

        status_var = tk.StringVar(value="Готово к установке")
        tk.Label(win, textvariable=status_var, bg=BG, fg=TEXT_MUTED,
                 font=FONT_SMALL, wraplength=440, justify="center").pack(pady=(0, 8))

        progress = tk.IntVar(value=0)
        bar = ttk.Progressbar(win, variable=progress, maximum=100, length=400)
        bar.pack(pady=(0, 16))

        def _install():
            install_btn.configure(state="disabled")
            skip_btn.configure(state="disabled")
            status_var.set("Скачиваю Ollama...")

            def _progress(stage, detail):
                if stage == "download":
                    status_var.set("Скачиваю Ollama... (это может занять пару минут)")
                elif stage == "download_progress":
                    try:
                        downloaded, total = detail.split("/")
                        downloaded = int(downloaded)
                        total = int(total)
                        if total > 0:
                            pct = int(downloaded / total * 100)
                            progress.set(pct)
                            status_var.set(f"Скачиваю... {pct}%")
                    except Exception:
                        pass
                elif stage == "install":
                    progress.set(100)
                    status_var.set("Устанавливаю...")
                elif stage == "launch":
                    status_var.set("Запускаю Ollama...")
                elif stage == "done":
                    status_var.set("Ollama готова!")

            def _worker():
                ok, msg = ollama_inst.full_install(progress_callback=_progress)
                if ok:
                    status_var.set("✅ Ollama установлена и запущена!")
                    progress.set(100)
                    self.root.after(1000, lambda: (win.destroy(), self._bootstrap()))
                else:
                    status_var.set(f"❌ {msg}")
                    self.root.after(2000, lambda: (
                        install_btn.configure(state="normal"),
                        skip_btn.configure(state="normal"),
                    ))

            threading.Thread(target=_worker, daemon=True).start()

        btn_frame = tk.Frame(win, bg=BG)
        btn_frame.pack(fill="x", padx=24, pady=(0, 16))
        install_btn = make_button(btn_frame, "Установить Ollama", _install, accent=True)
        install_btn.pack(side="right")
        skip_btn = make_button(btn_frame, "Пропустить", lambda: (win.destroy(), self._bootstrap()))
        skip_btn.pack(side="left")

    # ─── Bootstrap & Queue ───

    def _bootstrap(self) -> None:
        threading.Thread(target=self._bootstrap_services, daemon=True).start()
        self._append_chat("system", f"{COACH_NAME} готовит локальную AI-модель. Первое обращение: «{START_COMMAND}».\n\n")
        self._animate_status_loading()

    def _animate_status_loading(self) -> None:
        """Animate dots in status bar while Ollama is not yet connected."""
        if self._ollama_ok:
            return
        current = self.status_var.get()
        base = "Подключаюсь к Ollama"
        dots = (current.count(".") % 3) + 1
        self.status_var.set(base + "." * dots)
        self.root.after(600, self._animate_status_loading)

    def _bootstrap_services(self) -> None:
        voice_ok, voice_message = self.voice.compile_if_needed()
        self.response_queue.put(("system", f"{voice_message}\n\n"))
        if not voice_ok:
            self.response_queue.put(("error", voice_message))
        self._connect_and_load_models()

    def _connect_and_load_models(self) -> None:
        ok, message = self.client.ensure_server()
        self.response_queue.put(("status", message))
        if not ok:
            self.response_queue.put(("ollama_down", ""))
            return
        self.response_queue.put(("ollama_up", ""))
        models = self.client.list_models()
        if not models:
            self.response_queue.put((
                "system",
                "Локальные модели не найдены.\n"
                "Установите одну из моделей:\n"
                f"- ollama pull {DEFAULT_MODEL_SUGGESTIONS[0]}\n"
                f"- ollama pull {DEFAULT_MODEL_SUGGESTIONS[1]}\n\n",
            ))
        else:
            auto = self.client.auto_select_model()
            if auto:
                self.response_queue.put(("auto_model", auto))
        self.response_queue.put(("models", json.dumps(models)))

    def _schedule_reconnect(self) -> None:
        """Check Ollama every 10s and reconnect automatically if it comes back.
        If another app started Ollama, we wait for it — we don't restart it."""
        if self._ollama_ok:
            self._reconnect_pending = False
            return
        def _try():
            ok, msg = self.client.restart_server_if_ours()
            if ok:
                self.response_queue.put(("ollama_up", ""))
                threading.Thread(target=self._connect_and_load_models, daemon=True).start()
            else:
                self.response_queue.put(("status", msg))
                self.root.after(10_000, self._schedule_reconnect)
        threading.Thread(target=_try, daemon=True).start()

    def _schedule_daily_reminder(self) -> None:
        """Schedule a daily goal reminder check at 19:00 local time."""
        from datetime import datetime as dt, timedelta
        try:
            now = dt.now()
            target = now.replace(hour=19, minute=0, second=0, microsecond=0)
            if now >= target:
                target = target + timedelta(days=1)
            ms = int((target - now).total_seconds() * 1000)
            self.root.after(ms, self._check_daily_reminder)
            # Reschedule for next day
            self.root.after(ms + 1000, self._schedule_daily_reminder)
        except Exception:
            pass

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.response_queue.get_nowait()
                if kind == "ollama_up":
                    self._ollama_ok = True
                    self._reconnect_pending = False
                    self.status_var.set(f"{COACH_NAME} готова к практике")
                elif kind == "ollama_down":
                    self._ollama_ok = False
                    self.status_var.set("⚠️ Ollama недоступна — ожидаю...")
                    self._append_chat("system",
                        "⚠️ Ollama не отвечает.\n"
                        "Если Ollama запущена другим приложением — ожидаю её восстановления.\n"
                        "Если Ollama не установлена — установите через Настройки.\n"
                        "Приложение автоматически переподключится.\n\n")
                    if not self._reconnect_pending:
                        self._reconnect_pending = True
                        self.root.after(10_000, self._schedule_reconnect)
                elif kind == "status":
                    self.status_var.set(payload)
                elif kind == "auto_model":
                    if not self.model_var.get() or self.model_var.get() not in (self.models or []):
                        self.model_var.set(payload)
                        self.status_var.set(f"Авто-выбрана модель: {payload}")
                elif kind == "models":
                    models = json.loads(payload)
                    self.models = models
                    self._set_option_menu_values(self.model_combo, self.model_var, models or DEFAULT_MODEL_SUGGESTIONS)
                    if models:
                        self.model_var.set(models[0])
                    elif not self.model_var.get():
                        self.model_var.set(DEFAULT_MODEL_SUGGESTIONS[0])
                elif kind == "stream_chunk":
                    self.chat.configure(state="normal")
                    if not hasattr(self, "_streaming_active") or not self._streaming_active:
                        self.chat.insert("end", f"{COACH_NAME}:\n", "assistant")
                        self._streaming_active = True
                        self._stream_voice_buffer = ""
                        if self.voice_output_var.get():
                            self.voice.stop_speaking()
                    self.chat.insert("end", payload, "assistant")
                    self.chat.see("end")
                    self.chat.configure(state="disabled")
                    if self.voice_output_var.get():
                        self._stream_voice_buffer += payload
                        while ". " in self._stream_voice_buffer or "!" in self._stream_voice_buffer or "?" in self._stream_voice_buffer:
                            for delim in [". ", "! ", "? "]:
                                idx = self._stream_voice_buffer.find(delim)
                                if idx >= 0:
                                    sentence = self._stream_voice_buffer[:idx + len(delim)].strip()
                                    self._stream_voice_buffer = self._stream_voice_buffer[idx + len(delim):]
                                    if sentence and len(sentence) > 10:
                                        text = extract_speakable_text(sentence)
                                        if text:
                                            lang = "ru-RU" if re.search(r"[А-Яа-яЁё]", text) else "en-US"
                                            voice_name = self.tts_voice_var.get()
                                            threading.Thread(target=self.voice.speak, args=(text, lang, 0, voice_name), daemon=True).start()
                                    break
                            else:
                                break
                elif kind == "assistant_done":
                    self._ollama_ok = True
                    self._reconnect_pending = False
                    if hasattr(self, "_streaming_active") and self._streaming_active:
                        self.chat.configure(state="normal")
                        self.chat.insert("end", "\n\n", "assistant")
                        self.chat.configure(state="disabled")
                        self._streaming_active = False
                    else:
                        self._append_chat("assistant", f"{COACH_NAME}:\n{payload}\n\n")
                    if self.voice_output_var.get():
                        if hasattr(self, "_stream_voice_buffer") and self._stream_voice_buffer.strip():
                            remaining = self._stream_voice_buffer.strip()
                            self._stream_voice_buffer = ""
                            text = extract_speakable_text(remaining)
                            if text and len(text) > 5:
                                if self._is_dialogue_text(text):
                                    voice_a = self.tts_voice_var.get()
                                    voice_b = self.tts_voice2_var.get()
                                    threading.Thread(target=self.voice.speak_dialogue,
                                                     args=(text, voice_a, voice_b, 0), daemon=True).start()
                                else:
                                    lang = "ru-RU" if re.search(r"[А-Яа-яЁё]", text) else "en-US"
                                    voice_name = self.tts_voice_var.get()
                                    threading.Thread(target=self.voice.speak, args=(text, lang, 0, voice_name), daemon=True).start()
                        elif not hasattr(self, "_stream_voice_buffer"):
                            self._speak_response(payload)
                    self.status_var.set(f"{COACH_NAME} готова к практике")
                    self.is_generating = False
                    self.send_btn.configure(state="normal")
                    self._hide_typing()
                    self._show_quick_replies(payload)
                    self._autosave_chat()
                    self._notify_response_ready()
                elif kind == "assistant":
                    self._append_chat("assistant", f"{COACH_NAME}:\n{payload}\n\n")
                    if self.voice_output_var.get():
                        self._speak_response(payload)
                    self.status_var.set(f"{COACH_NAME} готова к практике")
                    self.is_generating = False
                    self.send_btn.configure(state="normal")
                    self._hide_typing()
                    self._show_quick_replies(payload)
                    self._autosave_chat()
                    self._notify_response_ready()
                elif kind == "badge":
                    self._show_toast("🎉 Новое достижение!", payload)
                    self._send_macos_notification("🎉 Достижение разблокировано", payload)
                elif kind == "story_text":
                    self._story_loading = False
                    self.story_text.configure(state="normal")
                    self.story_text.delete("1.0", "end")
                    self.story_text.insert("end", payload)
                    self.story_text.configure(state="disabled")
                    if self.voice_output_var.get():
                        text = extract_speakable_text(payload, max_lines=0)
                        if text:
                            if self._is_dialogue_text(text):
                                voice_a = self.tts_voice_var.get()
                                voice_b = self.tts_voice2_var.get()
                                threading.Thread(target=self.voice.speak_dialogue,
                                                 args=(text, voice_a, voice_b, 0), daemon=True).start()
                            else:
                                voice_name = self.tts_voice_var.get()
                                threading.Thread(target=self.voice.speak, args=(text, "en-US", 0, voice_name), daemon=True).start()
                elif kind == "story_qa":
                    self.story_qa_result.configure(state="normal")
                    self.story_qa_result.delete("1.0", "end")
                    self.story_qa_result.insert("end", payload)
                    self.story_qa_result.configure(state="disabled")
                    self.status_var.set(f"{COACH_NAME} готова к практике")
                elif kind == "course":
                    self._refresh_all()
                elif kind == "transcript":
                    self._fill_prompt(payload)
                    self.pending_voice_input = True
                    self.status_var.set("Речь распознана")
                elif kind == "system":
                    self._append_chat("system", payload)
                elif kind == "error":
                    self._append_chat("system", f"Ошибка: {payload}\n\n")
                    self.status_var.set("Проблема с локальной моделью")
                    self.is_generating = False
                    self.send_btn.configure(state="normal")
                    # Check if Ollama is down and trigger reconnect
                    if not self.client.is_server_running():
                        self._ollama_ok = False
                        if not self._reconnect_pending:
                            self._reconnect_pending = True
                            self._append_chat("system",
                                "⚠️ Ollama не отвечает. Приложение автоматически переподключится.\n\n")
                            self.root.after(5_000, self._schedule_reconnect)
                elif kind == "diglot_story":
                    self._display_diglot_story(payload)
                    self.status_var.set(f"{COACH_NAME} готова к практике")
                elif kind == "diglot_qa":
                    self.diglot_qa_result.configure(state="normal")
                    self.diglot_qa_result.delete("1.0", "end")
                    self.diglot_qa_result.insert("end", payload)
                    self.diglot_qa_result.configure(state="disabled")
                    self.status_var.set(f"{COACH_NAME} готова к практике")
                elif kind == "diglot_error":
                    self.diglot_text.configure(state="normal")
                    self.diglot_text.delete("1.0", "end")
                    self.diglot_text.insert("end", f"Ошибка: {payload}\n", "muted")
                    self.diglot_text.configure(state="disabled")
                    self.status_var.set("Проблема с локальной моделью")
        except queue.Empty:
            pass
        finally:
            self.root.after(150, self._poll_queue)

    # ─── Refresh UI ───

    def _refresh_all(self) -> None:
        self._refresh_dashboard()
        self._refresh_learn()
        self._refresh_progress()

    def _refresh_dashboard(self) -> None:
        c = self.course
        from datetime import date, timedelta

        # ── Streak milestone check ──
        try:
            milestone = c.streak_milestone_reached()
            if milestone:
                days, bonus = milestone
                self._show_streak_milestone_popup(days, bonus)
        except Exception:
            pass

        # ── Streak card ──
        streak = c.streak_days()
        today_min = c.today_minutes()
        goal_min = int(c.state.get("daily_goal_minutes", 20))
        self.dash_streak_num.configure(text=f"🔥 {streak}")
        done_today = today_min >= goal_min
        best = c.best_streak_days()
        record_str = f"  |  🏆 Рекорд: {best} дн." if best > 1 else ""
        sub = f"Сегодня: {today_min}/{goal_min} мин  {'✅' if done_today else '⏳'}{record_str}"
        self.dash_streak_sub.configure(text=sub)

        # 7-day dots — last 7 days, today rightmost
        activity = c.state.get("daily_activity", {})
        today = date.today()
        days_of_week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        for i, (dot, lbl) in enumerate(self._streak_dots):
            day = today - timedelta(days=6 - i)
            iso = day.isoformat()
            active = activity.get(iso, 0) > 0
            dot.configure(bg=SUCCESS if active else BORDER)
            lbl.configure(text=days_of_week[day.weekday()])

        # ── Status card ──
        self.dash_level_label.configure(text=f"Уровень: {c.level} → {c.target_level}  |  Can-do: {CEFR_CAN_DO.get(c.level, '')[:60]}...")
        self.dash_streak_label.configure(text=f"Серия дней: {streak}  |  Сегодня: {today_min} мин / {goal_min} мин")
        self.dash_goal_label.configure(text=f"День {c.days_elapsed()} из {c.state['goal_days']}  |  Осталось: {c.days_left()} дн.  |  Сессий: {c.state['completed_sessions']}")
        pct = c.completion_percent()
        self.dash_progress_label.configure(text=f"Общий прогресс курса: {pct}%")
        bar_width = self.dash_progress_bar.winfo_width()
        if bar_width <= 1:
            bar_width = 600
        self.dash_progress_fill.place(x=0, y=0, width=max(1, int(bar_width * pct / 100)))

        for skill in SKILLS:
            score = c.skill_score(skill)
            bar = self.skill_bars[skill]
            bar.place(x=0, y=0, width=max(1, int(200 * score / 100)))
            self.skill_labels[skill].configure(text=f"{score}%")

        practice_type, rec_text = c.recommended_practice(self.topic_var.get())
        self.dash_rec_label.configure(text=f"{PRACTICE_RU.get(practice_type, practice_type)}: {rec_text}")
        self._recommended_practice_type = practice_type
        self._recommended_practice_text = rec_text

        # Word of the Day
        wotd = c.word_of_day()
        if wotd:
            self.wotd_word_label.configure(text=wotd.get("word", ""))
            self.wotd_ipa_label.configure(text=wotd.get("ipa", ""))
            self.wotd_translation_label.configure(text=wotd.get("translation", ""))
            self.wotd_example_label.configure(text=wotd.get("example", ""))
            self._wotd_word = wotd.get("word", "")
        else:
            self.wotd_word_label.configure(text="—")
            self.wotd_ipa_label.configure(text="")
            self.wotd_translation_label.configure(text="База слов недоступна")
            self.wotd_example_label.configure(text="")
            self._wotd_word = ""

        # Idiom of the Day
        try:
            idiom, trans, example = self.course.idiom_of_day()
            self.idiom_text_label.configure(text=idiom)
            self.idiom_trans_label.configure(text=trans)
            self.idiom_example_label.configure(text=example)
            self._current_idiom = idiom
        except Exception:
            pass

        # Daily Challenge
        try:
            ch_type, ch_text, ch_cat = self.course.daily_challenge()
            done = self.course.daily_challenge_completed()
            self.challenge_category_label.configure(text=ch_cat)
            self.challenge_text_label.configure(text=ch_text)
            self.challenge_status_label.configure(text="✅ Выполнено" if done else "⏳ Не выполнено")
        except Exception:
            pass

        # Update actions level label
        try:
            self.actions_level_label.configure(text=f"Уровень: {self.course.level}")
        except Exception:
            pass

        # XP / Weekly goal
        try:
            weekly_xp = self.course.weekly_xp_total()
            goal = self.course.weekly_xp_goal()
            total = self.course.total_xp()
            today_xp = self.course.daily_xp()
            self.xp_total_label.configure(text=f"{weekly_xp}/{goal} XP")
            pct = min(100, int(weekly_xp * 100 / max(1, goal)))
            self.xp_bar_fill.place(x=0, y=0, width=max(1, int(300 * pct / 100)))
            if pct >= 100:
                self.xp_goal_label.configure(text="🎉 Недельная цель достигнута!")
            else:
                self.xp_goal_label.configure(text=f"До цели: {goal - weekly_xp} XP")
            self.xp_today_label.configure(text=f"Сегодня: +{today_xp} XP  |  Всего: {total} XP")
        except Exception:
            pass

    def _refresh_learn(self) -> None:
        c = self.course
        level = c.level

        # SRS status
        due = c.srs_due_count()
        new = c.srs_new_count()
        mastered = c.srs.mastered_count()
        total = len(c.srs.cards)
        db_total = c.db_word_count()
        vocab_learned, vocab_total = c.vocab_progress()
        avg_mastery = c.srs.average_mastery()
        self.srs_status_label.configure(text=f"К повторению: {due}  |  Новых: {new}  |  Освоено: {mastered} из {total}  |  База: {db_total} слов")
        if vocab_total > 0:
            self.srs_detail_label.configure(text=f"Среднее усвоение: {int(avg_mastery * 100)}%  |  Слов уровня {level} выучено: {vocab_learned} из {vocab_total}")
        else:
            self.srs_detail_label.configure(text=f"Среднее усвоение: {int(avg_mastery * 100)}%")

        # Grammar
        completed, total_g = c.grammar_progress()
        self.grammar_progress_label.configure(text=f"Освоено: {completed} из {total_g} тем")
        for child in self.grammar_container.winfo_children():
            child.destroy()
        for gp in grammar_for_level(level):
            row = tk.Frame(self.grammar_container, bg=CARD_BG)
            row.pack(fill="x", pady=2)
            done = gp.id in c.state.get("grammar_completed", [])
            marker = "✅" if done else "⬜"
            tk.Label(row, text=marker, bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_SMALL).pack(side="left")
            tk.Label(row, text=gp.title, bg=CARD_BG, fg=TEXT_PRIMARY if not done else TEXT_MUTED, font=FONT_SMALL).pack(side="left", padx=(4, 0))
            if not done:
                make_button(row, "Учить", lambda gid=gp.id: self._learn_grammar(gid), ).pack(side="right")

        # Vocabulary
        for child in self.vocab_container.winfo_children():
            child.destroy()
        for vset in vocabulary_for_level(level):
            row = tk.Frame(self.vocab_container, bg=CARD_BG)
            row.pack(fill="x", pady=2)
            done = vset.theme in c.state.get("vocab_themes_completed", [])
            marker = "✅" if done else "⬜"
            tk.Label(row, text=marker, bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_SMALL).pack(side="left")
            tk.Label(row, text=f"{vset.theme} ({len(vset.cards)} слов)", bg=CARD_BG, fg=TEXT_PRIMARY if not done else TEXT_MUTED, font=FONT_SMALL).pack(side="left", padx=(4, 0))
            make_button(row, "Изучить", lambda theme=vset.theme: self._learn_vocab(theme)).pack(side="right")

        # Functions
        for child in self.func_container.winfo_children():
            child.destroy()
        for fs in functions_for_level(level):
            row = tk.Frame(self.func_container, bg=CARD_BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"🎯 {fs.function}", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_SMALL).pack(side="left")
            make_button(row, "Практика", lambda fn=fs.function, sc=fs.scenario: self._practice_function(fn, sc)).pack(side="right")

    def _build_stories(self) -> None:
        frame = self.stories_frame
        scroll_frame = ctk.CTkScrollableFrame(frame, fg_color=BG, scrollbar_button_color=BORDER,
                                              scrollbar_button_hover_color=ACCENT)
        scroll_frame.pack(fill="both", expand=True, padx=0, pady=0)
        self._sf_stories = scroll_frame

        # ── Generator card ──
        gen_card = make_card(scroll_frame, padx=16, pady=16)
        gen_card.pack(fill="x", pady=(0, 8))
        tk.Label(gen_card, text="📖 AI-рассказы с вашими словами", bg=CARD_BG, fg=TEXT_PRIMARY,
                 font=FONT_HEADING).pack(anchor="w")
        tk.Label(gen_card, text="Ольга сгенерирует рассказ, используя слова из вашего SRS.",
                 bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL, wraplength=700, justify="left").pack(anchor="w", pady=(4, 8))

        # Topic input
        topic_row = tk.Frame(gen_card, bg=CARD_BG)
        topic_row.pack(fill="x", pady=(0, 8))
        tk.Label(topic_row, text="Тема:", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack(side="left")
        self.story_topic_var = tk.StringVar(value="")
        topic_entry = tk.Entry(topic_row, textvariable=self.story_topic_var, bg=CHAT_BG, fg=CHAT_FG,
                               relief="solid", borderwidth=1, font=FONT_BODY, width=30)
        topic_entry.pack(side="left", padx=(8, 12))
        tk.Label(topic_row, text="(необязательно)", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL).pack(side="left")

        # SRS words preview
        self.story_words_label = tk.Label(gen_card, text="", bg=CARD_BG, fg=TEXT_MUTED,
                                          font=FONT_SMALL, wraplength=700, justify="left")
        self.story_words_label.pack(anchor="w", pady=(0, 8))

        # Buttons
        btn_row = tk.Frame(gen_card, bg=CARD_BG)
        btn_row.pack(fill="x")
        make_button(btn_row, "✨ Сгенерировать рассказ", self._generate_story, accent=True).pack(side="left", padx=(0, 8))
        make_button(btn_row, "🔊 Озвучить", self._speak_story).pack(side="left", padx=(0, 8))
        make_button(btn_row, "➕ Слова в SRS", self._add_story_words_to_srs).pack(side="left")

        # ── Story display card ──
        story_card = make_card(scroll_frame, padx=16, pady=16)
        story_card.pack(fill="both", expand=True, pady=(0, 8))
        self.story_text = tk.Text(story_card, wrap="word", bg=CHAT_BG, fg=CHAT_FG,
                                  font=FONT_BODY, padx=12, pady=12, relief="flat", borderwidth=0,
                                  height=20, state="disabled")
        self.story_text.pack(fill="both", expand=True)
        self.story_text.tag_configure("title", foreground=TEXT_PRIMARY, font=FONT_HEADING)
        self.story_text.tag_configure("muted", foreground=TEXT_MUTED, font=FONT_SMALL)
        self.story_text.tag_configure("bold", font=("SF Pro Text", 12, "bold"))

        # ── Comprehension Q&A card ──
        qa_card = make_card(scroll_frame, padx=16, pady=16)
        qa_card.pack(fill="x", pady=(0, 8))
        tk.Label(qa_card, text="💬 Вопрос по рассказу", bg=CARD_BG, fg=TEXT_PRIMARY,
                 font=FONT_HEADING).pack(anchor="w")
        tk.Label(qa_card, text="Задайте вопрос по содержанию рассказа — Ольга ответит.",
                 bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL, wraplength=700, justify="left").pack(anchor="w", pady=(4, 8))
        qa_input_row = tk.Frame(qa_card, bg=CARD_BG)
        qa_input_row.pack(fill="x", pady=(0, 4))
        self.story_qa_var = tk.StringVar()
        qa_entry = tk.Entry(qa_input_row, textvariable=self.story_qa_var, bg=CHAT_BG, fg=CHAT_FG,
                            relief="solid", borderwidth=1, font=FONT_BODY)
        qa_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        qa_entry.bind("<Return>", lambda e: self._ask_story_question())
        make_button(qa_input_row, "Спросить", self._ask_story_question, accent=True).pack(side="left")
        self.story_qa_result = tk.Text(qa_card, wrap="word", bg=CHAT_BG, fg=CHAT_FG,
                                       font=FONT_BODY, padx=8, pady=8, relief="flat", borderwidth=0,
                                       height=4, state="disabled")
        self.story_qa_result.pack(fill="x", pady=(4, 0))

        # ── Web reading card (moved here for unified reading experience) ──
        web_card = make_card(scroll_frame, padx=16, pady=16)
        web_card.pack(fill="x", pady=(0, 8))
        tk.Label(web_card, text="🌐 Чтение веб-статей", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        tk.Label(web_card, text="Вставьте URL статьи на английском — Ольга адаптирует под ваш уровень.",
                 bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL, wraplength=700, justify="left").pack(anchor="w", pady=(4, 8))
        web_row = tk.Frame(web_card, bg=CARD_BG)
        web_row.pack(fill="x", pady=(0, 4))
        self.web_url_var = tk.StringVar()
        web_entry = tk.Entry(web_row, textvariable=self.web_url_var, bg=CHAT_BG, fg=CHAT_FG,
                             relief="solid", borderwidth=1, font=FONT_BODY, width=50)
        web_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        web_entry.bind("<Return>", lambda e: self._read_web_article())
        make_button(web_row, "Читать", self._read_web_article, accent=True).pack(side="left")

        # ── Dictation card ──
        dict_card = make_card(scroll_frame, padx=16, pady=16)
        dict_card.pack(fill="x", pady=(0, 8))
        tk.Label(dict_card, text="✍️ Диктант", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        tk.Label(dict_card, text="Ольга произносит предложение — вы печатаете то, что услышали.",
                 bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL, wraplength=700, justify="left").pack(anchor="w", pady=(4, 8))
        dict_btn_row = tk.Frame(dict_card, bg=CARD_BG)
        dict_btn_row.pack(fill="x", pady=(0, 8))
        make_button(dict_btn_row, "▶ Новое предложение", self._new_dictation, accent=True).pack(side="left", padx=(0, 4))
        make_button(dict_btn_row, "🔊 Повторить", self._replay_dictation).pack(side="left", padx=(0, 4))
        make_button(dict_btn_row, "🐢 Медленно", lambda: self._replay_dictation(slow=True)).pack(side="left")
        self.dictation_entry = tk.Entry(dict_card, bg=CHAT_BG, fg=CHAT_FG, relief="solid", borderwidth=1, font=FONT_BODY)
        self.dictation_entry.pack(fill="x", pady=(0, 4))
        self.dictation_entry.bind("<Return>", lambda e: self._check_dictation())
        make_button(dict_card, "Проверить", self._check_dictation).pack(anchor="w")
        self.dictation_result_label = tk.Label(dict_card, text="", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL, wraplength=700, justify="left")
        self.dictation_result_label.pack(anchor="w", pady=(8, 0))

    def _refresh_progress(self) -> None:
        c = self.course
        self.stats_overview_label.configure(
            text=(
                f"Сессий: {c.state['completed_sessions']}  |  "
                f"Голосовых: {c.voice_share_percent()}%  |  "
                f"Всего минут: {c.state['total_minutes']}\n"
                f"Ср. ввод: {c.avg_user_words()} слов  |  "
                f"Ср. ответ: {c.avg_assistant_words()} слов"
            )
        )
        self.stats_secondary_label.configure(
            text=(
                f"Сильная зона: {SKILL_RU.get(c.strongest_skill(), c.strongest_skill())}  |  "
                f"Слабая зона: {SKILL_RU.get(c.weakest_skill(), c.weakest_skill())}  |  "
                f"Активных дней: {len(c.state.get('active_days', []))}"
            )
        )

        # Heatmap (GitHub-style)
        for child in self.heatmap_frame.winfo_children():
            child.destroy()
        hm_data = c.heatmap_data(13)
        # Day labels
        day_labels = ["Пн", "", "Ср", "", "Пт", "", "Вс"]
        label_col = tk.Frame(self.heatmap_frame, bg=CARD_BG)
        label_col.pack(side="left", padx=(0, 4))
        for dl in day_labels:
            tk.Label(label_col, text=dl, bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL, width=3).pack(pady=1)
        # Week columns
        for week_idx in range(13):
            col = tk.Frame(self.heatmap_frame, bg=CARD_BG)
            col.pack(side="left", padx=1)
            for day_idx in range(7):
                cell_idx = week_idx * 7 + day_idx
                if cell_idx >= len(hm_data):
                    break
                date_iso, dow, mins = hm_data[cell_idx]
                if mins == 0:
                    bg = BORDER
                elif mins < 10:
                    bg = "#2d4a2d"
                elif mins < 20:
                    bg = "#4a8c4a"
                elif mins < 40:
                    bg = "#6bcf6b"
                else:
                    bg = "#2dd42d"
                cell = tk.Label(col, text="  ", bg=bg, width=2, height=1, relief="flat")
                cell.pack(pady=1)
                # Tooltip on hover
                date_str = date_iso.split("T")[0] if "T" in date_iso else date_iso
                cell.bind("<Enter>", lambda e, w=cell, d=date_str, m=mins: w.configure(text=str(m) if m else "·"))
                cell.bind("<Leave>", lambda e, w=cell: w.configure(text="  "))

        # Activity chart
        data = c.daily_chart_data(7)
        max_val = max([v for _, v in data] + [1])
        lines = ["Сессии по дням"]
        for label, val in data:
            bar = "█" * int((val * 20) / max_val) if val else "·"
            lines.append(f"{label} │{bar} ({val})")
        self.activity_canvas.configure(state="normal")
        self.activity_canvas.delete("1.0", "end")
        self.activity_canvas.insert("1.0", "\n".join(lines))
        self.activity_canvas.configure(state="disabled")

        # Minutes chart
        mdata = c.daily_minutes_chart_data(7)
        max_m = max([v for _, v in mdata] + [1])
        mlines = ["Минуты по дням"]
        for label, val in mdata:
            bar = "█" * int((val * 20) / max_m) if val else "·"
            mlines.append(f"{label} │{bar} ({val}м)")
        self.minutes_canvas.configure(state="normal")
        self.minutes_canvas.delete("1.0", "end")
        self.minutes_canvas.insert("1.0", "\n".join(mlines))
        self.minutes_canvas.configure(state="disabled")

        # Error analytics
        error_names = {
            "tense": "Времена (tenses)",
            "article": "Артикли (a/an/the)",
            "preposition": "Предлоги (prepositions)",
            "word_order": "Порядок слов",
            "spelling": "Орфография",
            "plural": "Множественное число",
            "pronoun": "Местоимения",
        }
        errors = c.error_pattern_summary()
        if errors:
            max_err = max(v for _, v in errors) or 1
            elines = ["Частые ошибки"]
            for key, count in errors:
                name = error_names.get(key, key)
                bar = "█" * int((count * 20) / max_err)
                elines.append(f"{name:25s} │{bar} ({count})")
            elines.append("")
            elines.append(f"Всего категорий ошибок: {len(errors)}")
        else:
            elines = ["Частые ошибки", "", "Пока данных недостаточно.", "Практикуйтесь чаще — Ольга соберёт статистику."]
        self.error_canvas.configure(state="normal")
        self.error_canvas.delete("1.0", "end")
        self.error_canvas.insert("1.0", "\n".join(elines))
        self.error_canvas.configure(state="disabled")

        # Sessions
        lines = []
        for item in c.recent_sessions(10):
            voice = "🎤" if item.get("voice") else "✍"
            ptype = PRACTICE_RU.get(item.get("practice_type", ""), item.get("practice_type", ""))
            lines.append(f"{item.get('date')} {voice} {ptype} | {item.get('user_words', 0)}→{item.get('assistant_words', 0)} слов | {item.get('duration_seconds', 0)}с")
        if not lines:
            lines = ["Пока нет завершённых сессий."]
        self.session_list.configure(state="normal")
        self.session_list.delete("1.0", "end")
        self.session_list.insert("1.0", "\n".join(lines))
        self.session_list.configure(state="disabled")

        # Speaking review
        analysis = self.last_voice_analysis or {}
        pron_avg, tempo_avg, conf_avg = c.speaking_average_scores()
        self.speaking_avg_label.configure(
            text=f"Среднее: Pronunciation {pron_avg}% | Tempo {tempo_avg}% | Confidence {conf_avg}%"
        )
        if analysis:
            self.speaking_summary_label.configure(
                text=f"Оценка: {analysis.get('overall_label', 'рабочий')} | Фокус: {analysis.get('focus_hint', 'stability')}"
            )
            self.speaking_metrics_label.configure(
                text=f"Темп: {analysis.get('wpm', 0)} wpm | Распознавание: {analysis.get('recognition_confidence', 0)}% | Длительность: {analysis.get('speech_seconds', 0):.1f}с"
            )
            transcript = analysis.get("transcript", "")
        else:
            self.speaking_summary_label.configure(text="Пока нет голосового ответа для анализа.")
            self.speaking_metrics_label.configure(text="Нажмите «🎤 Говорить 12 сек» во вкладке Практика.")
            transcript = ""
        self.review_transcript.configure(state="normal")
        self.review_transcript.delete("1.0", "end")
        self.review_transcript.insert("1.0", transcript or "Транскрипт появится после записи.")
        self.review_transcript.configure(state="disabled")

        # Speaking history
        hlines = []
        for item in c.recent_speaking_reviews(10):
            hlines.append(f"{item.get('date')} P{item.get('pronunciation_score', 0)} T{item.get('tempo_score', 0)} C{item.get('confidence_score', 0)} {item.get('wpm', 0)}wpm {item.get('overall_label', '')}")
        if not hlines:
            hlines = ["История появится после первых голосовых ответов."]
        self.speaking_history.configure(state="normal")
        self.speaking_history.delete("1.0", "end")
        self.speaking_history.insert("1.0", "\n".join(hlines))
        self.speaking_history.configure(state="disabled")

        # Error patterns
        patterns = c.error_pattern_summary()
        if patterns:
            plines = [f"  {name}: {count} раз" for name, count in patterns]
            self.error_patterns_label.configure(text="\n".join(plines))
        else:
            self.error_patterns_label.configure(text="Пока не выявлено повторяющихся ошибок.")

        # Word Battle scores
        scores = c.game_high_scores()
        if scores:
            score_lines = [f"  {i+1}. {s['score']} очков — {s['date']} (✅{s['correct']} ❌{s['wrong']})" for i, s in enumerate(scores[:5])]
            self.game_scores_label.configure(text="\n".join(score_lines))
        else:
            self.game_scores_label.configure(text="Пока нет игр. Начни Word Battle на вкладке «Учить»!")

        # Survival Game progress
        from survival_game import SCENARIOS
        completed_scenes = c.survival_game_progress()
        survival_lines = [f"Пройдено: {len(completed_scenes)} из {len(SCENARIOS)} сцен\n"]
        for sc in SCENARIOS:
            mark = "✅" if sc["id"] in completed_scenes else "⬜"
            survival_lines.append(f"  {mark} {sc['title']}")
        self.survival_progress_label.configure(text="\n".join(survival_lines))

        # Detective Game progress
        solved_cases = c.detective_game_progress()
        detective_history = c.state.get("detective_history", [])
        det_lines = [f"Раскрыто дел: {len(solved_cases)}"]
        if detective_history:
            det_lines.append("")
            for h in detective_history[-3:]:
                mark = "✅" if h["solved"] else "❌"
                det_lines.append(f"  {mark} {h['case'][:40]} — {h['score']} очков ({h['date']})")
        self.detective_progress_label.configure(text="\n".join(det_lines))

        # Time Loop progress
        from time_loop_game import LOOP_SCENARIOS
        broken_loops = c.time_loop_progress()
        tl_history = c.state.get("time_loop_history", [])
        tl_lines = [f"Петель разорвано: {len(broken_loops)} из {len(LOOP_SCENARIOS)}\n"]
        for sc in LOOP_SCENARIOS:
            mark = "✅" if sc["id"] in broken_loops else "⬜"
            tl_lines.append(f"  {mark} {sc['title']}")
        if tl_history:
            tl_lines.append("")
            for h in tl_history[-2:]:
                mark = "✅" if h["broken"] else "❌"
                tl_lines.append(f"  {mark} {h['scenario'][:30]} — {h['score']} очков ({h['date']})")
        self.timeloop_progress_label.configure(text="\n".join(tl_lines))

        # Badges
        all_badges = c.all_badges()
        earned_count = sum(1 for _, _, _, earned in all_badges if earned)
        badge_lines = [f"Получено: {earned_count} из {len(all_badges)}\n"]
        for bid, bname, bdesc, earned in all_badges:
            mark = "✅" if earned else "⬜"
            badge_lines.append(f"  {mark} {bname} — {bdesc}")
        self.badges_label.configure(text="\n".join(badge_lines))

        # Error journal
        journal = c.error_journal_summary()
        if journal["total"] > 0:
            jlines = [f"Всего записей: {journal['total']}"]
            for cat, count in sorted(journal["by_category"].items(), key=lambda x: x[1], reverse=True):
                jlines.append(f"  {cat}: {count}")
            if journal["recent_trend"]:
                jlines.append("\nПоследние:")
                for jdate, jcount, jcats in journal["recent_trend"][-5:]:
                    jlines.append(f"  {jdate} | {jcount} ошибок | {', '.join(jcats) if jcats else '—'}")
            self.error_journal_label.configure(text="\n".join(jlines))
        else:
            self.error_journal_label.configure(text="Журнал ошибок пуст. Ошибки будут записываться автоматически.")

    # ─── Actions ───

    def _apply_level(self) -> None:
        new_level = self.level_var.get()
        self.course.set_level(new_level)
        self._refresh_all()
        self._append_chat("system", f"Уровень изменён на {new_level}. Ольга адаптирует программу.\n\n")

    def _set_goal(self, days: int) -> None:
        self.course.set_goal(days)
        self._refresh_all()

    def _show_weekly_summary(self) -> None:
        summary = self.course.weekly_summary()
        self._switch_to_tab(2)
        self._append_chat("system", summary + "\n\n")

    def _start_daily_challenge(self) -> None:
        """Start today's daily challenge — switch to Practice with the challenge text."""
        ch_type, ch_text, ch_cat = self.course.daily_challenge()
        self._switch_to_tab(2)
        mode_map = {
            "writing": "Письмо",
            "speaking": "Собеседник",
            "grammar": "Упражнение",
            "vocab": "Упражнение",
            "reading": "Диалог",
        }
        self.mode_var.set(mode_map.get(ch_type, "Диалог"))
        self.current_practice_type = ch_type
        self._fill_prompt(ch_text)

    def _toggle_advanced_actions(self) -> None:
        """Show or hide advanced practice buttons."""
        if self._advanced_visible:
            self.advanced_actions_frame.pack_forget()
            self.advanced_toggle_btn.configure(text="Ещё →")
            self._advanced_visible = False
        else:
            # Pack advanced frame before the toggle button
            self.advanced_toggle_btn.pack_forget()
            self.advanced_actions_frame.pack(fill="x", pady=(0, 4))
            self.advanced_toggle_btn.configure(text="← Скрыть")
            self.advanced_toggle_btn.pack(anchor="w", pady=(4, 0))
            self._advanced_visible = True

    def _complete_daily_challenge(self) -> None:
        """Mark today's challenge as completed."""
        if self.course.daily_challenge_completed():
            messagebox.showinfo("Задание дня", "Сегодня задание уже выполнено! 🎉")
            return
        self.course.complete_daily_challenge()
        self._refresh_dashboard()
        self._show_toast("🎯 Задание дня", "Выполнено! +1 к прогрессу.")
        self._send_macos_notification("🎯 Задание дня выполнено", "Отличная работа!")

    def _show_placement_test(self) -> None:
        """Show CEFR placement test modal dialog."""
        questions = self.course.placement_questions()
        answers: list[int] = [0] * len(questions)

        win = tk.Toplevel(self.root)
        win.title("Тест на определение уровня")
        win.geometry("600x520")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        header = tk.Frame(win, bg=BG, padx=16, pady=12)
        header.pack(fill="x")
        tk.Label(header, text="🎯 Определение уровня English", bg=BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        tk.Label(header, text="Ответьте на 10 вопросов — Ольга подберёт оптимальный уровень.", bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack(anchor="w", pady=(4, 0))

        scroll = ctk.CTkScrollableFrame(win, fg_color=BG)
        scroll.pack(fill="both", expand=True, padx=12, pady=4)

        radios: list[tk.IntVar] = []
        for i, (question, options, choices) in enumerate(questions):
            card = tk.Frame(scroll, bg=CARD_BG, padx=12, pady=10)
            card.pack(fill="x", pady=(0, 8))
            tk.Label(card, text=f"{i+1}. {question}", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_BODY, wraplength=540, justify="left").pack(anchor="w")
            var = tk.IntVar(value=0)
            radios.append(var)
            for j, choice in enumerate(choices):
                tk.Radiobutton(card, text=f"{choice}) {options.split('  ')[j] if '  ' in options else choice}",
                               variable=var, value=j, bg=CARD_BG, fg=TEXT_SECONDARY,
                               selectcolor=CARD_BG, activebackground=CARD_BG,
                               activeforeground=TEXT_PRIMARY, font=FONT_SMALL,
                               highlightthickness=0, bd=0).pack(anchor="w", padx=(12, 0))

        def _submit():
            for i, var in enumerate(radios):
                answers[i] = var.get()
            level = self.course.submit_placement_test(answers)
            win.destroy()
            self._refresh_all()
            messagebox.showinfo("Уровень определён", f"Ваш уровень: {level}\nОльга адаптирует программу под вас!")
            self.root.after(500, self._start_onboarding_tour)

        btn_frame = tk.Frame(win, bg=BG, padx=16, pady=12)
        btn_frame.pack(fill="x")
        make_button(btn_frame, "Готово", _submit, accent=True).pack(side="right")

    def _start_onboarding_tour(self) -> None:
        """Show a 4-step onboarding tour for first-time users."""
        steps = [
            ("👋 Добро пожаловать!",
             f"Это ваш персональный AI-репетитор английского.\n\n"
             "Ольга живёт на этом Mac — ничего не уходит в облако.\n"
             "Давайте посмотрим, что здесь есть."),
            ("🎯 Задание дня",
             "Каждый день — новое задание: письмо, говорение,\n"
             "грамматика или чтение. Нажмите «Начать», чтобы\n"
             "перейти к практике.\n\n"
             "Выполните задание и отметьте «✅ Выполнено»."),
            ("⚡ Быстрые действия",
             "6 главных кнопок для старта: Диалог, Письмо,\n"
             "Ролевая игра, Чтение, Аудирование, Дебат.\n\n"
             "Нажмите «Ещё →» чтобы открыть продвинутые режимы\n"
             "(Shadowing, Minimal Pairs, Dictogloss и др.)."),
            ("💬 Практика — это чат",
             "Перейдите на вкладку «Практика» (Cmd+3) и просто\n"
             "напишите Ольге на английском. Она исправит ошибки\n"
             "и объяснит правила.\n\n"
             "Можно говорить голосом — нажмите «🎤 Говорить»."),
        ]
        step_idx = [0]

        def _show_step():
            if step_idx[0] >= len(steps):
                self.course.state["onboarding_done"] = True
                self.course._save_state()
                return
            title, body = steps[step_idx[0]]
            total = len(steps)
            current = step_idx[0] + 1

            tour_win = tk.Toplevel(self.root)
            tour_win.title(f"Тур {current}/{total}")
            tour_win.geometry("440x360")
            tour_win.resizable(True, True)
            tour_win.minsize(400, 300)
            tour_win.transient(self.root)
            tour_win.grab_set()

            # Pack button frame FIRST with side=bottom so it's always visible
            btn_frame = tk.Frame(tour_win, bg=BG, padx=20, pady=16)
            btn_frame.pack(side="bottom", fill="x")
            if step_idx[0] < total - 1:
                make_button(btn_frame, "Пропустить", lambda: (tour_win.destroy(), step_idx.__setitem__(0, total), _show_step())).pack(side="left")
                make_button(btn_frame, "Далее →", lambda: (tour_win.destroy(), step_idx.__setitem__(0, step_idx[0] + 1), _show_step()), accent=True).pack(side="right")
            else:
                make_button(btn_frame, "Поехали! 🚀", lambda: (tour_win.destroy(), step_idx.__setitem__(0, total), _show_step()), accent=True).pack(side="right")

            header = tk.Frame(tour_win, bg=BG, padx=20, pady=16)
            header.pack(side="top", fill="x")
            tk.Label(header, text=title, bg=BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
            # Progress dots
            dots_frame = tk.Frame(header, bg=BG)
            dots_frame.pack(anchor="w", pady=(8, 0))
            for i in range(total):
                color = ACCENT if i <= step_idx[0] else BORDER
                tk.Label(dots_frame, text="●", bg=BG, fg=color, font=FONT_SMALL).pack(side="left", padx=2)

            body_frame = tk.Frame(tour_win, bg=BG, padx=20, pady=8)
            body_frame.pack(fill="both", expand=True)
            tk.Label(body_frame, text=body, bg=BG, fg=TEXT_SECONDARY, font=FONT_BODY, justify="left", wraplength=400).pack(anchor="w")

        _show_step()

    def _show_streak_milestone_popup(self, days: int, bonus_xp: int) -> None:
        """Show a celebration popup for streak milestones."""
        emoji = "🎉" if days >= 100 else ("🏆" if days >= 30 else "🔥")
        popup = tk.Toplevel(self.root)
        popup.title(f"{emoji} Streak {days} дней!")
        popup.geometry("380x240")
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.grab_set()

        # Center on parent
        popup.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 380) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 240) // 2
        popup.geometry(f"380x240+{x}+{y}")

        frame = tk.Frame(popup, bg=BG, padx=24, pady=24)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text=f"{emoji}", bg=BG, fg=ACCENT, font=("SF Pro Display", 48)).pack(pady=(0, 8))
        tk.Label(frame, text=f"{days} дней подряд!", bg=BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack()
        tk.Label(frame, text=f"Бонус: +{bonus_xp} XP", bg=BG, fg=ACCENT, font=("SF Pro Display", 16, "bold")).pack(pady=(8, 0))
        tk.Label(frame, text="Так держать! Ольга гордится тобой.", bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack(pady=(4, 0))
        make_button(frame, "Спасибо!", popup.destroy, accent=True).pack(pady=(12, 0))

    def _start_recommended_lesson(self) -> None:
        practice_type = getattr(self, "_recommended_practice_type", "dialogue")
        rec_text = getattr(self, "_recommended_practice_text", "")
        self._switch_to_tab(2)
        self._fill_prompt(rec_text)
        mode_map = {
            "speaking_drill": "Собеседник",
            "grammar_exercise": "Упражнение",
            "writing_task": "Письмо",
            "vocab_review": "Упражнение",
            "listening_task": "Диалог",
            "reading_task": "Чтение",
            "dialogue_listening": "Диалог-аудирование",
            "dictation": "Диктант",
            "shadowing": "Shadowing",
            "minimal_pairs": "Minimal Pairs",
            "collocation_drill": "Collocation Drill",
            "error_correction": "Error Correction",
            "sentence_transformation": "Sentence Transformation",
            "phrasal_verbs": "Phrasal Verbs",
            "dictogloss": "Dictogloss",
            "input_flood": "Input Flood",
            "pushed_output": "Pushed Output",
            "lexical_chunks": "Lexical Chunks",
            "task_repetition": "Task Repetition",
        }
        self.mode_var.set(mode_map.get(practice_type, "Диалог"))
        self.current_practice_type = practice_type

    def _start_interleaved_session(self) -> None:
        session_parts = self.course.recommended_interleaved_session(self.topic_var.get())
        self._switch_to_tab(2)
        mode_map = {
            "speaking_drill": "Собеседник", "grammar_exercise": "Упражнение",
            "writing_task": "Письмо", "vocab_review": "Упражнение",
            "listening_task": "Диалог", "reading_task": "Чтение",
            "dialogue_listening": "Диалог-аудирование", "dictation": "Диктант",
            "shadowing": "Shadowing", "minimal_pairs": "Minimal Pairs",
            "collocation_drill": "Collocation Drill", "error_correction": "Error Correction",
            "sentence_transformation": "Sentence Transformation", "phrasal_verbs": "Phrasal Verbs",
            "dictogloss": "Dictogloss", "input_flood": "Input Flood",
            "pushed_output": "Pushed Output", "lexical_chunks": "Lexical Chunks",
            "task_repetition": "Task Repetition", "dialogue": "Диалог",
            "roleplay": "Ролевая игра",
        }
        pt1, txt1 = session_parts[0]
        pt2, txt2 = session_parts[1]
        combined = f"🔀 Смешанная сессия (interleaving):\n\nЧасть 1 — {PRACTICE_RU.get(pt1, pt1)}:\n{txt1}\n\nЧасть 2 — {PRACTICE_RU.get(pt2, pt2)}:\n{txt2}\n\nНачни с Части 1. Когда пользователь закончит, переходи к Части 2."
        self.mode_var.set(mode_map.get(pt1, "Диалог"))
        self.current_practice_type = pt1
        self._fill_prompt(combined)

    def _quick_start_chat(self) -> None:
        """Quick-start button: switch to Practice tab and pre-fill the start command."""
        self._switch_to_tab(2)
        self.mode_var.set("Диалог")
        self.current_practice_type = "dialogue"
        self._fill_prompt(START_COMMAND)
        self.input.focus_set()

    def _quick_practice(self, mode: str, practice_type: str) -> None:
        self._switch_to_tab(2)
        self.mode_var.set(mode)
        self.current_practice_type = practice_type
        prompts = {
            "dialogue": "Давай начнём разговорную практику.",
            "writing_task": "Дай мне writing task для практики.",
            "roleplay": "Давай проведём ролевую игру на английском.",
            "speaking_drill": "Давай проведём speaking drill. Задавай по одному вопросу.",
            "grammar_exercise": "Дай мне упражнение по грамматике.",
            "listening_task": self.coach.build_listening_prompt(self.course.level, self.topic_var.get(), self.concise_var.get()),
            "reading_task": "Дай мне короткий текст для чтения на английском с вопросами и разбором.",
            "dialogue_listening": "Дай короткий диалог на английском между двумя людьми для практики аудирования. 6-8 реплик из реальной жизни. Формат: каждая реплика с меткой спикера 'A: ' или 'B: ' в начале строки. После диалога задай 3 вопроса по содержанию.",
            "dictation": "Проведи диктант: 5 коротких предложений с пропусками только предлогов и артиклей.",
            "shadowing": "Дай 3 короткие английские фразы для shadowing-практики. Я повторю их вслух.",
            "minimal_pairs": "Дай 5 пар минимальных слов (minimal pairs) для тренировки произношения. Покажи IPA и примеры.",
            "collocation_drill": "Дай 5 словосочетаний (collocations) с пропусками. Я дополню короткими словами.",
            "error_correction": "Дай 5 предложений с одной ошибкой в каждом. Я найду и исправлю ошибку.",
            "sentence_transformation": "Дай 5 заданий на преобразование предложений (sentence transformation). Покажи исходное предложение и начало второго.",
            "phrasal_verbs": "Дай 5 фразовых глаголов с контекстом и пропусками. Я дополню правильным фразовым глаголом.",
            "dictogloss": "Дай короткий текст для dictogloss — реконструкции по памяти.",
            "input_flood": "Дай текст с насыщенным повторением одной грамматической структуры для input flood.",
            "pushed_output": "Дай pushed output task — задачу с грамматическими ограничениями.",
            "lexical_chunks": "Дай тренировку лексических чанков и устойчивых выражений.",
            "task_repetition": "Дай task repetition — коммуникативную задачу для повторения в новом контексте.",
            "debate": "Давай проведём дебаты на английском. Предложи тему и свою позицию.",
        }
        self._fill_prompt(prompts.get(practice_type, "Давай практиковать английский."))

    def _start_debate(self) -> None:
        """Start an AI debate — Olga takes a position and argues."""
        model = self.model_var.get().strip()
        if not model:
            messagebox.showwarning("Дебат", "Нет локальной модели.")
            return
        level = self.course.level
        topic = self.topic_var.get().strip()
        self._switch_to_tab(2)
        self.mode_var.set("Диалог")
        self.current_practice_type = "debate"
        self.status_var.set("Готовлю дебат...")
        self._append_chat("system", "🎭 Ольга готовит тему для дебатов...\n\n")
        def _worker():
            try:
                from coach import build_debate_prompt
                prompt = build_debate_prompt(level, topic)
                response = self.client.generate(model, prompt, use_cache=False)
                self.response_queue.put(("assistant_done", response))
                if self.voice_output_var.get():
                    text = extract_speakable_text(response, max_lines=4)
                    if text:
                        voice_name = self.tts_voice_var.get()
                        threading.Thread(target=self.voice.speak, args=(text, "en-US", 0, voice_name), daemon=True).start()
            except Exception as exc:
                self.response_queue.put(("error", f"Дебат не удалось начать: {exc}"))
        threading.Thread(target=_worker, daemon=True).start()

    def _learn_grammar(self, grammar_id: str) -> None:
        gp = grammar_point_by_id(grammar_id)
        if not gp:
            return
        self.current_grammar_point_id = grammar_id
        self.current_practice_type = "grammar_exercise"
        self._switch_to_tab(2)
        self.mode_var.set("Упражнение")
        prompt = self.coach.build_grammar_lesson_prompt(self.course.level, gp, self.concise_var.get())
        self._fill_prompt(prompt)

    def _learn_vocab(self, theme: str) -> None:
        self.current_vocab_theme = theme
        self.current_practice_type = "vocab_review"
        self._switch_to_tab(2)
        self.mode_var.set("Упражнение")
        level = self.course.level
        cards = []
        for vset in vocabulary_for_level(level):
            if vset.theme == theme:
                for card in vset.cards:
                    cards.append((card.word, card.translation, card.example))
        prompt = self.coach.build_vocab_review_prompt(level, cards, self.concise_var.get())
        self._fill_prompt(prompt)

    def _practice_function(self, function_name: str, scenario: str) -> None:
        self.current_practice_type = "roleplay"
        self._switch_to_tab(2)
        self.mode_var.set("Ролевая игра")
        prompt = self.coach.build_roleplay_prompt(self.course.level, scenario, self.concise_var.get())
        self._fill_prompt(prompt)

    def _start_word_battle(self) -> None:
        from word_game import WordBattleGame
        level = self.course.level

        # Collect due SRS cards as dicts for the game
        try:
            due_cards = self.course.srs.due_cards()[:20]
            srs_words = [{"front": c.front, "back": c.back} for c in due_cards if c.front and c.back]
        except Exception:
            srs_words = []

        def on_finish(score: int, wrong_words: list[str]) -> None:
            correct_count = len(wrong_words) == 0 and 10 or (10 - len(wrong_words))
            self.course.record_game_score(score, correct_count, len(wrong_words))
            for word in wrong_words:
                card_id = f"vocab:{level}:{word}"
                if card_id not in self.course.srs.cards:
                    try:
                        from worddb import get_db
                        rows = get_db().search(word, limit=1)
                        if rows:
                            r = rows[0]
                            from srs import SRSCard
                            self.course.srs.add_card(SRSCard(
                                card_id=card_id, front=r["word"], back=r["translation"],
                                example=r.get("example", ""), ipa=r.get("ipa", ""),
                            ))
                    except Exception:
                        pass
            if wrong_words:
                self.course._save_srs()
                self._refresh_learn()

        WordBattleGame(self.root, level=level, on_finish=on_finish, srs_words=srs_words)

    def _speak_wotd(self) -> None:
        word = getattr(self, "_wotd_word", "")
        if word and self.voice:
            self.voice.speak(word, "en")

    def _speak_srs_word(self) -> None:
        """Speak the current SRS card's front (English word)."""
        try:
            if self.srs_review_index <= len(self.srs_review_session):
                idx = max(0, self.srs_review_index - 1) if self.srs_review_index > 0 else 0
                card = self.srs_review_session[idx] if self.srs_review_session else None
                if card and card.front:
                    threading.Thread(target=self.voice.speak, args=(card.front, "en-US"), daemon=True).start()
        except Exception:
            pass

    def _generate_mnemonic(self) -> None:
        """Generate a mnemonic association for the current SRS card word."""
        try:
            idx = max(0, self.srs_review_index - 1) if self.srs_review_index > 0 else 0
            card = self.srs_review_session[idx] if self.srs_review_session else None
            if not card or not card.front:
                return
            model = self.model_var.get().strip()
            if not model:
                messagebox.showwarning("Мнемоника", "Нет локальной модели.")
                return
            word = card.front
            translation = card.back or ""
            level = self.course.level
            self.srs_mnemonic_label.configure(text="Готовлю мнемонику...")
            def _worker():
                try:
                    from coach import build_mnemonic_prompt
                    prompt = build_mnemonic_prompt(word, translation, level)
                    result = self.client.generate(model, prompt, use_cache=True)
                    self.srs_mnemonic_label.configure(text=result)
                except Exception as exc:
                    self.srs_mnemonic_label.configure(text=f"Ошибка: {exc}")
            threading.Thread(target=_worker, daemon=True).start()
        except Exception:
            pass

    def _start_survival_game(self) -> None:
        from survival_game import SurvivalGame
        level = self.course.level
        error_patterns = self.course.state.get("error_patterns", {})
        completed = self.course.survival_game_progress()

        def on_finish(scene_id: str, passed: bool, rating: float, words: list[str]) -> None:
            self.course.record_survival_scene(scene_id, passed, rating, words)

        SurvivalGame(
            self.root,
            ollama_client=self.ollama,
            level=level,
            error_patterns=error_patterns,
            completed_scenes=completed,
            on_finish=on_finish,
            voice_toolkit=self.voice,
        )

    def _start_detective_game(self) -> None:
        from detective_game import DetectiveGame
        level = self.course.level
        error_patterns = self.course.state.get("error_patterns", {})
        solved = self.course.detective_game_progress()

        def on_finish(case_title: str, solved: bool, score: int, words: list[str]) -> None:
            self.course.record_detective_case(case_title, solved, score, words)

        DetectiveGame(
            self.root,
            ollama_client=self.ollama,
            level=level,
            error_patterns=error_patterns,
            completed_cases=solved,
            on_finish=on_finish,
            voice_toolkit=self.voice,
        )

    def _start_time_loop_game(self) -> None:
        from time_loop_game import TimeLoopGame
        level = self.course.level
        error_patterns = self.course.state.get("error_patterns", {})
        broken = self.course.time_loop_progress()

        def on_finish(scenario_id: str, broken: bool, score: int, words: list[str]) -> None:
            self.course.record_time_loop(scenario_id, broken, score, words)

        TimeLoopGame(
            self.root,
            ollama_client=self.ollama,
            level=level,
            error_patterns=error_patterns,
            completed_loops=broken,
            on_finish=on_finish,
            voice_toolkit=self.voice,
        )

    def _start_contexto_game(self) -> None:
        from contexto_game import ContextoGame
        level = self.course.level

        def on_finish(word: str, guesses: int, elapsed: int) -> None:
            # Award XP for winning
            if guesses <= 5:
                xp = 30
            elif guesses <= 10:
                xp = 20
            else:
                xp = 10
            self._show_toast("🔍 Contexto", f"Слово: {word} | +{xp} XP")
            self.course.award_xp("game_bonus", base_xp=xp)
            self._refresh_dashboard()

        ContextoGame(
            self.root,
            ollama_client=self.ollama,
            level=level,
            on_finish=on_finish,
        )

    def _start_taboo_game(self) -> None:
        from taboo_game import TabooGame
        level = self.course.level

        def on_finish(score: int, words_guessed: int) -> None:
            xp = words_guessed * 10
            self._show_toast("🤐 Taboo Talks", f"Угадано: {words_guessed} | +{xp} XP")
            self.course.award_xp("game_bonus", base_xp=xp)
            self._refresh_dashboard()

        TabooGame(
            self.root,
            ollama_client=self.ollama,
            level=level,
            on_finish=on_finish,
        )

    def _start_vocab_graph(self) -> None:
        from vocab_graph import VocabGraphGame
        level = self.course.level

        def on_finish(score: int, total: int) -> None:
            xp = score * 5
            self._show_toast("🕸 Knowledge Graph", f"Квиз: {score}/{total} | +{xp} XP")
            self.course.award_xp("game_bonus", base_xp=xp)
            self._refresh_dashboard()

        VocabGraphGame(
            self.root,
            ollama_client=self.ollama,
            level=level,
            on_finish=on_finish,
        )

    def _add_wotd_to_srs(self) -> None:
        word = getattr(self, "_wotd_word", "")
        if not word:
            return
        level = self.course.level
        card_id = f"vocab:{level}:{word}"
        if card_id in self.course.srs.cards:
            messagebox.showinfo("Слово дня", "Это слово уже в повторении.")
            return
        try:
            from worddb import get_db
            rows = get_db().search(word, limit=1)
            if rows:
                r = rows[0]
                from srs import SRSCard
                self.course.srs.add_card(SRSCard(
                    card_id=card_id, front=r["word"], back=r["translation"],
                    example=r.get("example", ""), ipa=r.get("ipa", ""),
                ))
                self.course._save_srs()
                self._refresh_learn()
                messagebox.showinfo("Слово дня", f"«{word}» добавлено в повторение.")
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось добавить: {exc}")

    def _speak_idiom(self) -> None:
        idiom = getattr(self, "_current_idiom", "")
        if idiom and self.voice:
            self.voice.speak(idiom, "en")

    def _add_idiom_to_srs(self) -> None:
        idiom = getattr(self, "_current_idiom", "")
        if not idiom:
            return
        card_id = f"idiom:{idiom}"
        if card_id in self.course.srs.cards:
            messagebox.showinfo("Идиома", "Эта идиома уже в повторении.")
            return
        try:
            from srs import SRSCard
            self.course.srs.add_card(SRSCard(
                card_id=card_id, front=idiom, back="",
                example="", ipa="",
            ))
            self.course._save_srs()
            self._refresh_learn()
            messagebox.showinfo("Идиома", f"«{idiom}» добавлено в повторение.")
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось добавить: {exc}")

    def _on_word_search(self, event=None) -> None:
        query = self.search_var.get().strip()
        if not query:
            self.search_result_label.configure(text="Введите слово для поиска.")
            return
        try:
            from worddb import get_db
            results = get_db().search(query, limit=10)
            if not results:
                self.search_result_label.configure(text=f"Ничего не найдено по запросу «{query}».")
                return
            lines = []
            for r in results:
                parts = [r["word"]]
                if r["translation"]:
                    parts.append(f"→ {r['translation']}")
                if r["cefr"]:
                    parts.append(f"[{r['cefr']}]")
                if r["example"]:
                    parts.append(f"Ex: {r['example'][:60]}")
                lines.append("  ".join(parts))
            self.search_result_label.configure(text="\n".join(lines))
        except Exception as exc:
            self.search_result_label.configure(text=f"Ошибка поиска: {exc}")

    def _start_vocab_review(self) -> None:
        session = self.course.srs_review_session(limit=20)
        if not session:
            messagebox.showinfo("SRS", "Нет карточек для повторения. Изучите новые слова во вкладке «Учить».")
            return
        self.srs_review_session = session
        self.srs_review_index = 0
        self.srs_review_card.pack(fill="x", pady=(0, 8))
        self._show_srs_card()
        self._switch_to_tab(1)

    def _show_srs_card(self) -> None:
        if self.srs_review_index >= len(self.srs_review_session):
            self.srs_review_card.pack_forget()
            self._refresh_learn()
            messagebox.showinfo("SRS", "Повторение завершено! Молодец!")
            return
        card = self.srs_review_session[self.srs_review_index]
        # Interleaved SRS: alternate between Meaning, Form, Use
        mode = self.srs_review_index % 3  # 0=Meaning, 1=Form, 2=Use
        mode_names = ["📖 Meaning", "✏️ Form", "💬 Use"]
        mode_labels = ["Перевод", "Написание", "В предложении"]

        if mode == 0:
            # Meaning: show English word, ask for translation
            self.srs_word_label.configure(text=card.front)
            ipa_text = f"IPA: {card.ipa}" if card.ipa else ""
            trans_text = f"[{mode_names[mode]}] Перевод: {card.back}"
            if ipa_text:
                trans_text = f"{ipa_text}  |  {trans_text}"
            self.srs_translation_label.configure(text=trans_text)
            parts = []
            if card.example:
                parts.append(f"Пример: {card.example}")
            if card.collocations:
                parts.append(f"Словосочетания: {card.collocations}")
            self.srs_example_label.configure(text="\n".join(parts) if parts else "")
        elif mode == 1:
            # Form: show translation, ask to spell the word
            self.srs_word_label.configure(text=f"[{mode_names[mode]}] Как пишется?")
            self.srs_translation_label.configure(text=f"Перевод: {card.back}  |  IPA: {card.ipa or '?'}")
            parts = [f"Написание: {'_ ' * len(card.front)}"]
            if card.example:
                # Show example with the word blanked out
                blanked = card.example.replace(card.front, "_" * len(card.front))
                parts.append(f"Пример: {blanked}")
            self.srs_example_label.configure(text="\n".join(parts))
        else:
            # Use: show word, ask to make a sentence
            self.srs_word_label.configure(text=f"[{mode_names[mode]}] {card.front}")
            self.srs_translation_label.configure(text=f"Перевод: {card.back}  |  Составь предложение с этим словом")
            parts = []
            if card.example:
                parts.append(f"Пример: {card.example}")
            if card.collocations:
                parts.append(f"Словосочетания: {card.collocations}")
            self.srs_example_label.configure(text="\n".join(parts) if parts else "")
        self.srs_mnemonic_label.configure(text=f"Режим: {mode_labels[mode]}")
        self.srs_review_card.update_idletasks()

    def _rate_card(self, rating: str) -> None:
        if self.srs_review_index >= len(self.srs_review_session):
            return
        card = self.srs_review_session[self.srs_review_index]
        self.course.review_vocab_card(card.card_id, rating)
        self.srs_review_index += 1
        self._show_srs_card()

    def send_message(self) -> None:
        if self.is_generating:
            return
        user_text = self.input.get("1.0", "end").strip()
        if not user_text:
            messagebox.showinfo("English Coach", "Введите текст или задание.")
            return
        self.voice.stop_speaking()
        settings = self._current_settings()
        if not settings.model:
            messagebox.showwarning("English Coach", "Нет локальной модели. Загрузите через `ollama pull`.")
            return

        # Intercept "Дальше?" — generate personalised recommendations
        if user_text.strip().lower().rstrip("??!.") in ("дальше", "далее", "что дальше", "next", "что дальше?"):
            self._append_chat("user", f"Вы:\n{user_text}\n\n")
            self.input.delete("1.0", "end")
            self.is_generating = True
            self.client._cancel_event.clear()
            self.send_btn.configure(state="disabled")
            self.status_var.set("Ольга думает над рекомендациями...")
            self._show_typing()
            threading.Thread(target=self._generate_recommendation, args=(settings,), daemon=True).start()
            return

        used_voice = self.pending_voice_input
        speaking_review = self.last_voice_analysis if used_voice else None

        self._append_chat("user", f"Вы:\n{user_text}\n\n")
        self.input.delete("1.0", "end")
        self.pending_voice_input = False
        self.is_generating = True
        self.client._cancel_event.clear()
        self.send_btn.configure(state="disabled")
        self.status_var.set("Ольга думает локально...")
        self._show_typing()
        self.session_start_time = time.time()

        threading.Thread(
            target=self._generate_response,
            args=(settings, user_text, used_voice, speaking_review),
            daemon=True,
        ).start()

    def _generate_recommendation(self, settings):
        """Generate personalised learning recommendations when user asks 'Дальше?'."""
        try:
            from coach import build_recommendation_prompt
            learning_context = self.course.learning_context()
            error_patterns = self.course.error_pattern_summary()
            profile_ctx = self.course.profile_context()
            srs_due = self.course.srs_due_count()
            weekly_xp = self.course.weekly_xp_total()
            weekly_goal = self.course.weekly_xp_goal()
            streak = self.course.streak_days()

            prompt = build_recommendation_prompt(
                level=self.course.level,
                learning_context=learning_context,
                error_patterns=error_patterns,
                profile_ctx=profile_ctx,
                srs_due=srs_due,
                weekly_xp=weekly_xp,
                weekly_xp_goal=weekly_goal,
                streak=streak,
            )

            chunks = []
            def on_chunk(chunk):
                chunks.append(chunk)
                self.response_queue.put(("stream_chunk", chunk))

            response = ""
            try:
                for chunk in self.client.generate_stream(settings.model, prompt):
                    response += chunk
                    on_chunk(chunk)
            except Exception:
                pass
            response = response.strip()
            if not response:
                response = "Не удалось сгенерировать рекомендации. Попробуйте ещё раз."

            self.response_queue.put(("assistant_done", response))
            self.response_queue.put(("status", f"{COACH_NAME} готова к практике"))
        except Exception as exc:
            self.response_queue.put(("error", f"Рекомендации не удалось создать: {exc}"))
        finally:
            self.is_generating = False
            self.send_btn.configure(state="normal")

    def _generate_response(self, settings, user_text, used_voice, speaking_review):
        try:
            learning_context = self.course.learning_context()
            error_patterns = self.course.error_pattern_summary()
            self.course.extract_profile_from_text(user_text)
            profile_ctx = self.course.profile_context()
            srs_recall = [c.front for c in self.course.srs.due_cards()[:5]] if hasattr(self.course.srs, 'due_cards') else []

            def on_chunk(chunk):
                self.response_queue.put(("stream_chunk", chunk))

            response = self.coach.generate_stream(settings, user_text, learning_context, error_patterns, on_chunk, profile_ctx, srs_recall)
            if not response:
                response = "Модель не вернула текст. Попробуйте переформулировать запрос."
            duration = int(time.time() - self.session_start_time)
            error_count = count_errors(response)
            self.course.record_session(
                practice_type=settings.practice_type,
                mode=settings.mode,
                user_text=user_text,
                assistant_text=response,
                used_voice=used_voice,
                duration_seconds=duration,
                speaking_review=speaking_review,
                error_count=error_count,
                grammar_point_id=self.current_grammar_point_id,
                vocab_theme=self.current_vocab_theme,
            )
            self.current_grammar_point_id = ""
            self.current_vocab_theme = ""
            self._last_user_text = user_text
            self._last_assistant_text = response
            self.response_queue.put(("assistant_done", response))
            self.response_queue.put(("course", "refresh"))
            self.coach.save_history(self.chat_history_path)
            new_badges = self.course.check_badges()
            for badge_id, badge_name in new_badges:
                self.response_queue.put(("system", f"🎉 Новое достижение: {badge_name}!\n\n"))
                self.response_queue.put(("badge", badge_name))
        except Exception as exc:
            self.response_queue.put(("error", str(exc)))

    def clear_chat(self) -> None:
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")
        self.coach.clear_history()
        self.coach.save_history(self.chat_history_path)
        self._append_chat("system", "Диалог очищен. Ольга готова к новой практике.\n\n")
        # Show hint chips again
        if hasattr(self, "hint_chips_frame"):
            self.hint_chips_frame.pack(fill="x", padx=12, pady=(8, 4))

    def _generate_feedback_report(self) -> None:
        """Generate a post-chat feedback report using Ollama."""
        user_text = getattr(self, "_last_user_text", "")
        assistant_text = getattr(self, "_last_assistant_text", "")
        if not user_text or not assistant_text:
            messagebox.showinfo("Отчёт", "Сначала проведите диалог с Ольгой.")
            return
        model = self.model_var.get().strip()
        if not model:
            messagebox.showwarning("Отчёт", "Нет локальной модели.")
            return
        self.status_var.set("Готовлю отчёт...")
        level = self.course.level
        def _worker():
            try:
                from coach import build_feedback_report
                prompt = build_feedback_report(user_text, assistant_text, level)
                report = self.client.generate(model, prompt, use_cache=False)
                self.response_queue.put(("system", report + "\n\n"))
                self.response_queue.put(("status", f"{COACH_NAME} готова к практике"))
            except Exception as exc:
                self.response_queue.put(("error", f"Отчёт не удалось создать: {exc}"))
        threading.Thread(target=_worker, daemon=True).start()

    def _export_chat(self) -> None:
        """Export current chat to a .txt file on Desktop."""
        try:
            chat_content = self.chat.get("1.0", "end").strip()
            if not chat_content:
                messagebox.showinfo("Экспорт", "Чат пуст — нечего сохранять.")
                return
            desktop = Path.home() / "Desktop"
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"olga_chat_{timestamp}.txt"
            filepath = desktop / filename
            filepath.write_text(chat_content, encoding="utf-8")
            self._show_toast("💾 Сохранено", f"Файл: {filename}")
        except Exception as exc:
            messagebox.showerror("Экспорт", f"Ошибка: {exc}")

    def _generate_quiz(self) -> None:
        """Generate a quiz from the current chat content."""
        chat_text = self.chat.get("1.0", "end").strip()
        if len(chat_text) < 50:
            messagebox.showinfo("Викторина", "Сначала проведите диалог с Ольгой.")
            return
        model = self.model_var.get().strip()
        if not model:
            messagebox.showwarning("Викторина", "Нет локальной модели.")
            return
        level = self.course.level
        self.status_var.set("Готовлю викторину...")
        def _worker():
            try:
                from coach import build_quiz_prompt
                prompt = build_quiz_prompt(level, chat_text)
                quiz = self.client.generate(model, prompt, use_cache=False)
                self.response_queue.put(("system", quiz + "\n\n"))
                self.response_queue.put(("status", f"{COACH_NAME} готова к практике"))
            except Exception as exc:
                self.response_queue.put(("error", f"Викторину не удалось создать: {exc}"))
        threading.Thread(target=_worker, daemon=True).start()

    def _generate_story(self) -> None:
        """Generate an AI story using the learner's SRS due words."""
        model = self.model_var.get().strip()
        if not model:
            messagebox.showwarning("AI-рассказ", "Нет локальной модели.")
            return
        # Collect SRS words (due first, then any) — randomized to vary topics
        try:
            due = self.course.srs.due_cards()
            random.shuffle(due)
            srs_words = [c.front for c in due[:10] if c.front]
            if len(srs_words) < 3:
                all_cards = list(self.course.srs.cards.values())
                random.shuffle(all_cards)
                srs_words = [c.front for c in all_cards[:10] if c.front]
        except Exception:
            srs_words = []

        if not srs_words:
            messagebox.showinfo("AI-рассказ", "Добавьте слова в SRS для генерации рассказа.")
            return

        level = self.course.level
        topic = self.story_topic_var.get().strip() if hasattr(self, "story_topic_var") else ""
        self.status_var.set("Готовлю AI-рассказ...")
        self.story_words_label.configure(text=f"Слова: {', '.join(srs_words[:10])}")
        self._last_story_words = srs_words

        # Show loading state in story_text with animation
        self._story_loading = True
        self._story_loading_dots = 0
        self.story_text.configure(state="normal")
        self.story_text.delete("1.0", "end")
        self.story_text.insert("end", "⏳ Готовлю рассказ", "muted")
        self.story_text.configure(state="disabled")

        def _animate_loading():
            if not getattr(self, "_story_loading", False):
                return
            self._story_loading_dots = (self._story_loading_dots + 1) % 4
            try:
                self.story_text.configure(state="normal")
                self.story_text.delete("1.0", "end")
                self.story_text.insert("end", "⏳ Готовлю рассказ" + "." * self._story_loading_dots, "muted")
                self.story_text.configure(state="disabled")
            except Exception:
                pass
            self.root.after(500, _animate_loading)
        _animate_loading()

        def _worker():
            try:
                from coach import build_story_prompt
                prompt = build_story_prompt(level, srs_words, topic)
                story = self.client.generate(model, prompt, use_cache=False)
                self._last_story_text = story
                self.response_queue.put(("story_text", story))
                self.response_queue.put(("status", f"{COACH_NAME} готова к практике"))
            except Exception as exc:
                self.response_queue.put(("error", f"Рассказ не удалось создать: {exc}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _speak_story(self) -> None:
        """Speak the currently displayed story via TTS."""
        story = getattr(self, "_last_story_text", "")
        if not story:
            messagebox.showinfo("Озвучка", "Сначала сгенерируйте рассказ.")
            return
        text = extract_speakable_text(story, max_lines=0)
        if text:
            rate = self.tts_rate_var.get()
            if self._is_dialogue_text(text):
                voice_a = self.tts_voice_var.get()
                voice_b = self.tts_voice2_var.get()
                threading.Thread(target=self.voice.speak_dialogue,
                                 args=(text, voice_a, voice_b, rate), daemon=True).start()
            else:
                voice_name = self.tts_voice_var.get()
                threading.Thread(target=self.voice.speak, args=(text, "en-US", rate, voice_name), daemon=True).start()

    def _ask_story_question(self) -> None:
        """Answer a comprehension question about the current story."""
        question = self.story_qa_var.get().strip()
        if not question:
            return
        story = getattr(self, "_last_story_text", "")
        if not story:
            messagebox.showinfo("Вопрос", "Сначала сгенерируйте рассказ.")
            return
        model = self.model_var.get().strip()
        if not model:
            messagebox.showwarning("Вопрос", "Нет локальной модели.")
            return
        self.story_qa_result.configure(state="normal")
        self.story_qa_result.delete("1.0", "end")
        self.story_qa_result.insert("end", "Ольга думает...\n", "muted")
        self.story_qa_result.configure(state="disabled")
        self.story_qa_var.set("")

        def _worker():
            try:
                prompt = (
                    f"Here is a story:\n{story}\n\n"
                    f"Question: {question}\n"
                    f"Answer the question about the story. "
                    f"If the question is in Russian, answer in Russian. "
                    f"If in English, answer in English. Be concise."
                )
                answer = self.client.generate(model, prompt, use_cache=False)
                self.response_queue.put(("story_qa", answer))
            except Exception as exc:
                self.response_queue.put(("error", f"Не удалось ответить: {exc}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _add_story_words_to_srs(self) -> None:
        """Add words from the last story to SRS."""
        words = getattr(self, "_last_story_words", [])
        if not words:
            messagebox.showinfo("SRS", "Сначала сгенерируйте рассказ.")
            return
        added = 0
        for word in words:
            try:
                self.course.srs.add_or_update(word.lower(), word, "", "")
                added += 1
            except Exception:
                pass
        self.course._save_srs()
        self._refresh_learn()
        messagebox.showinfo("SRS", f"Добавлено слов в SRS: {added}")

    def _new_dictation(self) -> None:
        """Generate a new dictation sentence and speak it."""
        model = self.model_var.get().strip()
        if not model:
            messagebox.showwarning("Диктант", "Нет локальной модели.")
            return
        level = self.course.level
        self.status_var.set("Готовлю диктант...")
        self.dictation_result_label.configure(text="")
        self.dictation_entry.delete(0, "end")
        def _worker():
            try:
                from coach import build_dictation_prompt
                prompt = build_dictation_prompt(level)
                sentence = self.client.generate(model, prompt, use_cache=False)
                sentence = sentence.strip().strip('"').strip(".")
                self._dictation_sentence = sentence
                self.response_queue.put(("status", f"{COACH_NAME} готова к практике"))
                threading.Thread(target=self.voice.speak, args=(sentence, "en-US"), daemon=True).start()
            except Exception as exc:
                self.response_queue.put(("error", f"Диктант не удалось создать: {exc}"))
        threading.Thread(target=_worker, daemon=True).start()

    def _replay_dictation(self, slow: bool = False) -> None:
        """Replay the current dictation sentence via TTS."""
        sentence = getattr(self, "_dictation_sentence", "")
        if not sentence:
            messagebox.showinfo("Диктант", "Сначала нажмите «Новое предложение».")
            return
        rate = 120 if slow else 175
        threading.Thread(target=self.voice.speak, args=(sentence, "en-US", rate), daemon=True).start()

    def _check_dictation(self) -> None:
        """Check the user's dictation input against the original sentence."""
        sentence = getattr(self, "_dictation_sentence", "")
        if not sentence:
            messagebox.showinfo("Диктант", "Сначала нажмите «Новое предложение».")
            return
        user_input = self.dictation_entry.get().strip()
        if not user_input:
            return
        import difflib
        original_words = sentence.lower().replace(".", "").replace(",", "").split()
        user_words = user_input.lower().replace(".", "").replace(",", "").split()
        similarity = difflib.SequenceMatcher(None, original_words, user_words).ratio()
        # Find wrong/missing words
        matcher = difflib.SequenceMatcher(None, original_words, user_words)
        errors = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != "equal":
                if tag in ("replace", "delete"):
                    for w in original_words[i1:i2]:
                        errors.append(f"✗ {w}")
                if tag == "insert":
                    for w in user_words[j1:j2]:
                        errors.append(f"+ {w} (лишнее)")
        if similarity >= 0.95:
            self.dictation_result_label.configure(
                text=f"✅ Отлично! Точность: {int(similarity*100)}%\nОригинал: {sentence}",
                fg=SUCCESS)
        elif similarity >= 0.7:
            self.dictation_result_label.configure(
                text=f"⚠️ Почти! Точность: {int(similarity*100)}%\nОшибки: {', '.join(errors[:5])}\nОригинал: {sentence}",
                fg=ACCENT)
        else:
            self.dictation_result_label.configure(
                text=f"❌ Точность: {int(similarity*100)}%\nОшибки: {', '.join(errors[:5])}\nОригинал: {sentence}",
                fg=DANGER)

    def _read_web_article(self) -> None:
        """Fetch a web article, adapt it to the learner's level, and display in story_text."""
        url = self.web_url_var.get().strip()
        if not url:
            messagebox.showinfo("Чтение", "Введите URL статьи.")
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        model = self.model_var.get().strip()
        if not model:
            messagebox.showwarning("Чтение", "Нет локальной модели.")
            return
        level = self.course.level
        self.status_var.set("Загружаю статью...")
        self.story_text.configure(state="normal")
        self.story_text.delete("1.0", "end")
        self.story_text.insert("end", f"Загружаю: {url}\n\n", "muted")
        self.story_text.configure(state="disabled")

        def _worker():
            try:
                # Fetch article
                import urllib.request
                import html.parser
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
                })
                with urllib.request.urlopen(req, timeout=15) as resp:
                    raw_html = resp.read().decode("utf-8", errors="replace")

                # Simple HTML text extraction
                class _TextExtractor(html.parser.HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self._skip = False
                        self._chunks: list[str] = []
                    def handle_starttag(self, tag, attrs):
                        if tag in ("script", "style", "nav", "footer", "header"):
                            self._skip = True
                    def handle_endtag(self, tag):
                        if tag in ("script", "style", "nav", "footer", "header"):
                            self._skip = False
                        if tag in ("p", "div", "br", "h1", "h2", "h3"):
                            self._chunks.append("\n")
                    def handle_data(self, data):
                        if not self._skip:
                            self._chunks.append(data)

                extractor = _TextExtractor()
                extractor.feed(raw_html)
                article_text = " ".join(extractor._chunks)
                # Clean up whitespace
                article_text = " ".join(article_text.split())
                if len(article_text) < 100:
                    self.response_queue.put(("error", "Не удалось извлечь текст статьи."))
                    self.response_queue.put(("status", f"{COACH_NAME} готова к практике"))
                    return

                self.response_queue.put(("status", "Адаптирую под уровень..."))
                from coach import build_reading_adaptation_prompt
                prompt = build_reading_adaptation_prompt(level, article_text)
                adapted = self.client.generate(model, prompt, use_cache=False)
                self.response_queue.put(("story_text", adapted))
                self.response_queue.put(("status", f"{COACH_NAME} готова к практике"))

                # Speak if voice output is on
                if self.voice_output_var.get():
                    text = extract_speakable_text(adapted, max_lines=0)
                    if text:
                        voice_name = self.tts_voice_var.get()
                        threading.Thread(target=self.voice.speak, args=(text, "en-US", 0, voice_name), daemon=True).start()
            except Exception as exc:
                self.response_queue.put(("error", f"Не удалось загрузить статью: {exc}"))
                self.response_queue.put(("status", f"{COACH_NAME} готова к практике"))

        threading.Thread(target=_worker, daemon=True).start()

    def _autosave_chat(self) -> None:
        """Save chat history after each response."""
        try:
            self.coach.save_history(self.chat_history_path)
        except Exception as e:
            logger.warning("Autosave failed: %s", e)

    def _cleanup_srs(self) -> None:
        """Archive easy SRS cards to reduce file size."""
        try:
            import json
            srs_path = self.data_root / "srs_state.json"
            if not srs_path.exists():
                return
            data = json.loads(srs_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or len(data) < 100:
                return
            archived = 0
            to_remove = []
            for key, card in data.items():
                if not isinstance(card, dict):
                    continue
                interval = card.get("interval", 0)
                reps = card.get("reps", 0)
                ease = card.get("ease", 2.5)
                if interval >= 60 and reps >= 5 and ease >= 2.5:
                    to_remove.append(key)
                    archived += 1
            for key in to_remove:
                del data[key]
            if archived > 0:
                srs_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                self._append_chat("system", f"Архивировано {archived} изученных слов из SRS.\n\n")
        except Exception as e:
            logger.warning("SRS cleanup failed: %s", e)

    def refresh_models(self) -> None:
        self.client.invalidate_models_cache()
        self.status_var.set("Обновляю список моделей...")
        threading.Thread(target=self._connect_and_load_models, daemon=True).start()

    def _pull_model_dialog(self) -> None:
        """Диалог для подкачки новой модели Ollama из сети."""
        from tkinter import simpledialog
        model_name = simpledialog.askstring(
            "Скачать модель",
            "Введите имя модели для загрузки\n(например: qwen2.5:7b-instruct, llama3.1:8b, gemma3:4b):",
            initialvalue="qwen2.5:7b-instruct",
            parent=self.root,
        )
        if not model_name:
            return
        self._append_chat("system", f"Загрузка модели {model_name}...\nЭто может занять несколько минут.\n\n")
        self.status_var.set(f"Загрузка {model_name}...")
        threading.Thread(target=self._pull_model_worker, args=(model_name,), daemon=True).start()

    def _pull_model_worker(self, model_name: str) -> None:
        ok, message = self.client.pull_model(model_name)
        if ok:
            self.response_queue.put(("system", f"✅ {message}\n\n"))
            self.response_queue.put(("status", f"{COACH_NAME} готова к практике"))
            self._connect_and_load_models()
        else:
            self.response_queue.put(("error", message))
            self.response_queue.put(("status", "Ошибка загрузки модели"))

    def record_voice(self) -> None:
        self.status_var.set("Ольга слушает микрофон...")
        self._append_chat("system", f"Запись: язык {self.voice_input_var.get()}, до 12 сек.\n\n")
        threading.Thread(target=self._record_voice_worker, daemon=True).start()

    def _record_voice_worker(self) -> None:
        try:
            voice_data = self.voice.transcribe(self.voice_input_var.get(), seconds=12)
            if voice_data.get("error"):
                self.response_queue.put(("system", f"Ошибка записи: {voice_data['error']}\n\n"))
                self.response_queue.put(("status", "Готов к практике"))
                return
            text = (voice_data.get("transcript") or "").strip()
            if not text:
                self.response_queue.put(("system", "Речь не распознана. Попробуйте говорить ближе к микрофону.\n\n"))
                self.response_queue.put(("status", "Готов к практике"))
                return
            analysis = analyze_speaking(voice_data)
            self.last_voice_analysis = analysis
            self.response_queue.put(("system", f"Распознано:\n{text}\n\n"))
            self.response_queue.put(("transcript", text))
            self.response_queue.put(("course", "refresh"))
        except Exception as exc:
            self.response_queue.put(("error", str(exc)))
            self.response_queue.put(("status", "Ошибка записи. Попробуйте ещё раз."))

    def _speak_response(self, payload: str) -> None:
        text = extract_speakable_text(payload, max_lines=4)
        if self._is_dialogue_text(text):
            voice_a = self.tts_voice_var.get()
            voice_b = self.tts_voice2_var.get()
            threading.Thread(target=self.voice.speak_dialogue,
                             args=(text, voice_a, voice_b, 0), daemon=True).start()
        else:
            language = "ru-RU" if re.search(r"[А-Яа-яЁё]", text) else "en-US"
            voice_name = self.tts_voice_var.get()
            threading.Thread(target=self.voice.speak, args=(text, language, 0, voice_name), daemon=True).start()

    @staticmethod
    def _is_dialogue_text(text: str) -> bool:
        """Check if text contains dialogue speaker labels (A:, B:, Speaker A:, Anna:)."""
        if not text or len(text) < 20:
            return False
        # Count lines matching speaker label pattern
        label_re = re.compile(
            r"^\s*(?:"
            r"(?:Speaker|Person)\s+\w+\s*[:\-]"
            r"|(?:[A-C])\s*[:\-]"
            r"|(?:[A-Z][a-z]+)\s*[:\-]"
            r")",
            re.MULTILINE,
        )
        matches = label_re.findall(text)
        return len(matches) >= 2

    def _speak_last_response(self, rate: int) -> None:
        self.voice.stop_speaking()
        self.chat.configure(state="normal")
        content = self.chat.get("1.0", "end").strip()
        self.chat.configure(state="disabled")
        if not content:
            return
        lines = content.split("\n")
        for line in reversed(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith("—") and not stripped.startswith("Ольга:"):
                text = extract_speakable_text(stripped)
                if text:
                    if self._is_dialogue_text(text):
                        voice_a = self.tts_voice_var.get()
                        voice_b = self.tts_voice2_var.get()
                        threading.Thread(target=self.voice.speak_dialogue,
                                         args=(text, voice_a, voice_b, rate), daemon=True).start()
                    else:
                        language = "ru-RU" if re.search(r"[А-Яа-яЁё]", text) else "en-US"
                        voice_name = self.tts_voice_var.get()
                        threading.Thread(target=self.voice.speak, args=(text, language, rate, voice_name), daemon=True).start()
                    return

    def _stop_speaking(self) -> None:
        self.voice.stop_speaking()

    def _stop_generation(self) -> None:
        """Cancel ongoing AI generation."""
        if self.is_generating:
            self.client.cancel_generation()
            self.is_generating = False
            self._streaming_active = False
            self._hide_typing()
            self.send_btn.configure(state="normal")
            self.status_var.set("Генерация остановлена")
            self._append_chat("system", "Генерация остановлена пользователем.\n\n")
            self._autosave_chat()

    def _toggle_theme(self) -> None:
        dark = toggle_dark_mode()
        self.theme_btn.configure(text="☀ Светлая" if dark else "🌙 Тёмная")
        try:
            self.root.configure(bg=BG)
        except Exception:
            pass
        ctk.set_appearance_mode("dark" if dark else "light")
        self._refresh_all()
        self._apply_theme_to_widgets(self.root)
        save_theme_pref()

    def _apply_theme_to_widgets(self, widget) -> None:
        """Apply theme colors to widget tree — handles both tk and CTk widgets."""
        widget_type = type(widget).__name__
        try:
            if widget_type in ("CTkFrame",):
                widget.configure(fg_color=CARD_BG)
            elif widget_type in ("CTkLabel",):
                # Preserve CTkLabel text_color — don't override
                pass
            elif widget_type in ("CTkButton",):
                pass  # CTkButton manages its own colors
            elif widget_type in ("CTkEntry",):
                widget.configure(fg_color=CHAT_BG, text_color=CHAT_FG)
            elif widget_type == "CTk":
                pass  # Root window managed by CTk appearance mode
            else:
                # Standard tkinter widgets
                cls = widget.winfo_class()
                card_bgs = {"#ffffff", "#16213e", "#faf8f5", "#1a1a2e"}
                bg_bgs = {"#faf8f5", "#1a1a2e"}
                try:
                    current_bg = str(widget.cget("bg"))
                except Exception:
                    current_bg = ""
                try:
                    current_fg = str(widget.cget("fg"))
                except Exception:
                    current_fg = ""
                if cls in ("Frame", "Labelframe"):
                    if current_bg in card_bgs and current_bg not in bg_bgs:
                        widget.configure(bg=CARD_BG)
                    else:
                        widget.configure(bg=BG)
                elif cls == "Label":
                    # Determine the label's bg
                    if current_bg in card_bgs:
                        new_bg = CARD_BG
                    else:
                        new_bg = BG
                    # Preserve semantic fg role
                    muted_fgs = {"#9ca3af", "#6b6b80", "#606080", "#8a8580", "#75706a", "#8a8aa0"}
                    secondary_fgs = {"#6b6560", "#a0a0b0", "#5a5550"}
                    accent_fgs = {"#2563eb", "#e94560"}
                    success_fgs = {"#16a34a", "#00ff88"}
                    warning_fgs = {"#d97706"}
                    danger_fgs = {"#dc2626", "#ff4466"}
                    if current_fg in muted_fgs:
                        new_fg = TEXT_MUTED
                    elif current_fg in secondary_fgs:
                        new_fg = TEXT_SECONDARY
                    elif current_fg in accent_fgs:
                        new_fg = ACCENT
                    elif current_fg in success_fgs:
                        new_fg = SUCCESS
                    elif current_fg in warning_fgs:
                        new_fg = WARNING
                    elif current_fg in danger_fgs:
                        new_fg = DANGER
                    else:
                        new_fg = TEXT_PRIMARY
                    widget.configure(bg=new_bg, fg=new_fg)
                elif cls == "Button":
                    if current_bg == ACCENT:
                        widget.configure(bg=ACCENT, fg="white", activebackground=ACCENT_HOVER)
                    else:
                        widget.configure(bg=CARD_BG, fg=TEXT_PRIMARY, activebackground=BUTTON_IDLE_BG)
                elif cls == "Text":
                    widget.configure(bg=CHAT_BG, fg=CHAT_FG)
                    dark = is_dark()
                    tag_colors = {
                        "user": "#4a9eff" if dark else "#0066cc",
                        "assistant": "#d4a574" if dark else "#8B4513",
                        "system": TEXT_MUTED,
                        "npc": "#4a9eff" if dark else "#0066cc",
                        "player": "#50c878" if dark else "#008844",
                        "detective": "#50c878" if dark else "#008844",
                        "evidence": "#d4a017" if dark else "#8a6800",
                        "learned": SUCCESS,
                        "rating": WARNING,
                        "muted": TEXT_MUTED,
                    }
                    for tag, color in tag_colors.items():
                        try:
                            widget.tag_config(tag, foreground=color)
                        except tk.TclError:
                            pass
                elif cls == "Canvas":
                    widget.configure(bg=BG)
                elif cls == "Entry":
                    widget.configure(bg=CARD_BG, fg=TEXT_PRIMARY)
        except (tk.TclError, ValueError, Exception):
            pass
        try:
            for child in widget.winfo_children():
                self._apply_theme_to_widgets(child)
        except Exception:
            pass

    def _show_help(self) -> None:
        """Show help/FAQ dialog."""
        win = tk.Toplevel(self.root)
        win.title("Помощь")
        win.geometry("560x520")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        win.configure(bg=BG)

        tk.Label(win, text="❓", bg=BG, fg=ACCENT, font=("SF Pro Display", 32)).pack(pady=(16, 4))
        tk.Label(win, text="Помощь", bg=BG, fg=TEXT_PRIMARY,
                 font=FONT_HEADING).pack(pady=(0, 8))

        faq_text = tk.Text(win, wrap="word", bg=BG, fg=TEXT_PRIMARY,
                           font=FONT_BODY, padx=16, pady=8, relief="flat",
                           borderwidth=0, state="disabled")
        faq_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        content = """Частые вопросы

■ Как начать заниматься?
  Напишите /start в чате во вкладке «Практика». Ольга подберёт задание.

■ Как сменить AI-модель?
  Вкладка «Настройки» → Модель → выберите из списка.
  Модели загружаются через: ollama pull qwen2.5:7b-instruct

■ Как Ольга читает текст вслух?
  Включите «Озвучивать» в настройках практики. Русский текст
  озвучивает голос Milena, английский — выбранный голос (Samantha по умолчанию).

■ Как добавить слово в повторение?
  Выделите слово в чате → правый клик → «В повторение».
  Или откройте вкладку «Учить» → SRS повторение.

■ Как работают AI-рассказы?
  Вкладка «Рассказы» → «Сгенерировать». Ольга пишет рассказ
  из ваших SRS-слов на случайную тему. Можно задать вопрос по рассказу.

■ Как перенести данные на другой Mac?
  Настройки → «Резервная копия» (сохранит ZIP). На новом Mac:
  Настройки → «Восстановить».

■ Сколько занимает установка Ollama?
  ~250 МБ скачивание + 4–8 ГБ на модель. Первый запуск
  может занять 5–10 минут.

■ Приложение не отвечает / зависло
  Проверьте, что Ollama запущена. Перезапустите приложение.
  Лог: ~/Library/Application Support/OlgaEnglishCoach/app.log

■ Активация лицензии
  Настройки → «Активировать» → введите ключ формата
  OLGA-XXXX-XXXX-XXXX-XXXX.

■ Обратная связь
  Email: support@olga-english-coach.com
"""

        faq_text.configure(state="normal")
        faq_text.insert("1.0", content)
        faq_text.configure(state="disabled")

        make_button(win, "Закрыть", win.destroy).pack(pady=(0, 16))

    def _show_license_activation(self) -> None:
        """Show license activation dialog from settings."""
        win = tk.Toplevel(self.root)
        win.title("Активация лицензии")
        win.geometry("460x320")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        win.configure(bg=BG)

        tk.Label(win, text="🔑", bg=BG, fg=ACCENT, font=("SF Pro Display", 36)).pack(pady=(20, 4))
        tk.Label(win, text="Активация лицензии", bg=BG, fg=TEXT_PRIMARY,
                 font=FONT_HEADING).pack()
        info = self.license.get_info()
        if info["activated"]:
            tk.Label(win, text=f"✅ Лицензия активирована\nКлюч: {info['license_key'][:14]}...",
                     bg=BG, fg=SUCCESS, font=FONT_BODY, justify="center").pack(pady=(8, 16))
            make_button(win, "Закрыть", win.destroy).pack()
            return
        tk.Label(win, text=f"Пробный период: осталось {info['trial_days_left']} дн.\n"
                           "Введите лицензионный ключ для активации.",
                 bg=BG, fg=TEXT_SECONDARY, font=FONT_BODY,
                 justify="center", wraplength=400).pack(pady=(8, 12))

        key_var = tk.StringVar()
        entry = tk.Entry(win, textvariable=key_var, bg=CHAT_BG, fg=CHAT_FG,
                         relief="solid", borderwidth=1, font=FONT_MONO,
                         justify="center", width=28)
        entry.pack(pady=(0, 8))
        entry.focus_set()

        def _activate():
            key = key_var.get().strip()
            ok, msg = self.license.activate(key)
            if ok:
                win.destroy()
                self._append_chat("system", "✅ Лицензия активирована. Спасибо!\n\n")
                messagebox.showinfo("Активация", "Лицензия успешно активирована!")
            else:
                messagebox.showwarning("Активация", msg, parent=win)

        btn_frame = tk.Frame(win, bg=BG)
        btn_frame.pack(fill="x", padx=24, pady=(0, 16))
        make_button(btn_frame, "Активировать", _activate, accent=True).pack(side="right")
        make_button(btn_frame, "Отмена", win.destroy).pack(side="left")

    def _export_data(self) -> None:
        """Export user data to a ZIP backup."""
        import zipfile
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP archive", "*.zip")],
            initialfile=f"olga_backup_{date.today().isoformat()}.zip",
            parent=self.root,
        )
        if not path:
            return
        try:
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                for fname in ["state.json", "srs.json", "chat_history.json",
                              "license.json", "theme_pref.json"]:
                    fpath = self.data_root / fname
                    if fpath.exists():
                        zf.write(fpath, fname)
            messagebox.showinfo("Резервная копия", f"Данные сохранены в:\n{path}")
        except Exception as exc:
            messagebox.showerror("Резервная копия", f"Ошибка: {exc}")

    def _import_data(self) -> None:
        """Import user data from a ZIP backup."""
        import zipfile
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            filetypes=[("ZIP archive", "*.zip")],
            parent=self.root,
        )
        if not path:
            return
        try:
            with zipfile.ZipFile(path, "r") as zf:
                for fname in zf.namelist():
                    if fname in ["state.json", "srs.json", "chat_history.json",
                                 "license.json", "theme_pref.json"]:
                        zf.extract(fname, self.data_root)
            messagebox.showinfo("Восстановление",
                                "Данные восстановлены. Перезапустите приложение.")
        except Exception as exc:
            messagebox.showerror("Восстановление", f"Ошибка: {exc}")

    def _export_csv(self) -> None:
        import csv
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="olga_progress.csv",
            parent=self.root,
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["Дата", "Тип", "Режим", "Голос", "Слов пользователя", "Слов ответ", "Секунд", "Ошибок", "Грамматика", "Словарь"])
                for s in self.course.state.get("sessions", []):
                    writer.writerow([
                        s.get("date", ""),
                        PRACTICE_RU.get(s.get("practice_type", ""), s.get("practice_type", "")),
                        s.get("mode", ""),
                        "да" if s.get("voice") else "нет",
                        s.get("user_words", 0),
                        s.get("assistant_words", 0),
                        s.get("duration_seconds", 0),
                        s.get("error_count", 0),
                        s.get("grammar_point", ""),
                        s.get("vocab_theme", ""),
                    ])
            messagebox.showinfo("Экспорт", f"Прогресс сохранён в:\n{path}")
        except Exception as exc:
            messagebox.showerror("Экспорт", f"Ошибка: {exc}")

    def _export_pdf_report(self) -> None:
        """Export a styled PDF progress report with Unicode support."""
        try:
            from fpdf import FPDF
        except ImportError:
            messagebox.showerror("Экспорт PDF", "Модуль fpdf2 не установлен.\n\npip3.12 install fpdf2")
            return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile="olga_progress_report.pdf",
            parent=self.root,
        )
        if not path:
            return
        try:
            font_path = None
            for candidate in [
                "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
                "/Library/Fonts/Arial Unicode.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ]:
                if Path(candidate).exists():
                    font_path = candidate
                    break
            pdf = FPDF()
            pdf.add_page()
            if font_path:
                pdf.add_font("Uni", "", font_path, uni=True)
                pdf.set_font("Uni", size=16)
            else:
                pdf.set_font("Helvetica", size=16)
            pdf.cell(0, 10, "Olga English Coach — Отчёт прогресса", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font_size(11)
            pdf.ln(5)

            st = self.course.state
            pdf.cell(0, 8, f"Уровень: {st.get('level', 'B1')}", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 8, f"Цель: {st.get('goal_days', 0)} дней", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 8, f"Завершено сессий: {st.get('completed_sessions', 0)}", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 8, f"Всего минут: {st.get('total_minutes', 0)}", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 8, f"Активных дней: {len(st.get('daily_activity', {}))}", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)

            sessions = st.get("sessions", [])
            pdf.set_font_size(13)
            pdf.cell(0, 8, f"Сессии ({len(sessions)})", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font_size(10)
            for s in sessions[-20:]:
                date_s = s.get("date", "")
                mode = s.get("mode", "")
                dur = s.get("duration_seconds", 0)
                errs = s.get("error_count", 0)
                pdf.cell(0, 6, f"  {date_s} | {mode} | {dur}s | ошибок: {errs}", new_x="LMARGIN", new_y="NEXT")

            pdf.ln(4)
            pdf.set_font_size(13)
            pdf.cell(0, 8, "Игры", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font_size(10)
            scores = st.get("game_scores", [])
            pdf.cell(0, 6, f"  Word Battle: игр={len(scores)}, рекорд={scores[0]['score'] if scores else 0}", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 6, f"  Survival: сцен пройдено={len(st.get('survival_completed_scenes', []))}", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 6, f"  Detective: дел раскрыто={len(st.get('detective_solved_cases', []))}", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 6, f"  Time Loop: петель разорвано={len(st.get('time_loop_broken', []))}", new_x="LMARGIN", new_y="NEXT")

            pdf.ln(4)
            pdf.set_font_size(13)
            pdf.cell(0, 8, "Навыки", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font_size(10)
            for skill, val in st.get("skill_scores", {}).items():
                pdf.cell(0, 6, f"  {skill}: {val}", new_x="LMARGIN", new_y="NEXT")

            pdf.output(path)
            messagebox.showinfo("Экспорт PDF", f"Отчёт сохранён в:\n{path}")
        except Exception as exc:
            logger.error("PDF export failed: %s", exc)
            messagebox.showerror("Экспорт PDF", f"Ошибка: {exc}")

    # ──────────────────────────────────────────────────────────────────
    #  Flashcards tab — чистый режим карточек с SRS, без чата
    # ──────────────────────────────────────────────────────────────────

    def _build_flashcards(self) -> None:
        frame = self.flashcards_frame
        scroll_frame = ctk.CTkScrollableFrame(frame, fg_color=BG, scrollbar_button_color=BORDER,
                                              scrollbar_button_hover_color=ACCENT)
        scroll_frame.pack(fill="both", expand=True, padx=0, pady=0)
        self._sf_flashcards = scroll_frame

        # ── Session stats card ──
        stats_card = make_card(scroll_frame, padx=16, pady=12)
        stats_card.pack(fill="x", pady=(0, 8))
        self._fc_stats_label = tk.Label(stats_card, text="", bg=CARD_BG, fg=TEXT_SECONDARY,
                                        font=FONT_BODY, justify="left")
        self._fc_stats_label.pack(anchor="w")

        # ── Card display area ──
        card_area = make_card(scroll_frame, padx=24, pady=24)
        card_area.pack(fill="both", expand=True, pady=(0, 8))

        # Front (word)
        self._fc_front_label = tk.Label(card_area, text="Нажмите «Начать»", bg=CARD_BG,
                                        fg=TEXT_PRIMARY, font=FONT_HEADING, wraplength=600,
                                        justify="center")
        self._fc_front_label.pack(pady=(20, 4))

        # IPA
        self._fc_ipa_label = tk.Label(card_area, text="", bg=CARD_BG, fg=TEXT_MUTED,
                                      font=FONT_MONO)
        self._fc_ipa_label.pack(pady=(0, 8))

        # Back (translation) — hidden initially
        self._fc_back_label = tk.Label(card_area, text="", bg=CARD_BG, fg=ACCENT,
                                       font=FONT_HEADING, wraplength=600, justify="center")
        self._fc_back_label.pack(pady=(4, 4))

        # Example
        self._fc_example_label = tk.Label(card_area, text="", bg=CARD_BG, fg=TEXT_SECONDARY,
                                          font=FONT_BODY, wraplength=600, justify="center")
        self._fc_example_label.pack(pady=(8, 20))

        # ── Progress bar ──
        self._fc_progress = make_progress_bar(scroll_frame, 0)
        self._fc_progress.pack(fill="x", pady=(0, 8))
        self._fc_progress_label = tk.Label(scroll_frame, text="", bg=BG, fg=TEXT_MUTED,
                                           font=FONT_SMALL)
        self._fc_progress_label.pack(anchor="w", pady=(0, 8))

        # ── Buttons ──
        btn_row = tk.Frame(scroll_frame, bg=BG)
        btn_row.pack(fill="x", pady=(0, 8))

        make_button(btn_row, "▶ Начать сессию", self._fc_start_session, accent=True).pack(side="left", padx=(0, 8))
        make_button(btn_row, "🔄 Перевернуть", self._fc_flip).pack(side="left", padx=(0, 8))
        make_button(btn_row, "🔊 Озвучить", self._fc_speak).pack(side="left")

        # Rating buttons (hidden until card is flipped)
        self._fc_rating_row = tk.Frame(scroll_frame, bg=BG)
        self._fc_rating_row.pack(fill="x", pady=(0, 8))

        make_button(self._fc_rating_row, "❌ Не знаю", lambda: self._fc_rate("again")).pack(side="left", padx=(0, 4))
        make_button(self._fc_rating_row, "😐 Сложно", lambda: self._fc_rate("hard")).pack(side="left", padx=(0, 4))
        make_button(self._fc_rating_row, "👌 Знаю", lambda: self._fc_rate("good")).pack(side="left", padx=(0, 4))
        make_button(self._fc_rating_row, "🚀 Легко", lambda: self._fc_rate("easy")).pack(side="left")

        # ── State ──
        self._fc_session: list = []
        self._fc_index: int = 0
        self._fc_flipped: bool = False
        self._fc_current_card = None

        self._fc_update_stats()

    def _fc_update_stats(self) -> None:
        due = self.course.srs.due_count()
        new = self.course.srs.new_count()
        mastered = self.course.srs.mastered_count()
        total = len(self.course.srs.cards)
        self._fc_stats_label.config(
            text=f"📊 Всего: {total}  |  К повторению: {due}  |  Новых: {new}  |  Изучено: {mastered}"
        )

    def _fc_start_session(self) -> None:
        cards = self.course.srs.review_session(limit=20)
        if not cards:
            self._fc_front_label.config(text="Нет карточек для повторения! 🎉")
            self._fc_back_label.config(text="")
            self._fc_ipa_label.config(text="")
            self._fc_example_label.config(text="")
            self._fc_progress_label.config(text="")
            return
        self._fc_session = cards
        self._fc_index = 0
        self._fc_show_card()

    def _fc_show_card(self) -> None:
        if self._fc_index >= len(self._fc_session):
            self._fc_front_label.config(text="Сессия завершена! 🎉")
            self._fc_back_label.config(text="")
            self._fc_ipa_label.config(text="")
            self._fc_example_label.config(text="")
            self._fc_progress_label.config(text="")
            self._fc_update_stats()
            return

        card = self._fc_session[self._fc_index]
        self._fc_current_card = card
        self._fc_flipped = False

        self._fc_front_label.config(text=card.front)
        self._fc_ipa_label.config(text=card.ipa or "")
        self._fc_back_label.config(text="")
        self._fc_example_label.config(text="")

        # Progress
        progress_val = self._fc_index / max(len(self._fc_session), 1)
        self._fc_progress.set(progress_val)
        self._fc_progress_label.config(
            text=f"Карточка {self._fc_index + 1} из {len(self._fc_session)}"
        )

    def _fc_flip(self) -> None:
        if not self._fc_current_card:
            return
        card = self._fc_current_card
        if not self._fc_flipped:
            self._fc_flipped = True
            self._fc_back_label.config(text=card.back)
            self._fc_example_label.config(text=card.example or "")

    def _fc_rate(self, rating: str) -> None:
        if not self._fc_current_card:
            return
        quality = quality_from_rating(rating)
        self.course.srs.review(self._fc_current_card.card_id, quality)
        self._fc_index += 1
        self._fc_show_card()
        self._fc_update_stats()

    def _fc_speak(self) -> None:
        if not self._fc_current_card:
            return
        text = self._fc_current_card.front
        if self._fc_flipped and self._fc_current_card.example:
            text = self._fc_current_card.example
        threading.Thread(target=self.voice.speak, args=(text, "en-US", 0, ""), daemon=True).start()

    # ──────────────────────────────────────────────────────────────────
    #  Diglot Weave tab — билингвальные рассказы с постепенным замещением
    # ──────────────────────────────────────────────────────────────────

    def _build_diglot(self) -> None:
        frame = self.diglot_frame
        scroll_frame = ctk.CTkScrollableFrame(frame, fg_color=BG, scrollbar_button_color=BORDER,
                                              scrollbar_button_hover_color=ACCENT)
        scroll_frame.pack(fill="both", expand=True, padx=0, pady=0)
        self._sf_diglot = scroll_frame

        # ── Info card ──
        info_card = make_card(scroll_frame, padx=16, pady=16)
        info_card.pack(fill="x", pady=(0, 8))
        tk.Label(info_card, text="🧵 Diglot Weave — билингвальные рассказы", bg=CARD_BG,
                 fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        tk.Label(info_card, text=(
            "Рассказ начинается на русском и постепенно вплетает английские слова.\n"
            "Контекст помогает понять значение без перевода — как дети учат язык.\n"
            "5 абзацев: от 90% русского → до 90% английского."
        ), bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL, wraplength=700,
            justify="left").pack(anchor="w", pady=(4, 8))

        # ── Generator controls ──
        gen_card = make_card(scroll_frame, padx=16, pady=16)
        gen_card.pack(fill="x", pady=(0, 8))

        topic_row = tk.Frame(gen_card, bg=CARD_BG)
        topic_row.pack(fill="x", pady=(0, 8))
        tk.Label(topic_row, text="Тема:", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack(side="left")
        self.diglot_topic_var = tk.StringVar(value="")
        diglot_entry = tk.Entry(topic_row, textvariable=self.diglot_topic_var, bg=CHAT_BG, fg=CHAT_FG,
                                relief="solid", borderwidth=1, font=FONT_BODY, width=30)
        diglot_entry.pack(side="left", padx=(8, 12))
        tk.Label(topic_row, text="(необязательно)", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL).pack(side="left")

        # SRS words preview
        self.diglot_words_label = tk.Label(gen_card, text="", bg=CARD_BG, fg=TEXT_MUTED,
                                           font=FONT_SMALL, wraplength=700, justify="left")
        self.diglot_words_label.pack(anchor="w", pady=(0, 8))

        # Buttons
        btn_row = tk.Frame(gen_card, bg=CARD_BG)
        btn_row.pack(fill="x")
        make_button(btn_row, "✨ Сгенерировать рассказ", self._generate_diglot, accent=True).pack(side="left", padx=(0, 8))
        make_button(btn_row, "🔊 Озвучить", self._speak_diglot).pack(side="left", padx=(0, 8))
        make_button(btn_row, "➕ Слова в SRS", self._add_diglot_words_to_srs).pack(side="left")

        # ── Story display ──
        story_card = make_card(scroll_frame, padx=16, pady=16)
        story_card.pack(fill="both", expand=True, pady=(0, 8))
        self.diglot_text = tk.Text(story_card, wrap="word", bg=CHAT_BG, fg=CHAT_FG,
                                   font=FONT_BODY, padx=12, pady=12, relief="flat", borderwidth=0,
                                   height=25, state="disabled")
        self.diglot_text.pack(fill="both", expand=True)
        self.diglot_text.tag_configure("title", foreground=TEXT_PRIMARY, font=FONT_HEADING)
        self.diglot_text.tag_configure("muted", foreground=TEXT_MUTED, font=FONT_SMALL)
        self.diglot_text.tag_configure("bold", font=("SF Pro Text", 12, "bold"))
        self.diglot_text.tag_configure("en_word", foreground=ACCENT, font=("SF Pro Text", 12, "bold"))

        # ── Q&A card ──
        qa_card = make_card(scroll_frame, padx=16, pady=16)
        qa_card.pack(fill="x", pady=(0, 8))
        tk.Label(qa_card, text="💬 Вопрос по рассказу", bg=CARD_BG, fg=TEXT_PRIMARY,
                 font=FONT_HEADING).pack(anchor="w")
        tk.Label(qa_card, text="Задайте вопрос по содержанию — Ольга ответит.",
                 bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL, wraplength=700,
                 justify="left").pack(anchor="w", pady=(4, 8))
        qa_row = tk.Frame(qa_card, bg=CARD_BG)
        qa_row.pack(fill="x", pady=(0, 4))
        self.diglot_qa_var = tk.StringVar()
        diglot_qa_entry = tk.Entry(qa_row, textvariable=self.diglot_qa_var, bg=CHAT_BG, fg=CHAT_FG,
                                   relief="solid", borderwidth=1, font=FONT_BODY)
        diglot_qa_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        diglot_qa_entry.bind("<Return>", lambda e: self._ask_diglot_question())
        make_button(qa_row, "Спросить", self._ask_diglot_question, accent=True).pack(side="left")
        self.diglot_qa_result = tk.Text(qa_card, wrap="word", bg=CHAT_BG, fg=CHAT_FG,
                                        font=FONT_BODY, padx=8, pady=8, relief="flat", borderwidth=0,
                                        height=4, state="disabled")
        self.diglot_qa_result.pack(fill="x", pady=(4, 0))

        self._diglot_current_story = ""

    def _generate_diglot(self) -> None:
        srs_words = [c.front for c in list(self.course.srs.cards.values())[:15]]
        topic = self.diglot_topic_var.get().strip()

        # Determine actual words that will be used (including fallback)
        prompt_preview = build_diglot_prompt(self.course.level, srs_words, topic)
        words_match = re.search(r"Английские слова для вплетения: (.+)", prompt_preview)
        used_words = words_match.group(1).split(", ") if words_match else srs_words
        self.diglot_words_label.config(
            text=f"Слова для рассказа: {', '.join(used_words[:8])}{'…' if len(used_words) > 8 else ''}"
        )

        self.diglot_text.config(state="normal")
        self.diglot_text.delete("1.0", "end")
        self.diglot_text.insert("end", "⏳ Генерация рассказа…\n", "muted")
        self.diglot_text.config(state="disabled")

        def _has_russian(text: str) -> bool:
            """Check if text contains enough Cyrillic characters (>=10%)."""
            cyrillic = sum(1 for ch in text if "\u0400" <= ch <= "\u04ff")
            return cyrillic > 0 and (cyrillic / max(len(text), 1)) >= 0.05

        def _worker():
            try:
                model = self.model_var.get().strip()
                prompt = build_diglot_prompt(self.course.level, srs_words, topic)
                response = self.ollama.generate(prompt, model=model)
                # If model ignored Russian base language, retry once with stricter reminder
                if not _has_russian(response):
                    retry_prompt = (
                        "Ты НЕПРАВИЛЬНО сгенерировал рассказ. "
                        "Важно: БАЗОВЫЙ ЯЗЫК — РУССКИЙ. Попробуй снова.\n\n" + prompt
                    )
                    response = self.ollama.generate(retry_prompt, model=model)
                self.response_queue.put(("diglot_story", response))
            except Exception as exc:
                self.response_queue.put(("diglot_error", str(exc)))

        threading.Thread(target=_worker, daemon=True).start()

    def _display_diglot_story(self, story: str) -> None:
        self._diglot_current_story = story
        self.diglot_text.config(state="normal")
        self.diglot_text.delete("1.0", "end")

        # Highlight English words (bold markers **word**)
        lines = story.split("\n")
        for line in lines:
            if line.startswith("---"):
                self.diglot_text.insert("end", line + "\n", "muted")
            elif line.startswith("•") or line.startswith("English words used:"):
                self.diglot_text.insert("end", line + "\n", "muted")
            elif line.startswith(("1.", "2.", "3.")) and "?" in line:
                self.diglot_text.insert("end", line + "\n", "muted")
            else:
                # Process **bold** markers
                pos = 0
                while "**" in line[pos:]:
                    start = line.index("**", pos)
                    end = line.find("**", start + 2)
                    if end == -1:
                        break
                    if start > pos:
                        self.diglot_text.insert("end", line[pos:start])
                    word = line[start + 2:end]
                    self.diglot_text.insert("end", word, "en_word")
                    pos = end + 2
                if pos < len(line):
                    self.diglot_text.insert("end", line[pos:])
                self.diglot_text.insert("end", "\n")

        self.diglot_text.config(state="disabled")

    def _speak_diglot(self) -> None:
        if not self._diglot_current_story:
            return
        text = self._diglot_current_story.split("---")[0]
        text = re.sub(r"\*\*", "", text)
        threading.Thread(target=self.voice.speak, args=(text, "en-US", 0, ""), daemon=True).start()

    def _add_diglot_words_to_srs(self) -> None:
        if not self._diglot_current_story:
            return
        # Extract English words from the "English words used:" section
        lines = self._diglot_current_story.split("\n")
        in_word_section = False
        added = 0
        for line in lines:
            if "English words used:" in line:
                in_word_section = True
                continue
            if in_word_section:
                if line.startswith("•"):
                    word = line.replace("•", "").strip()
                    if word and word not in self.course.srs.cards:
                        card_id = f"diglot_{word.lower()}_{date.today().isoformat()}"
                        self.course.srs.add_or_update(card_id, word, "", "")
                        added += 1
                elif line.startswith("Questions:"):
                    break
        if added:
            self.course._save_srs()
            messagebox.showinfo("SRS", f"Добавлено {added} слов в SRS")
        else:
            messagebox.showinfo("SRS", "Новые слова не найдены")

    def _ask_diglot_question(self) -> None:
        question = self.diglot_qa_var.get().strip()
        if not question or not self._diglot_current_story:
            return
        story = self._diglot_current_story.split("---")[0].strip()

        self.diglot_qa_result.config(state="normal")
        self.diglot_qa_result.delete("1.0", "end")
        self.diglot_qa_result.insert("end", "⏳ …\n")
        self.diglot_qa_result.config(state="disabled")

        def _worker():
            try:
                prompt = (
                    f"Here is a diglot weave story:\n{story}\n\n"
                    f"Question: {question}\n"
                    f"Answer the question about the story. "
                    f"If the question is in Russian, answer in Russian. "
                    f"If in English, answer in English. Be concise."
                )
                response = self.ollama.generate(prompt, model=self.model_var.get().strip())
                self.response_queue.put(("diglot_qa", response))
            except Exception as exc:
                self.response_queue.put(("diglot_error", str(exc)))

        threading.Thread(target=_worker, daemon=True).start()
