"""Modern UI theme for Olga English Coach with dark mode support."""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import customtkinter as ctk


# ─── Light theme ───
_LIGHT = {
    "bg": "#f5f3f0",
    "card_bg": "#ffffff",
    "text_primary": "#1e1b18",
    "text_secondary": "#5a5550",
    "text_muted": "#75706a",
    "border": "#d8d4cf",
    "button_idle_bg": "#eae7e2",
    "chat_bg": "#f8f6f3",
    "chat_fg": "#1e1b18",
}

# ─── Dark theme ───
_DARK = {
    "bg": "#1a1a2e",
    "card_bg": "#16213e",
    "text_primary": "#e8e8e8",
    "text_secondary": "#a0a0b0",
    "text_muted": "#8a8aa0",
    "border": "#2a2a4a",
    "button_idle_bg": "#2a2a4a",
    "chat_bg": "#0f0f23",
    "chat_fg": "#e0e0e0",
}

_current = _DARK.copy()
_is_dark = True

BG = _current["bg"]
CARD_BG = _current["card_bg"]
ACCENT = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
ACCENT_LIGHT = "#dbeafe"
TEXT_PRIMARY = _current["text_primary"]
TEXT_SECONDARY = _current["text_secondary"]
TEXT_MUTED = _current["text_muted"]
SUCCESS = "#16a34a"
WARNING = "#d97706"
DANGER = "#dc2626"
BORDER = _current["border"]
CHART_COLORS = ["#2563eb", "#16a34a", "#d97706", "#7c3aed", "#dc2626"]
BUTTON_IDLE_BG = _current["button_idle_bg"]
CHAT_BG = _current["chat_bg"]
CHAT_FG = _current["chat_fg"]

FONT_TITLE = ("SF Pro Display", 20, "bold")
FONT_HEADING = ("SF Pro Display", 14, "bold")
FONT_BODY = ("SF Pro Text", 12)
FONT_SMALL = ("SF Pro Text", 10)
FONT_MONO = ("SF Mono", 11)


def toggle_dark_mode() -> bool:
    """Toggle between light and dark. Returns True if dark mode is now active."""
    global _current, _is_dark, BG, CARD_BG, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, BORDER, BUTTON_IDLE_BG, CHAT_BG, CHAT_FG
    _is_dark = not _is_dark
    _current = _DARK.copy() if _is_dark else _LIGHT.copy()
    BG = _current["bg"]
    CARD_BG = _current["card_bg"]
    TEXT_PRIMARY = _current["text_primary"]
    TEXT_SECONDARY = _current["text_secondary"]
    TEXT_MUTED = _current["text_muted"]
    BORDER = _current["border"]
    BUTTON_IDLE_BG = _current["button_idle_bg"]
    CHAT_BG = _current["chat_bg"]
    CHAT_FG = _current["chat_fg"]
    return _is_dark


def is_dark() -> bool:
    return _is_dark


_theme_pref_path: Path | None = None


def set_theme_pref_path(path: Path) -> None:
    global _theme_pref_path
    _theme_pref_path = path


def load_theme_pref() -> None:
    """Load saved theme preference on startup. Default is dark."""
    global _is_dark
    if _theme_pref_path and _theme_pref_path.exists():
        try:
            data = json.loads(_theme_pref_path.read_text(encoding="utf-8"))
            if data.get("dark", True):
                # Already dark by default, nothing to do
                pass
            else:
                # User prefers light — switch from dark to light
                _is_dark = True  # toggle will flip to False
                toggle_dark_mode()
        except Exception:
            pass


def save_theme_pref() -> None:
    """Save current theme preference."""
    if _theme_pref_path:
        try:
            _theme_pref_path.write_text(
                json.dumps({"dark": _is_dark}, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass


def apply_theme(root) -> None:
    """Apply theme to root window — works with both tk.Tk and ctk.CTk."""
    try:
        root.configure(bg=BG)
    except Exception:
        pass
    try:
        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background=BG, foreground=TEXT_PRIMARY, font=FONT_BODY)
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD_BG, relief="solid", borderwidth=1)
        style.configure("TLabel", background=BG, foreground=TEXT_PRIMARY, font=FONT_BODY)
        style.configure("Card.TLabel", background=CARD_BG, foreground=TEXT_PRIMARY, font=FONT_BODY)
        style.configure("Title.TLabel", background=BG, foreground=TEXT_PRIMARY, font=FONT_TITLE)
        style.configure("Heading.TLabel", background=BG, foreground=TEXT_PRIMARY, font=FONT_HEADING)
        style.configure("CardHeading.TLabel", background=CARD_BG, foreground=TEXT_PRIMARY, font=FONT_HEADING)
        style.configure("Muted.TLabel", background=BG, foreground=TEXT_SECONDARY, font=FONT_SMALL)
        style.configure("CardMuted.TLabel", background=CARD_BG, foreground=TEXT_SECONDARY, font=FONT_SMALL)
        style.configure("Accent.TLabel", background=BG, foreground=ACCENT, font=FONT_BODY)
        style.configure("Success.TLabel", background=BG, foreground=SUCCESS, font=FONT_BODY)
        style.configure("TButton", font=FONT_BODY, padding=(12, 6))
        style.configure("Accent.TButton", font=FONT_BODY, padding=(14, 8))
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 8), font=FONT_BODY)
        style.map(
            "TNotebook.Tab",
            background=[("selected", CARD_BG), ("!selected", BG)],
            foreground=[("selected", ACCENT), ("!selected", TEXT_SECONDARY)],
        )
        style.configure("TEntry", fieldbackground=CARD_BG, borderwidth=1, relief="solid")
        style.configure("TCombobox", fieldbackground=CARD_BG, borderwidth=1)
    except Exception:
        pass


def make_card(parent: tk.Widget, **kwargs) -> tk.Frame:
    """Create a card frame — uses CTkFrame for rounded corners."""
    try:
        card = ctk.CTkFrame(parent, corner_radius=12, fg_color=CARD_BG, border_width=1, border_color=BORDER)
        if "padx" in kwargs:
            card._card_padx = kwargs.pop("padx")
        if "pady" in kwargs:
            card._card_pady = kwargs.pop("pady")
        # Store padx/pady for pack, but return the CTkFrame
        # We need to apply padx/pady when packing
        original_pack = card.pack
        padx = kwargs.get("padx", 0)
        pady = kwargs.get("pady", 0)
        def patched_pack(**pkw):
            pkw.setdefault("padx", padx)
            pkw.setdefault("pady", pady)
            original_pack(**pkw)
        card.pack = patched_pack
        return card
    except Exception:
        return tk.Frame(parent, bg=CARD_BG, relief="solid", borderwidth=1, **kwargs)


def make_button(parent: tk.Widget, text: str, command, accent: bool = False, **kwargs) -> tk.Widget:
    """Create a button — uses CTkButton for modern look."""
    try:
        if accent:
            btn = ctk.CTkButton(parent, text=text, command=command,
                                fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                text_color="white", corner_radius=8,
                                font=FONT_BODY, height=32)
        else:
            btn = ctk.CTkButton(parent, text=text, command=command,
                                fg_color=CARD_BG, hover_color=BUTTON_IDLE_BG,
                                text_color=TEXT_PRIMARY, corner_radius=8,
                                font=FONT_BODY, height=32,
                                border_width=1, border_color=BORDER)
        return btn
    except Exception:
        bg = ACCENT if accent else CARD_BG
        fg = "white" if accent else TEXT_PRIMARY
        active_bg = ACCENT_HOVER if accent else BUTTON_IDLE_BG
        active_fg = "white" if accent else TEXT_PRIMARY
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                         activebackground=active_bg, activeforeground=active_fg,
                         relief="flat", borderwidth=0, font=FONT_BODY,
                         cursor="hand2", padx=14, pady=6, **kwargs)


def make_label(parent: tk.Widget, text: str = "", heading: bool = False, muted: bool = False, **kwargs) -> tk.Widget:
    """Create a label — uses CTkLabel for consistent theming."""
    font = FONT_HEADING if heading else (FONT_SMALL if muted else FONT_BODY)
    fg = TEXT_SECONDARY if muted else TEXT_PRIMARY
    try:
        wraplength = kwargs.pop("wraplength", None)
        justify = kwargs.pop("justify", None)
        anchor = kwargs.pop("anchor", None)
        lbl = ctk.CTkLabel(parent, text=text, font=font, text_color=fg,
                          corner_radius=0)
        if wraplength:
            lbl.configure(wraplength=wraplength)
        if justify:
            lbl.configure(justify=justify)
        if anchor:
            lbl.configure(anchor=anchor)
        return lbl
    except Exception:
        return tk.Label(parent, text=text, bg=BG, fg=fg, font=font, **kwargs)


def make_progress_bar(parent: tk.Widget, value: int, maximum: int = 100, width: int = 200) -> tk.Frame:
    container = tk.Frame(parent, bg=BG)
    bar_bg = tk.Frame(container, bg=BORDER, height=8, width=width)
    bar_bg.pack(side="left", fill="x", expand=True)
    fill_width = max(1, int(width * value / max(maximum, 1)))
    fill = tk.Frame(bar_bg, bg=ACCENT, height=8, width=fill_width)
    fill.place(x=0, y=0)
    return container
