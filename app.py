#!/usr/bin/env python3
"""Olga English Coach — entry point.

A modular, offline English learning app powered by local Ollama models.
Architecture:
  app.py          — entry point
  ui_main.py      — tabbed UI (Dashboard, Learn, Practice, Progress)
  ui_theme.py     — modern theme and styling
  coach.py        — AI coach logic, prompt building, assessment
  course.py       — adaptive course management with SRS integration
  curriculum.py   — CEFR-aligned grammar, vocabulary, functional language
  srs.py          — SM-2 spaced repetition engine
  ollama_client.py — Ollama API client
  voice_toolkit.py — voice I/O (Swift + macOS say)
"""

from __future__ import annotations

import sys
import logging
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

# Set CTk defaults — dark theme, rounded corners
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

from app_paths import get_resources_dir, get_user_data_dir

# Ensure local imports work when run from .app bundle
_runtime_root = get_resources_dir()
if str(_runtime_root) not in sys.path:
    sys.path.insert(0, str(_runtime_root))

from ui_main import EnglishCoachUI


APP_TITLE = "Olga English Coach"


def setup_logging() -> logging.Logger:
    log_path = get_user_data_dir() / "app.log"
    logger = logging.getLogger("olga")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        fh = logging.FileHandler(str(log_path), encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


def log_exception(exc: BaseException) -> Path:
    log_path = get_user_data_dir() / "startup-error.log"
    details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    log_path.write_text(details, encoding="utf-8")
    return log_path


def main() -> None:
    logger = setup_logging()
    logger.info("Starting Olga English Coach")
    try:
        root = ctk.CTk()
        root.title(APP_TITLE)
        icon_path = _runtime_root.joinpath("assets", "icon.png")
        if icon_path.exists():
            try:
                icon = tk.PhotoImage(file=str(icon_path))
                root.iconphoto(True, icon)
            except Exception:
                pass
        EnglishCoachUI(root)
        root.lift()
        root.attributes("-topmost", True)
        root.after(500, lambda: root.attributes("-topmost", False))
        root.focus_force()
        root.mainloop()
    except Exception as exc:
        log_path = log_exception(exc)
        try:
            messagebox.showerror(
                APP_TITLE,
                f"Ошибка запуска приложения.\n\nЛог сохранён в:\n{log_path}",
            )
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
