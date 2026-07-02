"""Ollama API client with streaming support and keep-alive."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
import multiprocessing
from collections import OrderedDict
from dataclasses import dataclass

_CACHE_MAX = 128   # max cached responses
_CACHE_TTL = 86400 # seconds (24 h)


OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL_SUGGESTIONS = [
    "qwen2.5:32b-instruct",
    "qwen2.5:7b-instruct",
    "llama3.1:8b",
    "mistral",
]
REQUEST_TIMEOUT = 240


def _find_ollama_binary() -> str:
    """Find the ollama binary, checking common macOS locations."""
    # Check PATH first
    import shutil
    found = shutil.which("ollama")
    if found:
        return found
    # Check common macOS locations
    for path in ["/opt/homebrew/bin/ollama", "/usr/local/bin/ollama", "/usr/bin/ollama"]:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return "ollama"  # fallback to name, will likely fail


@dataclass
class GenerateOptions:
    temperature: float = 0.6
    num_predict: int = 800
    top_p: float = 0.9
    seed: int = -1
    num_thread: int = 0  # 0 = auto (use all CPU cores)
    num_ctx: int = 4096  # context window size


class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self._server_process: subprocess.Popen[str] | None = None
        self._cpu_threads = max(2, multiprocessing.cpu_count() - 1)
        self._models_cache: list[str] | None = None
        self._models_cache_time: float = 0.0
        # Response cache: OrderedDict[key -> (timestamp, response)]
        self._resp_cache: OrderedDict[str, tuple[float, str]] = OrderedDict()
        # Cancellation flag for streaming generation
        self._cancel_event = threading.Event()
        # Track whether WE started the Ollama server (vs external app)
        self._we_started_server = False

    def _cache_key(self, model: str, prompt: str) -> str:
        return hashlib.sha256(f"{model}\x00{prompt}".encode()).hexdigest()

    def _cache_get(self, key: str) -> str | None:
        entry = self._resp_cache.get(key)
        if entry is None:
            return None
        ts, val = entry
        if time.time() - ts > _CACHE_TTL:
            del self._resp_cache[key]
            return None
        # Move to end (LRU)
        self._resp_cache.move_to_end(key)
        return val

    def _cache_put(self, key: str, value: str) -> None:
        self._resp_cache[key] = (time.time(), value)
        self._resp_cache.move_to_end(key)
        while len(self._resp_cache) > _CACHE_MAX:
            self._resp_cache.popitem(last=False)

    def invalidate_cache(self) -> None:
        """Clear the response cache (e.g. after model change)."""
        self._resp_cache.clear()

    def _request(self, path: str, payload: dict | None = None, timeout: int = 10) -> dict:
        url = f"{self.base_url}{path}"
        data = None
        headers = {"Connection": "keep-alive"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method="POST" if payload else "GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.code}: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Сеть недоступна: {exc.reason}") from exc
        except TimeoutError:
            raise RuntimeError("Таймаут запроса к Ollama.") from None

    def ensure_server(self) -> tuple[bool, str]:
        try:
            self._request("/api/tags", timeout=2)
            # Ollama is already running — don't touch it
            self._we_started_server = False
            return True, "Ollama уже запущен."
        except Exception:
            pass

        if self._server_process is None or self._server_process.poll() is not None:
            try:
                ollama_bin = _find_ollama_binary()
                self._server_process = subprocess.Popen(
                    [ollama_bin, "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                self._we_started_server = True
            except FileNotFoundError:
                return False, "Команда `ollama` не найдена. Установите Ollama для оффлайн-модели."
            except Exception as exc:
                return False, f"Не удалось запустить Ollama: {exc}"

        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                self._request("/api/tags", timeout=2)
                return True, "Ollama запущен локально."
            except Exception:
                time.sleep(0.5)

        return False, "Ollama не отвечает. Попробуйте запустить `ollama serve` вручную."

    def is_server_running(self) -> bool:
        """Quick health check — is Ollama responding?"""
        try:
            self._request("/api/tags", timeout=2)
            return True
        except Exception:
            return False

    def restart_server_if_ours(self) -> tuple[bool, str]:
        """Restart Ollama only if WE started it. If another app started it, just wait."""
        if not self._we_started_server:
            # Another app's Ollama — don't touch it, just check if it's back
            if self.is_server_running():
                return True, "Ollama снова доступна."
            return False, "Ollama запущена другим приложением и недоступна. Ожидаю..."
        # We started it — try to restart
        if self._server_process and self._server_process.poll() is not None:
            try:
                ollama_bin = _find_ollama_binary()
                self._server_process = subprocess.Popen(
                    [ollama_bin, "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
            except Exception as exc:
                return False, f"Не удалось перезапустить Ollama: {exc}"
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                self._request("/api/tags", timeout=2)
                return True, "Ollama перезапущена."
            except Exception:
                time.sleep(0.5)
        return False, "Ollama не отвечает после перезапуска."

    def list_models(self) -> list[str]:
        # Return cached models if fresh (5 min TTL)
        if self._models_cache is not None and (time.time() - self._models_cache_time) < 300:
            return self._models_cache
        try:
            data = self._request("/api/tags")
        except Exception:
            return self._models_cache or []
        models = data.get("models", [])
        result = [item.get("name", "") for item in models if item.get("name")]
        self._models_cache = result
        self._models_cache_time = time.time()
        return result

    def invalidate_models_cache(self) -> None:
        """Force refresh of models list on next call."""
        self._models_cache = None
        self._models_cache_time = 0.0

    def generate(self, model: str, prompt: str, options: GenerateOptions | None = None,
                 use_cache: bool = False) -> str:
        """Generate a response. Pass use_cache=True for deterministic/repeated requests."""
        if use_cache:
            key = self._cache_key(model, prompt)
            cached = self._cache_get(key)
            if cached is not None:
                return cached

        opts = options or GenerateOptions()
        gen_options = {
            "temperature": opts.temperature,
            "num_predict": opts.num_predict,
            "top_p": opts.top_p,
            "num_ctx": opts.num_ctx,
        }
        if opts.num_thread > 0:
            gen_options["num_thread"] = opts.num_thread
        else:
            gen_options["num_thread"] = self._cpu_threads
        if opts.seed >= 0:
            gen_options["seed"] = opts.seed
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "10m",
            "options": gen_options,
        }
        data = self._request("/api/generate", payload=payload, timeout=REQUEST_TIMEOUT)
        result = data.get("response", "").strip()
        if use_cache and result:
            self._cache_put(key, result)
        return result

    def cancel_generation(self) -> None:
        """Signal any active streaming generation to stop."""
        self._cancel_event.set()

    def generate_stream(self, model: str, prompt: str, options: GenerateOptions | None = None):
        """Streaming generate — yields text chunks as they arrive."""
        opts = options or GenerateOptions()
        options = {
            "temperature": opts.temperature,
            "num_predict": opts.num_predict,
            "top_p": opts.top_p,
            "num_ctx": opts.num_ctx,
        }
        if opts.num_thread > 0:
            options["num_thread"] = opts.num_thread
        else:
            options["num_thread"] = self._cpu_threads
        if opts.seed >= 0:
            options["seed"] = opts.seed
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "keep_alive": "10m",
            "options": options,
        }
        url = f"{self.base_url}/api/generate"
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json", "Connection": "keep-alive"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                # Set a shorter socket-level timeout for reading lines
                # so we detect a dead connection faster (10s instead of 240s)
                if hasattr(response, 'fp') and hasattr(response.fp, 'raw'):
                    sock = getattr(response.fp.raw, '_sock', None)
                    if sock is not None:
                        sock.settimeout(10)
                for line in response:
                    if self._cancel_event.is_set():
                        return
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line.decode("utf-8"))
                        text = obj.get("response", "")
                        if text:
                            yield text
                        if obj.get("done", False):
                            return
                    except json.JSONDecodeError:
                        continue
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.code}: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Сеть недоступна: {exc.reason}") from exc
        except (TimeoutError, ConnectionRefusedError, OSError) as exc:
            raise RuntimeError(f"Соединение с Ollama потеряно: {exc}") from exc

    def generate_with_context(self, model: str, system_prompt: str, user_message: str, options: GenerateOptions | None = None,
                              use_cache: bool = True) -> str:
        """Generate using a chat-style system + user prompt structure. Cached by default."""
        full_prompt = f"{system_prompt}\n\n---\n\nUser message:\n{user_message}"
        return self.generate(model, full_prompt, options, use_cache=use_cache)

    def is_model_available(self, model: str) -> bool:
        return model in self.list_models()

    def auto_select_model(self) -> str | None:
        """Auto-select best available model based on installed models."""
        models = self.list_models()
        if not models:
            return None
        priority = [
            "qwen2.5:32b-instruct", "qwen2.5:14b-instruct", "qwen2.5:7b-instruct",
            "llama3.1:8b", "llama3:8b", "mistral", "mistral:7b",
            "gemma2:9b", "gemma:7b", "phi3:mini",
        ]
        for preferred in priority:
            for available in models:
                if available == preferred or available.startswith(preferred.split(":")[0]):
                    return available
        return models[0]

    def pull_model(self, model: str) -> tuple[bool, str]:
        """Подкачать модель из сети. Блокирующий вызов, может занять минуты."""
        try:
            ollama_bin = _find_ollama_binary()
            result = subprocess.run(
                [ollama_bin, "pull", model],
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode == 0:
                return True, f"Модель {model} успешно загружена."
            return False, f"Ошибка загрузки: {result.stderr.strip() or result.stdout.strip()}"
        except subprocess.TimeoutExpired:
            return False, f"Таймаут при загрузке {model}. Попробуйте ещё раз."
        except FileNotFoundError:
            return False, "Команда `ollama` не найдена."
        except Exception as exc:
            return False, f"Ошибка: {exc}"
