"""
Vocabulary Knowledge Graph — build a graph of related words.

The player enters a word. Olga (LLM) suggests related words:
synonyms, antonyms, collocations, word family. The player selects
which to add to their graph. Then Olga generates a quiz from the graph.

Powered by local Ollama model.
"""

import tkinter as tk
from tkinter import ttk
import threading
import json
import time

BG = "#1a1a2e"
CARD_BG = "#16213e"
CHAT_BG = "#0f3460"
TEXT_PRIMARY = "#e0e0e0"
TEXT_SECONDARY = "#a0a0b0"
TEXT_MUTED = "#606080"
ACCENT = "#e94560"
BORDER = "#2a2a4a"
FONT_HEADING = ("SF Pro Display", 16, "bold")
FONT_BODY = ("SF Pro Text", 13)
FONT_SMALL = ("SF Pro Text", 11)
FONT_TITLE = ("SF Pro Display", 22, "bold")

# Colors for different relation types
REL_COLORS = {
    "synonym": "#00ff88",
    "antonym": "#ff4466",
    "collocation": "#44aaff",
    "family": "#ffaa00",
    "related": "#aa88ff",
}


class VocabGraphGame:
    """Vocabulary Knowledge Graph builder with AI-generated related words."""

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
        self.graph: dict[str, list[tuple[str, str]]] = {}  # word -> [(related_word, relation_type)]
        self.current_word = ""
        self.quiz_active = False
        self.quiz_questions: list[tuple[str, str, list[str]]] = []  # (question, answer, options)
        self.quiz_index = 0
        self.quiz_score = 0

        self._build_ui()

    def _build_ui(self) -> None:
        self.win = tk.Toplevel(self.parent)
        self.win.title("🕸 Vocabulary Knowledge Graph")
        self.win.geometry("620x620")
        self.win.resizable(True, True)
        self.win.transient(self.parent)
        self.win.grab_set()
        self.win.configure(bg=BG)

        # Header
        header = tk.Frame(self.win, bg=BG, padx=16, pady=12)
        header.pack(fill="x")
        tk.Label(header, text="🕸 Knowledge Graph", bg=BG, fg=ACCENT, font=FONT_TITLE).pack(side="left")
        tk.Label(header, text="Строй граф связанных слов.\nOlga предложит синонимы, антонимы, collocations.",
                 bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL, justify="left").pack(side="left", padx=(12, 0))

        # Input
        input_frame = tk.Frame(self.win, bg=BG, padx=16, pady=8)
        input_frame.pack(fill="x")
        self.entry = tk.Entry(input_frame, bg=CHAT_BG, fg=TEXT_PRIMARY, font=FONT_BODY,
                              relief="solid", borderwidth=1, width=25)
        self.entry.pack(side="left", padx=(0, 8))
        self.entry.bind("<Return>", lambda e: self._lookup_word())
        self.entry.focus_set()

        tk.Button(input_frame, text="Найти связи", bg=ACCENT, fg="white", font=FONT_BODY,
                  relief="flat", cursor="hand2", command=self._lookup_word).pack(side="left", padx=(0, 4))
        tk.Button(input_frame, text="📋 Квиз из графа", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_SMALL,
                  relief="flat", cursor="hand2", command=self._start_quiz).pack(side="left", padx=(0, 4))
        tk.Button(input_frame, text="Закрыть", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_SMALL,
                  relief="flat", cursor="hand2", command=self.win.destroy).pack(side="right")

        # Suggestions area
        self.suggest_frame = tk.Frame(self.win, bg=BG, padx=16, pady=8)
        self.suggest_frame.pack(fill="x")
        self.suggest_label = tk.Label(self.suggest_frame, text="", bg=BG, fg=TEXT_MUTED, font=FONT_SMALL)
        self.suggest_label.pack(anchor="w")

        # Graph display (scrollable)
        graph_frame = tk.Frame(self.win, bg=BG, padx=16, pady=8)
        graph_frame.pack(fill="both", expand=True)
        tk.Label(graph_frame, text="Твой граф:", bg=BG, fg=TEXT_MUTED, font=FONT_SMALL).pack(anchor="w")

        self.graph_canvas = tk.Canvas(graph_frame, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(graph_frame, orient="vertical", command=self.graph_canvas.yview)
        self.graph_inner = tk.Frame(self.graph_canvas, bg=BG)
        self.graph_inner.bind(
            "<Configure>",
            lambda e: self.graph_canvas.configure(scrollregion=self.graph_canvas.bbox("all")),
        )
        self.graph_canvas.create_window((0, 0), window=self.graph_inner, anchor="nw")
        self.graph_canvas.configure(yscrollcommand=scrollbar.set)
        self.graph_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Quiz area (hidden initially)
        self.quiz_frame = tk.Frame(self.win, bg=CARD_BG, padx=16, pady=12)
        self.quiz_label = tk.Label(self.quiz_frame, text="", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_BODY,
                                   wraplength=560, justify="left")
        self.quiz_label.pack(anchor="w", pady=(0, 8))
        self.quiz_options_frame = tk.Frame(self.quiz_frame, bg=CARD_BG)
        self.quiz_options_frame.pack(fill="x")
        self.quiz_status = tk.Label(self.quiz_frame, text="", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL)
        self.quiz_status.pack(anchor="w", pady=(4, 0))

    def _lookup_word(self) -> None:
        word = self.entry.get().strip().lower()
        if not word:
            return
        if word in self.graph:
            self.suggest_label.configure(text=f"«{word}» уже в графе ({len(self.graph[word])} связей)")
            return

        self.current_word = word
        self.entry.delete(0, "end")
        self.suggest_label.configure(text=f"Olga ищет связи для «{word}»...")

        prompt = f"""You are a vocabulary knowledge graph builder.
For the word "{word}" at {self.level} English level, suggest related words.

Return EXACTLY this JSON format (no other text):
{{
  "synonyms": ["word1", "word2", "word3"],
  "antonyms": ["word1", "word2"],
  "collocations": ["phrase1", "phrase2"],
  "family": ["word1", "word2"],
  "related": ["word1", "word2", "word3"]
}}

Maximum 3-4 words per category. Use common, useful words at {self.level} level."""

        threading.Thread(target=self._fetch_suggestions, args=(word, prompt), daemon=True).start()

    def _fetch_suggestions(self, word: str, prompt: str) -> None:
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
                    response = self._fallback_suggestions(word)
            else:
                response = self._fallback_suggestions(word)

            # Parse JSON from response
            try:
                # Find JSON in response
                start = response.find("{")
                end = response.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(response[start:end])
                else:
                    data = self._fallback_suggestions_dict(word)
            except (json.JSONDecodeError, ValueError):
                data = self._fallback_suggestions_dict(word)

            self.win.after(0, lambda: self._show_suggestions(word, data))
        except Exception as exc:
            self.win.after(0, lambda: self.suggest_label.configure(text=f"Ошибка: {exc}"))

    def _fallback_suggestions(self, word: str) -> str:
        return json.dumps(self._fallback_suggestions_dict(word))

    def _fallback_suggestions_dict(self, word: str) -> dict:
        return {
            "synonyms": [],
            "antonyms": [],
            "collocations": [],
            "family": [],
            "related": [],
        }

    def _show_suggestions(self, word: str, data: dict) -> None:
        self.graph[word] = []
        self.suggest_label.configure(text=f"Связи для «{word}». Нажми чтобы добавить в граф:")

        # Clear old suggestion buttons
        for widget in self.suggest_frame.winfo_children():
            if widget != self.suggest_label:
                widget.destroy()

        for rel_type, words in data.items():
            if not words:
                continue
            row = tk.Frame(self.suggest_frame, bg=BG)
            row.pack(fill="x", pady=2)
            color = REL_COLORS.get(rel_type, TEXT_MUTED)
            tk.Label(row, text=f"  {rel_type}:", bg=BG, fg=color, font=FONT_SMALL, width=14).pack(side="left")
            for w in words[:4]:
                w = w.strip().lower()
                if w and w != word:
                    def _add(word=w, rt=rel_type):
                        self._add_to_graph(word, rt)
                    btn = tk.Button(row, text=f"+ {w}", bg=CARD_BG, fg=color, font=FONT_SMALL,
                                    relief="flat", cursor="hand2", command=_add)
                    btn.pack(side="left", padx=(2, 4))

        self._render_graph()

    def _add_to_graph(self, word: str, rel_type: str) -> None:
        if self.current_word not in self.graph:
            self.graph[self.current_word] = []
        existing = [w for w, _ in self.graph[self.current_word]]
        if word not in existing:
            self.graph[self.current_word].append((word, rel_type))
        # Also add the word as a node if not present
        if word not in self.graph:
            self.graph[word] = []
        self._render_graph()

    def _render_graph(self) -> None:
        for widget in self.graph_inner.winfo_children():
            widget.destroy()

        if not self.graph:
            tk.Label(self.graph_inner, text="Граф пуст. Введи слово выше.", bg=BG, fg=TEXT_MUTED, font=FONT_SMALL).pack(anchor="w")
            return

        for word, connections in self.graph.items():
            row = tk.Frame(self.graph_inner, bg=BG)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=f"📌 {word}", bg=BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(side="left")

            if connections:
                conn_row = tk.Frame(self.graph_inner, bg=BG)
                conn_row.pack(fill="x", padx=(24, 0), pady=(0, 4))
                for related_word, rel_type in connections:
                    color = REL_COLORS.get(rel_type, TEXT_MUTED)
                    tk.Label(conn_row, text=f"  └─ [{rel_type}] {related_word}", bg=BG, fg=color, font=FONT_SMALL).pack(anchor="w")

        self.graph_canvas.update_idletasks()
        self.graph_canvas.yview_moveto(1.0)

    def _start_quiz(self) -> None:
        if len(self.graph) < 3:
            self.suggest_label.configure(text="Нужно минимум 3 слова в графе для квиза.")
            return

        # Build quiz from graph
        self.quiz_questions = []
        words = list(self.graph.keys())
        for word in words:
            connections = self.graph[word]
            if not connections:
                continue
            # Question: "Which word is a synonym of X?"
            for related, rel_type in connections[:2]:
                # Generate options: correct answer + 3 random
                options = [related]
                pool = [w for w in words if w != word and w != related]
                import random
                if len(pool) >= 3:
                    options.extend(random.sample(pool, 3))
                else:
                    options.extend(pool)
                random.shuffle(options)
                self.quiz_questions.append((
                    f"Which word is a {rel_type} of «{word}»?",
                    related,
                    options,
                ))

        if not self.quiz_questions:
            self.suggest_label.configure(text="Недостаточно связей для квиза. Добавь больше слов.")
            return

        self.quiz_index = 0
        self.quiz_score = 0
        self.quiz_active = True
        self.quiz_frame.pack(fill="x", padx=16, pady=(0, 8))
        self._show_quiz_question()

    def _show_quiz_question(self) -> None:
        if self.quiz_index >= len(self.quiz_questions):
            self.quiz_label.configure(text=f"Квиз завершён! Счёт: {self.quiz_score}/{len(self.quiz_questions)}")
            for w in self.quiz_options_frame.winfo_children():
                w.destroy()
            self.quiz_status.configure(text="Молодец!")
            if self.on_finish:
                self.on_finish(self.quiz_score, len(self.quiz_questions))
            return

        question, answer, options = self.quiz_questions[self.quiz_index]
        self.quiz_label.configure(text=f"[{self.quiz_index + 1}/{len(self.quiz_questions)}] {question}")

        for w in self.quiz_options_frame.winfo_children():
            w.destroy()

        for opt in options:
            def _answer(o=opt, a=answer):
                if o == a:
                    self.quiz_score += 1
                    self.quiz_status.configure(text="✅ Верно!", fg="#00ff88")
                else:
                    self.quiz_status.configure(text=f"❌ Правильный ответ: {a}", fg=ACCENT)
                self.quiz_index += 1
                self.win.after(1000, self._show_quiz_question)

            tk.Button(self.quiz_options_frame, text=opt, bg=CHAT_BG, fg=TEXT_PRIMARY, font=FONT_BODY,
                      relief="flat", cursor="hand2", command=_answer).pack(fill="x", pady=2)
