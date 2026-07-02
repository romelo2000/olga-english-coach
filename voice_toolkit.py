"""Voice I/O toolkit: speech recognition via Swift helper, TTS via macOS `say`."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path


class VoiceToolkit:
    def __init__(self, source_dir: Path, data_dir: Path) -> None:
        self.source_dir = source_dir
        self.data_dir = data_dir
        self.swift_source = source_dir / "voice_helper.swift"
        self.binary_path = data_dir / "bin" / "voice_helper"
        self.seed_binary_path = source_dir / "bin" / "voice_helper"
        self._speak_lock = threading.Lock()
        self._say_pids: list[int] = []

    def compile_if_needed(self) -> tuple[bool, str]:
        self.binary_path.parent.mkdir(parents=True, exist_ok=True)

        if self.seed_binary_path.exists() and (
            not self.binary_path.exists()
            or self.binary_path.stat().st_mtime < self.seed_binary_path.stat().st_mtime
        ):
            shutil.copy2(self.seed_binary_path, self.binary_path)

        if not self.swift_source.exists():
            if self.binary_path.exists():
                return True, "Голосовой модуль готов (без пересборки)."
            return False, "voice_helper.swift не найден."

        if self.binary_path.exists() and self.binary_path.stat().st_mtime >= self.swift_source.stat().st_mtime:
            return True, "Голосовой модуль готов."

        env = dict(os.environ)
        env["CLANG_MODULE_CACHE_PATH"] = str(self.data_dir / ".swift-module-cache")

        sdk_candidates = [
            "/Library/Developer/CommandLineTools/SDKs/MacOSX26.sdk",
            "/Library/Developer/CommandLineTools/SDKs/MacOSX15.sdk",
            "/Library/Developer/CommandLineTools/SDKs/MacOSX14.sdk",
        ]

        try:
            for sdk in sdk_candidates:
                sdk_path = Path(sdk)
                if not sdk_path.exists():
                    continue
                try:
                    subprocess.run(
                        [
                            "swiftc",
                            str(self.swift_source),
                            "-sdk",
                            str(sdk_path),
                            "-o",
                            str(self.binary_path),
                            "-framework",
                            "Foundation",
                            "-framework",
                            "AVFoundation",
                            "-framework",
                            "Speech",
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                        env=env,
                        timeout=60,
                    )
                    return True, f"Голосовой модуль собран через {sdk_path.name}."
                except subprocess.CalledProcessError:
                    continue
                except subprocess.TimeoutExpired:
                    continue
            return False, "Не удалось собрать голосовой модуль. Проверьте Command Line Tools."
        except Exception as exc:
            return False, f"Ошибка сборки voice helper: {exc}"

    def transcribe(self, locale: str, seconds: int = 12) -> dict:
        if not self.binary_path.exists():
            return {"transcript": "", "error": "Голосовой модуль не установлен. Перезапустите приложение."}
        try:
            result = subprocess.run(
                [str(self.binary_path), "transcribe", locale, str(seconds)],
                check=True,
                capture_output=True,
                text=True,
                timeout=seconds + 15,
            )
            raw = result.stdout.strip()
            return json.loads(raw) if raw else {}
        except subprocess.TimeoutExpired:
            return {"transcript": "", "error": "timeout"}
        except json.JSONDecodeError:
            return {"transcript": "", "error": "Не удалось разобрать ответ голосового модуля."}
        except Exception as exc:
            return {"transcript": "", "error": str(exc)}

    def speak(self, text: str, language: str, rate: int = 0, voice_name: str = "") -> None:
        with self._speak_lock:
            default_rate = 175
            actual_rate = rate if rate > 0 else default_rate
            # Split long text into chunks to avoid 'say' truncation
            chunks = self._split_text(text, max_chars=800)
            for chunk in chunks:
                # Detect language per chunk for bilingual text (diglot weave)
                is_russian = bool(re.search(r"[А-Яа-яЁё]", chunk))
                if is_russian:
                    voice = "Milena"
                    chunk_rate = rate if rate > 0 else 185
                elif voice_name:
                    voice = voice_name
                    chunk_rate = actual_rate
                else:
                    voice = "Samantha"
                    chunk_rate = actual_rate
                proc = subprocess.Popen(
                    ["say", "-v", voice, "-r", str(chunk_rate), chunk],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._say_pids.append(proc.pid)
                try:
                    proc.wait(timeout=180)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    try:
                        self._say_pids.remove(proc.pid)
                    except ValueError:
                        pass

    _DIALOGUE_LABEL_RE = re.compile(
        r"^\s*(?:"
        r"(?:Speaker|Person|Speaker\s+\w+|Person\s+\w+)\s*[:\-]"
        r"|"
        r"(?:[A-C])\s*[:\-]"  # A: B: C:
        r"|"
        r"(?:[A-Z][a-z]+)\s*[:\-]"  # Anna: Bob:
        r")\s*(.*)",
        re.MULTILINE,
    )

    def speak_dialogue(self, text: str, voice_a: str = "Samantha",
                       voice_b: str = "Daniel", rate: int = 175) -> None:
        """Speak a multi-speaker dialogue using two alternating voices.

        Parses lines like 'A: ...', 'B: ...', 'Speaker A: ...', 'Anna: ...'
        and alternates between voice_a and voice_b.
        Lines without a speaker label are assigned to the last active speaker.
        """
        with self._speak_lock:
            # Split into speaker segments
            segments: list[tuple[str, str]] = []  # (voice, text)
            current_voice = voice_a
            current_lines: list[str] = []

            for line in text.splitlines():
                clean = line.strip()
                if not clean:
                    continue
                m = self._DIALOGUE_LABEL_RE.match(clean)
                if m:
                    # Flush previous segment
                    if current_lines:
                        segments.append((current_voice, " ".join(current_lines)))
                        current_lines = []
                    # Determine which voice to use based on label
                    label = clean.split(":")[0].strip().lower() if ":" in clean else clean.split("-")[0].strip().lower()
                    # A/1/odd → voice_a, B/2/even → voice_b
                    if label in ("b", "c", "2", "speaker b", "person 2", "person b"):
                        current_voice = voice_b
                    else:
                        current_voice = voice_a
                    content = m.group(1).strip()
                    if content:
                        current_lines.append(content)
                else:
                    current_lines.append(clean)

            if current_lines:
                segments.append((current_voice, " ".join(current_lines)))

            # If no speaker labels found, fall back to single-voice speak
            if not segments:
                self.speak(text, "en-US", rate, voice_a)
                return

            for voice, segment_text in segments:
                chunks = self._split_text(segment_text, max_chars=800)
                for chunk in chunks:
                    is_russian = bool(re.search(r"[А-Яа-яЁё]", chunk))
                    if is_russian:
                        v = "Milena"
                        r = rate if rate > 0 else 185
                    else:
                        v = voice
                        r = rate if rate > 0 else 175
                    proc = subprocess.Popen(
                        ["say", "-v", v, "-r", str(r), chunk],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    self._say_pids.append(proc.pid)
                    try:
                        proc.wait(timeout=180)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        try:
                            self._say_pids.remove(proc.pid)
                        except ValueError:
                            pass

    @staticmethod
    def _split_text(text: str, max_chars: int = 800) -> list[str]:
        """Split text into chunks at sentence boundaries for reliable TTS."""
        if len(text) <= max_chars:
            return [text]
        chunks = []
        remaining = text
        while len(remaining) > max_chars:
            # Find last sentence boundary within limit
            best = -1
            for delim in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
                idx = remaining.rfind(delim, 0, max_chars)
                if idx > best:
                    best = idx + len(delim)
            if best <= 0:
                # No sentence boundary — split at last space
                best = remaining.rfind(' ', 0, max_chars)
                if best <= 0:
                    best = max_chars
            chunks.append(remaining[:best].strip())
            remaining = remaining[best:].strip()
        if remaining:
            chunks.append(remaining)
        return chunks

    def stop_speaking(self) -> None:
        import signal
        with self._speak_lock:
            for pid in list(self._say_pids):
                try:
                    os.kill(pid, signal.SIGTERM)
                except Exception:
                    pass
            self._say_pids.clear()
