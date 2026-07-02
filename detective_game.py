"""Language Detective Game — solve crimes by understanding English.

The player is a detective investigating crimes. All evidence, witness
testimony, and documents are in English. The player must interrogate NPCs,
collect evidence, and make a final accusation.

Scenarios are AI-generated through Ollama using templates + variations.
The game adapts to the player's level and error patterns.
"""

from __future__ import annotations

import json
import random
import re
import tkinter as tk
from tkinter import messagebox
from datetime import date
from collections import Counter

from ui_theme import (
    BG, CARD_BG, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, ACCENT_HOVER, SUCCESS, WARNING, DANGER, BORDER, CHAT_BG, CHAT_FG,
    FONT_TITLE, FONT_HEADING, FONT_BODY, FONT_SMALL, FONT_MONO,
    make_button, is_dark,
)

# ─── Scenario templates ───

SCENARIO_TEMPLATES = [
    {
        "type": "theft",
        "setting": "a luxury hotel",
        "crime": "a diamond necklace was stolen from room 502",
        "goal": "Find the thief among the suspects.",
        "characters": ["hotel manager", "chambermaid", "guest from room 501", "security guard"],
        "twist": "the security guard has a false alibi",
        "evidence_types": ["a CCTV still photo", "a keycard log", "a handwritten note", "a phone record"],
    },
    {
        "type": "murder",
        "setting": "an old mansion",
        "crime": "Mr. Blackwood was found dead in his study",
        "goal": "Identify the murderer.",
        "characters": ["the butler", "Mr. Blackwood's business partner", "the gardener", "the niece"],
        "twist": "the niece inherits everything",
        "evidence_types": ["a poisoned teacup", "a life insurance policy", "a threatening letter", "muddy footprints"],
    },
    {
        "type": "disappearance",
        "setting": "a small coastal town",
        "crime": "a famous scientist vanished from her lab",
        "goal": "Find out what happened to Dr. Chen.",
        "characters": ["lab assistant", "rival researcher", "local fisherman", "delivery driver"],
        "twist": "the rival researcher was seen near the lab that night",
        "evidence_types": ["an encrypted email", "a ferry ticket", "a lab access log", "a witness statement"],
    },
    {
        "type": "fraud",
        "setting": "a tech startup office",
        "crime": "company funds were embezzled — $2 million missing",
        "goal": "Find the embezzler.",
        "characters": ["the CFO", "the lead developer", "the office manager", "the intern"],
        "twist": "the intern noticed something but was threatened",
        "evidence_types": ["a bank transfer record", "a fake invoice", "a chat log", "a suspicious contract"],
    },
    {
        "type": "vandalism",
        "setting": "an art gallery",
        "crime": "a valuable painting was destroyed overnight",
        "goal": "Find who destroyed the painting.",
        "characters": ["gallery curator", "night guard", "a jealous artist", "cleaning staff"],
        "twist": "the jealous artist has a motive but the night guard was asleep",
        "evidence_types": ["a broken alarm log", "a paint-stained glove", "a social media post", "a witness photo"],
    },
]


def build_case_generation_prompt(template: dict, level: str, error_hints: list[str]) -> str:
    """Build prompt for AI to generate a full detective case."""
    chars = ", ".join(template["characters"])
    evidence = ", ".join(template["evidence_types"])
    hints = f"\nAdaptive: The player struggles with {', '.join(error_hints)}. Include these naturally." if error_hints else ""

    return f"""You are a game designer creating a detective case for an English learning game.

CASE TEMPLATE:
- Type: {template['type']}
- Setting: {template['setting']}
- Crime: {template['crime']}
- Goal: {template['goal']}
- Characters: {chars}
- Twist: {template['twist']}
- Evidence types: {evidence}

Player's English level: {level}{hints}

Generate a JSON object with this exact structure:
{{
  "title": "short catchy title",
  "intro": "2-3 sentence scene description in English (sets the mood)",
  "culprit": "name of the guilty character (must be one of the listed characters)",
  "characters": [
    {{
      "name": "character name",
      "role": "their role",
      "greeting": "what they say when you first approach them (1-2 sentences, English)",
      "secret": "what they're hiding (English, 1 sentence)",
      "is_guilty": true/false (only one is true)
    }}
  ],
  "evidence": [
    {{
      "name": "evidence name",
      "description": "what the evidence shows (English, 1-2 sentences, level {level} vocabulary)",
      "implication": "who it points to and why (English, 1 sentence)"
    }}
  ],
  "solution_explanation": "1-2 sentences explaining why the culprit did it (English)"
}}

IMPORTANT:
- Use vocabulary appropriate for {level} level English learner
- Make the case solvable with the evidence provided
- Each character should have a distinct personality
- The culprit should be discoverable through interrogation + evidence
- Return ONLY the JSON, no other text"""


def parse_case_json(raw: str) -> dict | None:
    """Extract and parse JSON from AI response."""
    # Find JSON in response
    start = raw.find("{")
    if start == -1:
        return None
    # Find matching closing brace
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start:i + 1])
                except Exception:
                    # Try fixing common issues
                    try:
                        cleaned = raw[start:i + 1].replace("\n", " ").replace("'", '"')
                        return json.loads(cleaned)
                    except Exception:
                        return None
    return None


def generate_fallback_case(template: dict, level: str) -> dict:
    """Generate a simple case without AI when Ollama is unavailable."""
    chars = template["characters"]
    culprit_idx = random.randint(0, len(chars) - 1)
    names = ["Alice", "Bob", "Carol", "David", "Eve", "Frank"][:len(chars)]

    characters = []
    for i, role in enumerate(chars):
        characters.append({
            "name": names[i],
            "role": role,
            "greeting": f"Hello, detective. I heard about {template['crime']}. How can I help?",
            "secret": "I was doing my normal routine that night." if i != culprit_idx else f"I did it. {template['twist']}.",
            "is_guilty": i == culprit_idx,
        })

    evidence = []
    for i, etype in enumerate(template["evidence_types"]):
        points_to = names[culprit_idx] if i % 2 == 0 else names[(culprit_idx + 1) % len(names)]
        evidence.append({
            "name": etype,
            "description": f"This {etype} was found at the scene. It looks important.",
            "implication": f"This evidence points to {points_to}.",
        })

    return {
        "title": f"The Case of {template['type'].title()} at {template['setting'].title()}",
        "intro": f"A crime has been committed: {template['crime']}. You are the detective. Can you solve it?",
        "culprit": names[culprit_idx],
        "characters": characters,
        "evidence": evidence,
        "solution_explanation": f"{names[culprit_idx]} committed the crime because {template['twist']}.",
    }


def build_npc_interrogation_prompt(case: dict, character: dict, level: str, player_question: str, asked_questions: list[str]) -> str:
    """Build prompt for NPC response during interrogation."""
    history = ""
    if asked_questions:
        history = "\nPrevious questions from detective:\n" + "\n".join(f"- {q}" for q in asked_questions[-5:])

    is_guilty = character.get("is_guilty", False)
    guilt_hint = "You ARE guilty. Be evasive, nervous, but don't confess directly. Lie about your alibi." if is_guilty else "You are innocent. Be cooperative but you may be confused or scared."

    return f"""You are {character['name']}, the {character['role']} in a detective investigation.
You are being interrogated by the detective (the player).

CASE: {case['title']}
CRIME: {case['intro']}

YOUR SECRET: {character['secret']}
{guilt_hint}

Player's English level: {level}. Keep your vocabulary at that level.
Respond IN CHARACTER as {character['name']}. Stay in first person.
Answer in 1-3 sentences. Be natural and emotional.
If the player asks a unclear or grammatically broken question, act confused — you can say you don't understand.
If the player is polite, be more cooperative. If aggressive, get defensive.
{history}

Detective asks: "{player_question}"

Respond as {character['name']}:"""


def apply_language_fog(text: str, known_words: set[str], fog_ratio: float = 0.15) -> str:
    """Obscure unknown words to simulate incomplete understanding.

    Replaces some longer words with ▓▓▓ if they're not in the known set.
    """
    if fog_ratio <= 0:
        return text

    words = text.split()
    result = []
    for word in words:
        clean = re.sub(r'[^a-zA-Z]', '', word.lower())
        if len(clean) >= 6 and clean not in known_words and random.random() < fog_ratio:
            result.append("▓" * len(clean))
        else:
            result.append(word)
    return " ".join(result)


# Common English words that are always "known" (top 300-ish)
COMMON_WORDS = set("""
the a an and or but if then else when where why how what who whom whose
is are was were be been being have has had do does did will would could
should may might must can shall to of in on at by for with from about into
through during before after above below up down out off over under again
further here there all any both each few more most other some such no not
only own same so than too very just now also very well get got make made
go went gone come came take took see saw know knew think thought say said
want wanted like liked look looked find found tell told ask asked work worked
call called try tried need needed feel felt become became leave left put
mean meant keep kept let begin began seem seemed help helped show showed
run ran move moved live lived play played believe believed bring brought
happen happened write wrote sit sat stand stood lose lost pay paid meet met
include included continue continued set learn learned change changed lead
led understand understood watch watched follow followed stop stopped create
created speak spoke read allow allowed add added grow grew open opened walk
walked win won offer offered remember remembered love loved consider
considered appear appeared buy bought wait waited serve served die died
send sent expect expected build built stay stayed fall fell cut reach
reached remain remained person place time year day week month man woman
boy girl child people way thing part life world home hand eye face night
day morning evening door room house water food book car road name color
sound work money number problem question answer idea fact case point fact
good bad big small new old young long short high low near far right left
yes no hello hi bye please thanks thank sorry excuse
""".split())


class DetectiveGame:
    """Language Detective Game popup window."""

    def __init__(
        self,
        parent: tk.Tk,
        ollama_client=None,
        level: str = "B1",
        error_patterns: dict | None = None,
        completed_cases: list[str] | None = None,
        on_finish=None,
        voice_toolkit=None,
    ) -> None:
        self.parent = parent
        self.ollama = ollama_client
        self.level = level
        self.error_patterns = error_patterns or {}
        self.completed_cases = completed_cases or []
        self.on_finish = on_finish
        self.voice = voice_toolkit

        self.current_case = None
        self.current_suspect = None
        self.asked_questions: list[str] = []
        self.collected_evidence: list[dict] = []
        self.interrogation_log: list[tuple[str, str]] = []
        self.case_score = 0
        self.words_encountered: list[str] = []
        self.waiting_for_npc = False
        self.generating_case = False

        self.win = tk.Toplevel(parent)
        self.win.title("🕵️ Language Detective")
        self.win.configure(bg=BG)
        self.win.geometry("860x720")
        self.win.resizable(True, True)
        self.win.minsize(800, 650)
        self.win.grab_set()
        self.win.protocol("WM_DELETE_WINDOW", self._close)

        self._build_case_selection()
        self.win.focus_force()

    def _get_error_hints(self) -> list[str]:
        if not self.error_patterns:
            return []
        return [k for k, _ in sorted(self.error_patterns.items(), key=lambda x: x[1], reverse=True)[:2]]

    def _has_ollama(self) -> bool:
        return self.ollama is not None and bool(getattr(self.ollama, "model", None))

    # ─── Case selection screen ───

    def _build_case_selection(self) -> None:
        for child in self.win.winfo_children():
            child.destroy()

        header = tk.Frame(self.win, bg=BG, padx=20, pady=12)
        header.pack(fill="x")
        tk.Label(header, text="🕵️ Language Detective", bg=BG, fg=TEXT_PRIMARY, font=FONT_TITLE).pack()
        tk.Label(header, text="Раскрой дело. Английский — твой единственный инструмент.", bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack()

        content = tk.Frame(self.win, bg=BG, padx=20, pady=8)
        content.pack(fill="both", expand=True)

        tk.Label(content, text="Выбери тип дела:", bg=BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w", pady=(0, 8))

        for template in SCENARIO_TEMPLATES:
            card = tk.Frame(content, bg=CARD_BG, padx=16, pady=12)
            card.pack(fill="x", pady=(0, 8))

            top = tk.Frame(card, bg=CARD_BG)
            top.pack(fill="x")
            icon = {"theft": "💎", "murder": "🔪", "disappearance": "🔍", "fraud": "💰", "vandalism": "🎨"}.get(template["type"], "🕵️")
            tk.Label(top, text=f"{icon} {template['type'].title()} — {template['setting']}", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(side="left")
            make_button(top, "Начать расследование", lambda t=template: self._start_case(t), accent=True).pack(side="right")

            tk.Label(card, text=f"Преступление: {template['crime']}", bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL, wraplength=700, justify="left").pack(anchor="w", pady=(4, 2))
            tk.Label(card, text=f"Подозреваемых: {len(template['characters'])} | Улик: {len(template['evidence_types'])}", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL).pack(anchor="w")

        footer = tk.Frame(self.win, bg=BG, padx=20, pady=8)
        footer.pack(fill="x")
        solved = len(self.completed_cases)
        tk.Label(footer, text=f"Раскрыто дел: {solved}", bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack(side="left")
        make_button(footer, "Закрыть", self._close).pack(side="right")

    # ─── Case loading ───

    def _start_case(self, template: dict) -> None:
        for child in self.win.winfo_children():
            child.destroy()

        loading = tk.Frame(self.win, bg=BG, padx=40, pady=40)
        loading.pack(fill="both", expand=True)
        tk.Label(loading, text="🕵️ Генерация дела...", bg=BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack()
        self._loading_label = tk.Label(loading, text="Ольга придумывает кейс для тебя", bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL)
        self._loading_label.pack(pady=(8, 0))

        self.generating_case = True
        import threading
        thread = threading.Thread(target=self._generate_case_worker, args=(template,), daemon=True)
        thread.start()

    def _generate_case_worker(self, template: dict) -> None:
        try:
            hints = self._get_error_hints()
            case = None

            if self._has_ollama():
                prompt = build_case_generation_prompt(template, self.level, hints)
                response = self.ollama.generate(prompt, model=self.ollama.model)
                case = parse_case_json(response)

            if not case:
                case = generate_fallback_case(template, self.level)

            self.current_case = case
            self.asked_questions = []
            self.collected_evidence = []
            self.interrogation_log = []
            self.case_score = 0
            self.words_encountered = []

            self.win.after(0, self._build_investigation_ui)
        except Exception as exc:
            err = str(exc)
            self.win.after(0, lambda: self._generation_error(err))

    def _generation_error(self, error: str) -> None:
        self.generating_case = False
        for child in self.win.winfo_children():
            child.destroy()
        tk.Label(self.win, text=f"Ошибка генерации: {error[:100]}", bg=BG, fg=DANGER, font=FONT_BODY).pack(pady=40)
        make_button(self.win, "← Назад", self._build_case_selection).pack()

    # ─── Investigation UI ───

    def _build_investigation_ui(self) -> None:
        self.generating_case = False
        case = self.current_case
        for child in self.win.winfo_children():
            child.destroy()

        # Header
        header = tk.Frame(self.win, bg=BG, padx=16, pady=10)
        header.pack(fill="x")
        tk.Label(header, text=f"🕵️ {case['title']}", bg=BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(side="left")
        make_button(header, "🎯 Финальный выбор", self._show_accusation_screen, accent=True).pack(side="right")
        make_button(header, "← К делам", self._back_to_cases).pack(side="right", padx=(0, 8))

        # Intro
        intro_frame = tk.Frame(self.win, bg=BG, padx=16)
        intro_frame.pack(fill="x")
        tk.Label(intro_frame, text=case["intro"], bg=BG, fg=TEXT_SECONDARY, font=FONT_BODY, wraplength=750, justify="left").pack(anchor="w")
        tk.Label(intro_frame, text=f"🎯 {case.get('goal', 'Find the culprit.')}", bg=BG, fg=ACCENT, font=FONT_SMALL).pack(anchor="w", pady=(4, 0))

        # Main content area — left: suspects, right: evidence
        main = tk.Frame(self.win, bg=BG, padx=16, pady=8)
        main.pack(fill="both", expand=True)

        # Left panel — suspects
        left = tk.Frame(main, bg=CARD_BG, padx=12, pady=12)
        left.pack(side="left", fill="both", expand=True)
        tk.Label(left, text="👤 Подозреваемые", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w", pady=(0, 8))
        for char in case["characters"]:
            btn = make_button(left, f"{char['name']} — {char['role']}", lambda c=char: self._interrogate(c))
            btn.pack(fill="x", pady=(0, 4))

        # Right panel — evidence
        right = tk.Frame(main, bg=CARD_BG, padx=12, pady=12)
        right.pack(side="right", fill="both", expand=True, padx=(8, 0))
        tk.Label(right, text="🔍 Улики", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w", pady=(0, 8))
        for ev in case["evidence"]:
            make_button(right, f"📋 {ev['name']}", lambda e=ev: self._examine_evidence(e)).pack(fill="x", pady=(0, 4))

        # Input — packed FIRST with side=bottom so it's always visible
        input_frame = tk.Frame(self.win, bg=BG, padx=16, pady=8)
        input_frame.pack(side="bottom", fill="x")
        self.input_entry = tk.Entry(input_frame, bg=CHAT_BG, fg=CHAT_FG, relief="solid", borderwidth=1, font=FONT_BODY)
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.input_entry.bind("<Return>", self._on_ask)
        self.input_entry.config(state="disabled")
        make_button(input_frame, "Спросить", self._on_ask_click).pack(side="left", padx=(0, 4))
        make_button(input_frame, "🔊 Голос", self._on_voice_input).pack(side="left", padx=(0, 4))
        make_button(input_frame, "← К подозреваемым", self._back_to_suspects).pack(side="left")

        self.status_label = tk.Label(input_frame, text="", bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL)
        self.status_label.pack(side="left", padx=(8, 0))

        # Dialogue area — packed after input, fills remaining space
        dlg_frame = tk.Frame(self.win, bg=BG, padx=16, pady=8)
        dlg_frame.pack(fill="both", expand=True)

        self.dialogue_text = tk.Text(dlg_frame, wrap="word", bg=CHAT_BG, fg=CHAT_FG, font=FONT_BODY, relief="flat", height=8, padx=12, pady=12)
        self.dialogue_text.pack(fill="both", expand=True)
        self.dialogue_text.configure(state="disabled")
        self.dialogue_text.tag_config("npc", foreground="#4a9eff" if is_dark() else "#0066cc", font=("SF Pro Display", 12, "bold"))
        self.dialogue_text.tag_config("detective", foreground="#50c878" if is_dark() else "#008844", font=("SF Pro Display", 12, "bold"))
        self.dialogue_text.tag_config("evidence", foreground="#d4a017" if is_dark() else "#8a6800", font=FONT_BODY)
        self.dialogue_text.tag_config("system", foreground=TEXT_MUTED, font=FONT_SMALL)

        self._append_dialogue("system", "💡 Допроси подозреваемых и изучи улики. Когда будешь готов — нажми «Финальный выбор».\n\n")

    def _append_dialogue(self, tag: str, text: str) -> None:
        self.dialogue_text.configure(state="normal")
        self.dialogue_text.insert("end", text, tag)
        self.dialogue_text.configure(state="disabled")
        self.dialogue_text.see("end")

    # ─── Interrogation ───

    def _interrogate(self, character: dict) -> None:
        self.current_suspect = character
        self.asked_questions = []
        self.input_entry.config(state="normal")
        self.input_entry.focus_set()
        self._append_dialogue("system", f"\n{'─' * 40}\n")
        self._append_dialogue("npc", f"{character['name']} ({character['role']}):\n")
        greeting = apply_language_fog(character["greeting"], COMMON_WORDS, 0.1 if self.level in ("A1", "A2") else 0.05)
        self._append_dialogue("npc", f"  \"{greeting}\"\n\n")
        self.status_label.config(text=f"Допрос: {character['name']}")

    def _on_ask(self, event=None) -> None:
        self._on_ask_click()

    def _on_ask_click(self) -> None:
        if self.waiting_for_npc or not self.current_suspect:
            return
        question = self.input_entry.get().strip()
        if not question:
            return
        self.input_entry.delete(0, "end")
        self._append_dialogue("detective", f"Детектив: {question}\n")
        self.asked_questions.append(question)
        self.words_encountered.extend(question.lower().split())
        self._send_to_npc(question)

    def _on_voice_input(self) -> None:
        if not self.voice:
            self.status_label.config(text="❌ Голосовой модуль недоступен")
            return
        self.status_label.config(text="🎤 Запись...")
        try:
            result = self.voice.transcribe("en-US", seconds=8)
            text = result.get("transcript", "") if isinstance(result, dict) else ""
            if text:
                self.input_entry.delete(0, "end")
                self.input_entry.insert(0, text)
                self.status_label.config(text="✅ Распознано")
            else:
                self.status_label.config(text="❌ Не расслышал")
        except Exception:
            self.status_label.config(text="❌ Ошибка записи")

    def _send_to_npc(self, question: str) -> None:
        self.waiting_for_npc = True
        self.input_entry.config(state="disabled")
        self.status_label.config(text=f"{self.current_suspect['name']} думает...")

        import threading
        thread = threading.Thread(target=self._npc_response_worker, args=(question,), daemon=True)
        thread.start()

    def _npc_response_worker(self, question: str) -> None:
        try:
            if self._has_ollama():
                prompt = build_npc_interrogation_prompt(
                    self.current_case, self.current_suspect, self.level, question, self.asked_questions,
                )
                response = self.ollama.generate(prompt, model=self.ollama.model)
            else:
                response = self._fallback_npc_response(question)

            self.win.after(0, lambda: self._handle_npc_response(response))
        except Exception as exc:
            err = str(exc)
            self.win.after(0, lambda: self._handle_npc_response(f"I... I don't know what to say. (Error: {err[:50]})"))

    def _fallback_npc_response(self, question: str) -> str:
        char = self.current_suspect
        q_lower = question.lower()
        is_guilty = char.get("is_guilty", False)

        if any(kw in q_lower for kw in ["where", "last night", "alibi", "were you"]):
            if is_guilty:
                return "I was... I was at home. Yes, at home all night. I didn't go anywhere."
            return f"I was doing my job as usual. Nothing special happened."
        elif any(kw in q_lower for kw in ["did you", "you steal", "you kill", "you take", "guilty"]):
            if is_guilty:
                return "What?! How dare you! I would never do such a thing!"
            return "No! I'm innocent. I have nothing to do with this."
        elif any(kw in q_lower for kw in ["see", "saw", "witness", "notice", "hear", "heard"]):
            return "I saw... well, I'm not sure. It was dark. Maybe someone was near the scene, but I can't be certain."
        elif any(kw in q_lower for kw in ["why", "motive", "reason"]):
            if is_guilty:
                return "I have no reason to do anything wrong. I'm a good person."
            return "I can't think of anyone who would want to do this. It's terrible."
        else:
            if is_guilty:
                return "I... I don't understand what you're asking. Can we move on?"
            return "I'm not sure how to answer that. Could you ask differently?"

    def _handle_npc_response(self, response: str) -> None:
        self.waiting_for_npc = False
        self.input_entry.config(state="normal")
        self.status_label.config(text=f"Допрос: {self.current_suspect['name']}")

        fogged = apply_language_fog(response, COMMON_WORDS, 0.1 if self.level in ("A1", "A2") else 0.05)
        self._append_dialogue("npc", f"  \"{fogged}\"\n\n")
        self.interrogation_log.append((self.current_suspect["name"], response))
        self.words_encountered.extend(response.lower().split())
        self.input_entry.focus_set()

    def _back_to_suspects(self) -> None:
        self.current_suspect = None
        self.input_entry.config(state="disabled")
        self.status_label.config(text="Выбери подозреваемого для допроса")

    # ─── Evidence examination ───

    def _examine_evidence(self, evidence: dict) -> None:
        if evidence not in self.collected_evidence:
            self.collected_evidence.append(evidence)
            self.case_score += 5

        self._append_dialogue("system", f"\n{'─' * 40}\n")
        self._append_dialogue("evidence", f"📋 {evidence['name']}\n")
        desc = apply_language_fog(evidence["description"], COMMON_WORDS, 0.1 if self.level in ("A1", "A2") else 0.05)
        self._append_dialogue("evidence", f"  {desc}\n")
        impl = apply_language_fog(evidence["implication"], COMMON_WORDS, 0.1 if self.level in ("A1", "A2") else 0.05)
        self._append_dialogue("evidence", f"  👉 {impl}\n\n")
        self.status_label.config(text=f"Изучено улик: {len(self.collected_evidence)}")

    # ─── Final accusation ───

    def _show_accusation_screen(self) -> None:
        case = self.current_case
        for child in self.win.winfo_children():
            child.destroy()

        header = tk.Frame(self.win, bg=BG, padx=20, pady=12)
        header.pack(fill="x")
        tk.Label(header, text="🎯 Финальный выбор", bg=BG, fg=TEXT_PRIMARY, font=FONT_TITLE).pack()
        tk.Label(header, text="Кто виновен? Выбери осторожно — ошибка значит невиновный пострадает.", bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack()

        content = tk.Frame(self.win, bg=BG, padx=20, pady=12)
        content.pack(fill="both", expand=True)

        # Show collected evidence summary
        if self.collected_evidence:
            tk.Label(content, text="Собранные улики:", bg=BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w", pady=(0, 4))
            for ev in self.collected_evidence:
                tk.Label(content, text=f"  📋 {ev['name']}: {ev['implication']}", bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL, wraplength=700, justify="left").pack(anchor="w")
            tk.Label(content, text="", bg=BG).pack()

        tk.Label(content, text="Кто совершил преступление?", bg=BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w", pady=(8, 8))

        for char in case["characters"]:
            make_button(content, f"👉 {char['name']} — {char['role']}", lambda c=char: self._make_accusation(c), accent=True).pack(fill="x", pady=(0, 6))

        footer = tk.Frame(self.win, bg=BG, padx=20, pady=8)
        footer.pack(fill="x")
        make_button(footer, "← Назад к расследованию", self._build_investigation_ui).pack(side="left")

    def _make_accusation(self, accused: dict) -> None:
        case = self.current_case
        correct = accused.get("is_guilty", False)
        culprit_name = case.get("culprit", "")

        # Score calculation
        base_score = 50 if correct else 0
        evidence_bonus = len(self.collected_evidence) * 5
        questions_bonus = min(20, len(self.asked_questions) * 2)
        total_score = base_score + evidence_bonus + questions_bonus

        for child in self.win.winfo_children():
            child.destroy()

        result = tk.Frame(self.win, bg=BG, padx=20, pady=20)
        result.pack(fill="both", expand=True)

        if correct:
            tk.Label(result, text="🎉 ДЕЛО РАСКРЫТО!", bg=BG, fg=SUCCESS, font=FONT_TITLE).pack()
            tk.Label(result, text=f"Ты правильно обвинил(а) {accused['name']}.", bg=BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(pady=(8, 0))
        else:
            tk.Label(result, text="❌ НЕВЕРНО!", bg=BG, fg=DANGER, font=FONT_TITLE).pack()
            tk.Label(result, text=f"Невиновный пострадал. Виновный: {culprit_name}.", bg=BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(pady=(8, 0))

        tk.Label(result, text=f"\nОчки дела: {total_score}", bg=BG, fg=ACCENT, font=FONT_HEADING).pack()

        # Solution explanation
        tk.Label(result, text="\n📖 Разъяснение дела:", bg=BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w", pady=(8, 4))
        sol = case.get("solution_explanation", "")
        tk.Label(result, text=sol, bg=BG, fg=TEXT_SECONDARY, font=FONT_BODY, wraplength=700, justify="left").pack(anchor="w")

        # Stats
        tk.Label(result, text=f"\n📊 Статистика:", bg=BG, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w", pady=(8, 4))
        tk.Label(result, text=f"  Вопросов задано: {len(self.asked_questions)}", bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack(anchor="w")
        tk.Label(result, text=f"  Улик изучено: {len(self.collected_evidence)}", bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack(anchor="w")
        tk.Label(result, text=f"  Слов использовано: {len(self.words_encountered)}", bg=BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack(anchor="w")

        # Callback
        if self.on_finish:
            self.on_finish(case.get("title", "Unknown Case"), correct, total_score, self.words_encountered)

        # Buttons
        btn_frame = tk.Frame(self.win, bg=BG, padx=20, pady=12)
        btn_frame.pack(fill="x")
        make_button(btn_frame, "🕵️ Новое дело", self._build_case_selection, accent=True).pack(side="left", padx=(0, 8))
        make_button(btn_frame, "Закрыть", self._close).pack(side="left")

    def _back_to_cases(self) -> None:
        self.current_case = None
        self.current_suspect = None
        self._build_case_selection()

    def _close(self) -> None:
        self.win.grab_release()
        self.win.destroy()
