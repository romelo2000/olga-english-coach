"""Auto-updater: check for new versions, download, and install."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
import urllib.request
import urllib.error
from pathlib import Path

from app_paths import get_app_dir

_logger = logging.getLogger("olga.updater")

# Update server URL — points to GitHub releases version.json
VERSION_CHECK_URL = "https://raw.githubusercontent.com/romelo2000/olga-english-coach/main/version.json"
CURRENT_VERSION = "2.1.1"


def get_current_version() -> str:
    """Get current app version from Info.plist or fallback."""
    try:
        app_dir = get_app_dir()
        plist_path = app_dir / "Contents" / "Info.plist"
        if not plist_path.exists() and app_dir.name.endswith(".app"):
            plist_path = app_dir / "Info.plist"
        if plist_path.exists():
            import plistlib
            with open(plist_path, "rb") as f:
                plist = plistlib.load(f)
                return plist.get("CFBundleShortVersionString", CURRENT_VERSION)
    except Exception:
        pass
    return CURRENT_VERSION


def check_for_update() -> dict | None:
    """Check if a new version is available.
    Returns {"version": "2.2", "download_url": "...", "notes": "..."} or None.
    """
    try:
        req = urllib.request.Request(VERSION_CHECK_URL, method="GET")
        req.add_header("User-Agent", f"OlgaEnglishCoach/{get_current_version()}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            latest = data.get("latest_version", "")
            if latest and latest != get_current_version():
                return {
                    "version": latest,
                    "download_url": data.get("download_url", ""),
                    "notes": data.get("release_notes", ""),
                }
    except Exception as e:
        _logger.debug("Update check failed: %s", e)
    return None


def _compare_versions(v1: str, v2: str) -> int:
    """Compare version strings. Returns 1 if v1 > v2, -1 if v1 < v2, 0 if equal."""
    parts1 = [int(x) for x in v1.split(".")]
    parts2 = [int(x) for x in v2.split(".")]
    for a, b in zip(parts1, parts2):
        if a > b:
            return 1
        if a < b:
            return -1
    if len(parts1) > len(parts2):
        return 1
    if len(parts1) < len(parts2):
        return -1
    return 0


def download_and_install(download_url: str, progress_callback=None) -> tuple[bool, str]:
    """Download update ZIP and install it.
    progress_callback(downloaded, total) for progress.
    Returns (success, message).
    """
    if not download_url:
        return False, "URL загрузки не указан."

    tmp_zip = Path("/tmp/OlgaEnglishCoach-update.zip")
    try:
        req = urllib.request.Request(download_url, method="GET")
        req.add_header("User-Agent", f"OlgaEnglishCoach/{get_current_version()}")
        with urllib.request.urlopen(req, timeout=30) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(tmp_zip, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)
    except Exception as exc:
        return False, f"Ошибка скачивания: {exc}"

    # Find current app path
    app_path = get_app_dir()
    if not app_path.name.endswith(".app"):
        return False, "Не удалось определить путь приложения."

    # Backup current version
    backup_path = app_path.with_suffix(".app.bak")
    try:
        if backup_path.exists():
            shutil.rmtree(backup_path)
        shutil.copytree(app_path, backup_path)
    except Exception:
        pass  # non-critical

    # Unzip new version to temp, then replace
    tmp_extract = Path("/tmp/OlgaEnglishCoach-update")
    try:
        if tmp_extract.exists():
            shutil.rmtree(tmp_extract)
        subprocess.run(
            ["unzip", "-o", str(tmp_zip), "-d", str(tmp_extract)],
            capture_output=True, timeout=60,
        )
        tmp_zip.unlink(missing_ok=True)

        # Find the .app in extracted contents
        new_app = None
        for item in tmp_extract.iterdir():
            if item.name.endswith(".app"):
                new_app = item
                break

        if new_app is None:
            return False, "В архиве не найдено .app приложение."

        # Replace current app
        shutil.rmtree(app_path)
        shutil.move(str(new_app), str(app_path))

        # Cleanup
        shutil.rmtree(tmp_extract, ignore_errors=True)

        return True, "Обновление установлено. Перезапустите приложение."

    except Exception as exc:
        # Restore from backup
        try:
            if backup_path.exists():
                shutil.rmtree(app_path, ignore_errors=True)
                shutil.move(str(backup_path), str(app_path))
        except Exception:
            pass
        return False, f"Ошибка установки: {exc}"


def check_and_prompt(parent_root, auto: bool = False) -> None:
    """Check for update and show dialog if available.
    If auto=True, only shows dialog when update is found (for background check).
    """
    def _check():
        update = check_for_update()
        if update is None:
            if not auto:
                parent_root.after(0, lambda: _show_no_update(parent_root))
            return
        parent_root.after(0, lambda: _show_update_dialog(parent_root, update))

    threading.Thread(target=_check, daemon=True).start()


def _show_no_update(parent) -> None:
    import tkinter as tk
    from tkinter import messagebox
    messagebox.showinfo("Обновление", "У вас установлена последняя версия.")


def _show_update_dialog(parent, update: dict) -> None:
    import tkinter as tk
    import tkinter.ttk as ttk
    from ui_theme import BG, CARD_BG, TEXT_PRIMARY, TEXT_SECONDARY, ACCENT, FONT_HEADING, FONT_BODY, FONT_SMALL, make_button

    win = tk.Toplevel(parent)
    win.title("Доступно обновление")
    win.geometry("460x360")
    win.resizable(False, False)
    win.transient(parent)
    win.grab_set()
    win.configure(bg=BG)

    tk.Label(win, text="🔄", bg=BG, fg=ACCENT, font=("SF Pro Display", 36)).pack(pady=(20, 4))
    tk.Label(win, text=f"Новая версия {update['version']}",
             bg=BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack()
    tk.Label(win, text=update.get("notes", ""),
             bg=BG, fg=TEXT_SECONDARY, font=FONT_BODY,
             justify="center", wraplength=420).pack(pady=(8, 16))

    status_var = tk.StringVar(value="")
    tk.Label(win, textvariable=status_var, bg=BG, fg=TEXT_SECONDARY,
             font=FONT_SMALL).pack(pady=(0, 8))

    progress = tk.IntVar(value=0)
    bar = ttk.Progressbar(win, variable=progress, maximum=100, length=380)
    bar.pack(pady=(0, 16))

    def _download():
        dl_btn.configure(state="disabled")
        later_btn.configure(state="disabled")
        status_var.set("Скачиваю обновление...")

        def _pcb(d, t):
            if t > 0:
                pct = int(d / t * 100)
                progress.set(pct)
                status_var.set(f"Скачиваю... {pct}%")

        def _worker():
            ok, msg = download_and_install(update["download_url"], progress_callback=_pcb)
            if ok:
                status_var.set("✅ Обновление установлено!")
                progress.set(100)
                parent.after(1500, lambda: (win.destroy(), _restart_app(parent)))
            else:
                status_var.set(f"❌ {msg}")
                parent.after(2000, lambda: (
                    dl_btn.configure(state="normal"),
                    later_btn.configure(state="normal"),
                ))

        threading.Thread(target=_worker, daemon=True).start()

    btn_frame = tk.Frame(win, bg=BG)
    btn_frame.pack(fill="x", padx=24, pady=(0, 16))
    dl_btn = make_button(btn_frame, "Обновить", _download, accent=True)
    dl_btn.pack(side="right")
    later_btn = make_button(btn_frame, "Позже", win.destroy)
    later_btn.pack(side="left")


def _restart_app(parent) -> None:
    """Restart the application after update."""
    try:
        parent.destroy()
        app_path = get_app_dir()
        subprocess.Popen(["open", str(app_path)])
    except Exception:
        pass
