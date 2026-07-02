"""Ollama installer: auto-detect, download, install, and launch Ollama on macOS."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import threading
import time
import urllib.request
import urllib.error
import logging
from pathlib import Path

_logger = logging.getLogger("olga.installer")

OLLAMA_DOWNLOAD_URL = "https://ollama.com/download/Ollama-darwin.zip"
OLLAMA_APP_PATH = Path("/Applications/Ollama.app")
OLLAMA_BIN_IN_APP = "Ollama.app/Contents/MacOS/ollama"
OLLAMA_BIN_LOCAL = Path.home() / ".ollama" / "bin" / "ollama"
OLLAMA_BIN_INSTALL = "/usr/local/bin/ollama"

INSTALL_LOCK = threading.Lock()


def is_ollama_installed() -> bool:
    """Check if Ollama binary is available anywhere."""
    found = shutil.which("ollama")
    if found:
        return True
    for path in [
        str(OLLAMA_APP_PATH / "Resources" / "ollama"),
        str(OLLAMA_BIN_LOCAL),
        OLLAMA_BIN_INSTALL,
        "/opt/homebrew/bin/ollama",
        "/usr/local/bin/ollama",
    ]:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return True
    # Check inside Ollama.app bundle
    if OLLAMA_APP_PATH.exists():
        # Ollama.app contains the binary in Contents/MacOS/ollama
        bin_path = OLLAMA_APP_PATH / "Contents" / "MacOS" / "Ollama"
        if bin_path.exists():
            return True
    return False


def is_ollama_running() -> bool:
    """Check if Ollama server is responding on localhost:11434."""
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_ollama_binary() -> str | None:
    """Return path to ollama binary, or None if not found."""
    found = shutil.which("ollama")
    if found:
        return found
    for path in [
        str(OLLAMA_APP_PATH / "Contents" / "MacOS" / "Ollama"),
        str(OLLAMA_BIN_LOCAL),
        "/opt/homebrew/bin/ollama",
        "/usr/local/bin/ollama",
    ]:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def download_ollama(progress_callback=None) -> tuple[bool, str]:
    """Download Ollama-darwin.zip and install to /Applications.
    progress_callback(downloaded_bytes, total_bytes) is called periodically.
    Returns (success, message).
    """
    with INSTALL_LOCK:
        if OLLAMA_APP_PATH.exists():
            return True, "Ollama уже установлена."

        tmp_zip = Path("/tmp/Ollama-darwin.zip")
        try:
            req = urllib.request.Request(OLLAMA_DOWNLOAD_URL, method="GET")
            req.add_header("User-Agent", "OlgaEnglishCoach/1.0")
            with urllib.request.urlopen(req, timeout=30) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 65536
                with open(tmp_zip, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total)
            _logger.info("Downloaded Ollama zip: %d bytes", downloaded)
        except urllib.error.URLError as exc:
            return False, f"Не удалось скачать Ollama: {exc}"
        except Exception as exc:
            return False, f"Ошибка при скачивании: {exc}"

        # Unzip to /Applications
        try:
            result = subprocess.run(
                ["unzip", "-o", str(tmp_zip), "-d", "/Applications/"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            tmp_zip.unlink(missing_ok=True)
            if result.returncode != 0:
                return False, f"Не удалось распаковать: {result.stderr.strip()}"
        except Exception as exc:
            tmp_zip.unlink(missing_ok=True)
            return False, f"Ошибка при распаковке: {exc}"

        if not OLLAMA_APP_PATH.exists():
            return False, "Ollama.app не найден после распаковки."

        # Remove quarantine attribute
        try:
            subprocess.run(
                ["xattr", "-cr", str(OLLAMA_APP_PATH)],
                capture_output=True,
                timeout=10,
            )
        except Exception:
            pass

        return True, "Ollama успешно установлена."


def launch_ollama() -> tuple[bool, str]:
    """Launch Ollama server. Returns (success, message)."""
    # If already running, just return
    if is_ollama_running():
        return True, "Ollama уже запущена."

    # Try to find and launch
    binary = get_ollama_binary()
    if binary is None:
        if OLLAMA_APP_PATH.exists():
            # Launch the app (which starts the server)
            try:
                subprocess.Popen(
                    ["open", str(OLLAMA_APP_PATH)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as exc:
                return False, f"Не удалось запустить Ollama.app: {exc}"
        else:
            return False, "Ollama не установлена."
    else:
        try:
            subprocess.Popen(
                [binary, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            return False, f"Не удалось запустить ollama serve: {exc}"

    # Wait for server to be ready
    deadline = time.time() + 20
    while time.time() < deadline:
        if is_ollama_running():
            return True, "Ollama запущена и готова к работе."
        time.sleep(0.5)

    return False, "Ollama запущена, но сервер не отвечает. Попробуйте ещё раз."


def pull_model(model: str, progress_callback=None) -> tuple[bool, str]:
    """Pull a model from Ollama registry. progress_callback(line) for each output line.
    Returns (success, message).
    """
    binary = get_ollama_binary()
    if binary is None:
        return False, "Ollama не установлена."

    try:
        proc = subprocess.Popen(
            [binary, "pull", model],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in proc.stdout:
            line = line.strip()
            if line and progress_callback:
                progress_callback(line)
        proc.wait(timeout=600)
        if proc.returncode == 0:
            return True, f"Модель {model} загружена."
        return False, f"Ошибка загрузки модели."
    except subprocess.TimeoutExpired:
        proc.kill()
        return False, f"Таймаут при загрузке {model}."
    except Exception as exc:
        return False, f"Ошибка: {exc}"


def full_install(progress_callback=None) -> tuple[bool, str]:
    """Full installation flow: download → install → launch.
    progress_callback(stage, detail) where stage is 'download', 'install', 'launch'.
    Returns (success, message).
    """
    if is_ollama_installed() and is_ollama_running():
        return True, "Ollama уже установлена и запущена."

    if not is_ollama_installed():
        if progress_callback:
            progress_callback("download", "Скачиваю Ollama...")
        ok, msg = download_ollama(
            progress_callback=lambda d, t: progress_callback("download_progress", f"{d}/{t}") if progress_callback else None
        )
        if not ok:
            return False, msg
        if progress_callback:
            progress_callback("install", "Ollama установлена.")

    if progress_callback:
        progress_callback("launch", "Запускаю Ollama...")
    ok, msg = launch_ollama()
    if not ok:
        return False, msg
    if progress_callback:
        progress_callback("done", "Ollama готова.")
    return True, msg
