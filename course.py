"""Adaptive course management with SRS integration.

Implements:
- CEFR-structured learning path with mastery tracking
- Spaced repetition (SM-2) for vocabulary
- Skill tracking: grammar, vocabulary, speaking, listening, writing
- Interleaving: mixing grammar, vocab, and practice for better retention
- Adaptive focus: weakest skill gets priority
- Streak tracking, daily goals, session logging
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from curriculum import (
    CEFR_LEVELS,
    GRAMMAR_CURRICULUM,
    GrammarPoint,
    VocabCard,
    all_vocab_cards_for_level,
    grammar_for_level,
    grammar_point_by_id,
    next_level,
)
from srs import SRSManager, SRSCard, quality_from_rating, review_card


SKILLS = ["grammar", "vocabulary", "speaking", "listening", "writing"]

SKILL_RU = {
    "grammar": "Грамматика",
    "vocabulary": "Словарный запас",
    "speaking": "Говорение",
    "listening": "Аудирование",
    "writing": "Письмо",
}

PRACTICE_TYPES = [
    "dialogue",
    "grammar_exercise",
    "vocab_review",
    "writing_task",
    "speaking_drill",
    "listening_task",
    "roleplay",
    "free_practice",
    "reading_task",
    "dialogue_listening",
    "dictation",
    "shadowing",
    "minimal_pairs",
    "collocation_drill",
    "error_correction",
    "sentence_transformation",
    "phrasal_verbs",
    "dictogloss",
    "input_flood",
    "pushed_output",
    "lexical_chunks",
    "task_repetition",
]

PRACTICE_RU = {
    "dialogue": "Диалог",
    "grammar_exercise": "Упражнение по грамматике",
    "vocab_review": "Повторение слов",
    "writing_task": "Письменное задание",
    "speaking_drill": "Спикинг-дрилл",
    "listening_task": "Аудирование",
    "roleplay": "Ролевая игра",
    "free_practice": "Свободная практика",
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

PRACTICE_SKILL_BUMPS: dict[str, dict[str, int]] = {
    "listening_task": {"listening": 5},
    "reading_task": {"vocabulary": 3, "grammar": 2},
    "dialogue_listening": {"listening": 5, "speaking": 2},
    "dictation": {"listening": 3, "grammar": 2},
    "shadowing": {"speaking": 5, "listening": 2},
    "minimal_pairs": {"speaking": 4, "listening": 3},
    "collocation_drill": {"vocabulary": 4, "grammar": 1},
    "error_correction": {"grammar": 4, "writing": 2},
    "sentence_transformation": {"grammar": 5, "writing": 2},
    "phrasal_verbs": {"vocabulary": 4, "speaking": 1},
    "dictogloss": {"listening": 4, "grammar": 3, "writing": 3},
    "input_flood": {"grammar": 5, "vocabulary": 3},
    "pushed_output": {"speaking": 4, "grammar": 3, "writing": 3},
    "lexical_chunks": {"vocabulary": 5, "speaking": 2},
    "task_repetition": {"speaking": 3, "grammar": 2, "vocabulary": 2},
}


@dataclass
class SessionRecord:
    date: str
    practice_type: str
    mode: str
    voice: bool
    user_words: int
    assistant_words: int
    skill_focus: str
    grammar_point: str = ""
    vocab_theme: str = ""
    duration_seconds: int = 0
    error_count: int = 0
    corrected: bool = False


class CourseManager:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.state_path = data_dir / "course_state.json"
        self.srs_path = data_dir / "srs_state.json"
        self.error_journal_path = data_dir / "error_journal.json"
        self.state = self._load_state()
        self.srs = self._load_srs()
        self._seed_vocab_for_level()

    def _default_state(self) -> dict:
        today = date.today().isoformat()
        return {
            "level": "B1",
            "target_level": "B2",
            "goal_days": 30,
            "start_date": today,
            "daily_goal_minutes": 20,
            "completed_sessions": 0,
            "total_minutes": 0,
            "active_days": [],
            "daily_activity": {},
            "daily_minutes": {},
            "skill_scores": {skill: 20 for skill in SKILLS},
            "grammar_completed": [],
            "grammar_current": "",
            "vocab_themes_completed": [],
            "vocab_theme_current": "",
            "sessions": [],
            "voice_sessions": 0,
            "speaking_reviews": [],
            "error_patterns": {},
            "last_practice_type": "",
            "streak_frozen": False,
            "best_streak": 0,
            "earned_badges": [],
            "level_history": ["B1"],
            "total_xp": 0,
            "weekly_xp": {},
            "xp_history": [],
            "game_scores": [],
            "survival_completed_scenes": [],
            "survival_history": [],
            "detective_solved_cases": [],
            "detective_history": [],
            "time_loop_broken": [],
            "time_loop_history": [],
            "student_profile": {
                "name": "",
                "profession": "",
                "hobbies": [],
                "goals": "",
                "notes": [],
            },
            "session_summaries": [],
        }

    def _load_state(self) -> dict:
        if not self.state_path.exists():
            state = self._default_state()
            self._save_state(state)
            return state
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            state = self._default_state()
        merged = self._default_state()
        for key, val in state.items():
            if val is not None:
                merged[key] = val
        for skill in SKILLS:
            if skill not in merged["skill_scores"]:
                merged["skill_scores"][skill] = 20
        merged["skill_scores"].update({k: v for k, v in state.get("skill_scores", {}).items() if v is not None})
        merged["sessions"] = state.get("sessions", []) or []
        merged["sessions"] = merged["sessions"][-100:]
        merged["daily_activity"] = state.get("daily_activity", {}) or {}
        merged["daily_minutes"] = state.get("daily_minutes", {}) or {}
        merged["speaking_reviews"] = state.get("speaking_reviews", []) or []
        merged["speaking_reviews"] = merged["speaking_reviews"][-50:]
        merged["error_patterns"] = state.get("error_patterns", {}) or {}
        merged["grammar_completed"] = state.get("grammar_completed", []) or []
        merged["vocab_themes_completed"] = state.get("vocab_themes_completed", []) or []
        merged["earned_badges"] = state.get("earned_badges", []) or []
        merged["active_days"] = state.get("active_days", []) or []
        merged["total_xp"] = state.get("total_xp", 0) or 0
        merged["weekly_xp"] = state.get("weekly_xp", {}) or {}
        merged["xp_history"] = state.get("xp_history", []) or []
        merged["placement_done"] = state.get("placement_done", False)
        merged["onboarding_done"] = state.get("onboarding_done", False)
        merged["daily_challenges_completed"] = state.get("daily_challenges_completed", []) or []
        merged["claimed_milestones"] = state.get("claimed_milestones", []) or []
        return merged

    def _save_state(self, state: dict | None = None) -> None:
        data = state or self.state
        self.state_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_srs(self) -> SRSManager:
        if not self.srs_path.exists():
            return SRSManager()
        try:
            data = json.loads(self.srs_path.read_text(encoding="utf-8"))
            return SRSManager.from_dict(data)
        except Exception:
            return SRSManager()

    def _save_srs(self) -> None:
        self.srs_path.write_text(
            json.dumps(self.srs.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _seed_vocab_for_level(self) -> None:
        try:
            level = self.state["level"]
            cards = all_vocab_cards_for_level(level)
            new_count = 0
            max_new_per_seed = 100
            for card in cards:
                card_id = f"vocab:{level}:{card.word}"
                if card_id not in self.srs.cards:
                    self.srs.add_card(SRSCard(
                        card_id=card_id,
                        front=card.word,
                        back=card.translation,
                        example=card.example,
                        ipa=card.ipa,
                        collocations=", ".join(card.collocations) if card.collocations else "",
                    ))
                    if card.word_family:
                        self.srs.cards[card_id].collocations += f" | Word family: {', '.join(card.word_family)}"
                    new_count += 1
                    if new_count >= max_new_per_seed:
                        break
            if new_count > 0:
                self._save_srs()
        except Exception as exc:
            from app_logger import log_exception
            log_exception(exc, "_seed_vocab_for_level")

    @property
    def level(self) -> str:
        return self.state["level"]

    @property
    def target_level(self) -> str:
        return self.state["target_level"]

    MIN_LEVEL = "B1"

    def set_level(self, level: str) -> None:
        if level not in CEFR_LEVELS:
            return
        level_order = CEFR_LEVELS.index(level)
        min_order = CEFR_LEVELS.index(self.MIN_LEVEL)
        if level_order < min_order:
            return
        if level != self.state.get("level"):
            history = self.state.get("level_history", [])
            if not history or history[-1] != level:
                history.append(level)
            self.state["level_history"] = history[-10:]
        self.state["level"] = level
        target = next_level(level)
        if target:
            self.state["target_level"] = target
        self._seed_vocab_for_level()
        self._save_state()

    def set_goal(self, days: int) -> None:
        today = date.today().isoformat()
        self.state["goal_days"] = days
        self.state["start_date"] = today
        self.state["completed_sessions"] = 0
        self.state["total_minutes"] = 0
        self.state["active_days"] = []
        self.state["daily_activity"] = {}
        self.state["daily_minutes"] = {}
        self.state["sessions"] = []
        self.state["voice_sessions"] = 0
        self.state["speaking_reviews"] = []
        self.state["grammar_completed"] = []
        self.state["vocab_themes_completed"] = []
        self.state["error_patterns"] = {}
        self._save_state()

    def set_daily_goal(self, minutes: int) -> None:
        self.state["daily_goal_minutes"] = minutes
        self._save_state()

    def weakest_skill(self) -> str:
        return min(self.state["skill_scores"], key=self.state["skill_scores"].get)

    def strongest_skill(self) -> str:
        return max(self.state["skill_scores"], key=self.state["skill_scores"].get)

    def skill_score(self, skill: str) -> int:
        return int(self.state["skill_scores"].get(skill, 0))

    def _bump_skill(self, skill: str, amount: int) -> None:
        current = self.state["skill_scores"].get(skill, 0)
        self.state["skill_scores"][skill] = max(0, min(100, current + amount))

    def record_session(
        self,
        practice_type: str,
        mode: str,
        user_text: str,
        assistant_text: str,
        used_voice: bool,
        duration_seconds: int = 0,
        speaking_review: dict | None = None,
        error_count: int = 0,
        grammar_point_id: str = "",
        vocab_theme: str = "",
    ) -> None:
        today = date.today().isoformat()
        if today not in self.state["active_days"]:
            self.state["active_days"].append(today)

        self.state["completed_sessions"] += 1
        self.state["total_minutes"] += max(1, duration_seconds // 60)
        self.state["last_practice_type"] = practice_type

        combined = f"{user_text} {assistant_text}".lower()
        user_words = len(user_text.split())
        assistant_words = len(assistant_text.split())

        if used_voice or practice_type in ("speaking_drill", "dialogue", "roleplay"):
            self._bump_skill("speaking", 5)
            self._bump_skill("listening", 2)
        elif user_words >= 10:
            self._bump_skill("speaking", 2)

        if practice_type == "grammar_exercise" or any(
            token in combined for token in ["grammar", "tense", "article", "preposition", "ошибка", "правило", "conditional", "passive"]
        ):
            self._bump_skill("grammar", 5)
        elif mode in ("Проверка", "Объяснение", "Упражнение"):
            self._bump_skill("grammar", 3)
        else:
            self._bump_skill("grammar", 1)

        if practice_type == "vocab_review" or any(
            token in combined for token in ["word", "phrase", "meaning", "translate", "слово", "фраз", "vocab"]
        ):
            self._bump_skill("vocabulary", 5)
        elif practice_type in ("grammar_exercise", "Объяснение"):
            self._bump_skill("vocabulary", 2)
        else:
            self._bump_skill("vocabulary", 1)

        if practice_type == "writing_task" or user_words >= 30:
            self._bump_skill("writing", 5)
        elif user_words >= 10:
            self._bump_skill("writing", 2)

        bumps = PRACTICE_SKILL_BUMPS.get(practice_type, {})
        for skill, amount in bumps.items():
            self._bump_skill(skill, amount)

        if used_voice:
            self.state["voice_sessions"] += 1

        if grammar_point_id and grammar_point_id not in self.state["grammar_completed"]:
            if error_count <= 1:
                self.state["grammar_completed"].append(grammar_point_id)

        if vocab_theme and vocab_theme not in self.state["vocab_themes_completed"]:
            self.state["vocab_themes_completed"].append(vocab_theme)

        if error_count > 0:
            patterns = self.state.get("error_patterns", {})
            error_keys = [
                ("tense", ["tense", "время", "past", "present", "future", "perfect", "continuous"]),
                ("article", ["article", "артикл", "a/an", "the ", "определённ"]),
                ("preposition", ["preposition", "предлог", "in/on/at", "to/from"]),
                ("word_order", ["word order", "порядок слов", "word order"]),
                ("spelling", ["spelling", "орфограф", "опечатк"]),
                ("pronunciation", ["pronunciation", "произношен", "sound", "звук"]),
                ("collocation", ["collocation", "словосочетан", "combination"]),
                ("plural", ["plural", "множествен", "singular", "единствен"]),
            ]
            for key, keywords in error_keys:
                if any(kw in combined for kw in keywords):
                    patterns[key] = patterns.get(key, 0) + 1
            self.state["error_patterns"] = patterns

            self._log_error_journal(practice_type, error_count, assistant_text, error_keys, combined)

        session_entry = {
            "date": today,
            "practice_type": practice_type,
            "mode": mode,
            "voice": used_voice,
            "user_words": user_words,
            "assistant_words": assistant_words,
            "skill_focus": self.weakest_skill(),
            "duration_seconds": duration_seconds,
            "grammar_point": grammar_point_id,
            "vocab_theme": vocab_theme,
            "error_count": error_count,
        }
        if speaking_review:
            session_entry["speaking_review"] = {
                "pronunciation": speaking_review.get("pronunciation_score", 0),
                "tempo": speaking_review.get("tempo_score", 0),
                "confidence": speaking_review.get("confidence_score", 0),
            }
        self.state["sessions"] = (self.state.get("sessions", []) + [session_entry])[-100:]

        daily_activity = dict(self.state.get("daily_activity", {}))
        daily_activity[today] = daily_activity.get(today, 0) + 1
        self.state["daily_activity"] = daily_activity

        daily_minutes = dict(self.state.get("daily_minutes", {}))
        daily_minutes[today] = daily_minutes.get(today, 0) + max(1, duration_seconds // 60)
        self.state["daily_minutes"] = daily_minutes

        if speaking_review:
            review_entry = dict(speaking_review)
            review_entry["date"] = today
            self.state["speaking_reviews"] = (self.state.get("speaking_reviews", []) + [review_entry])[-50:]

        self._save_state()
        self.award_xp(practice_type, duration_seconds=duration_seconds, used_voice=used_voice)

    def review_vocab_card(self, card_id: str, rating: str) -> SRSCard | None:
        quality = quality_from_rating(rating)
        card = self.srs.review(card_id, quality)
        if card:
            if quality >= 3:
                self._bump_skill("vocabulary", 2)
            self._save_srs()
            self._save_state()
        return card

    def streak_days(self) -> int:
        active = sorted(self.state.get("active_days", []))
        if not active:
            return 0
        active_set = set(active)
        today = date.today()
        yesterday = today - timedelta(days=1)
        today_iso = today.isoformat()
        yesterday_iso = yesterday.isoformat()

        if today_iso in active_set:
            cursor = today
        elif yesterday_iso in active_set and self.state.get("streak_frozen", False):
            cursor = yesterday
        elif yesterday_iso in active_set:
            cursor = yesterday
        else:
            return 0

        streak = 0
        while cursor.isoformat() in active_set:
            streak += 1
            cursor = cursor - timedelta(days=1)
        # Update best_streak record
        if streak > self.state.get("best_streak", 0):
            self.state["best_streak"] = streak
        return streak

    def best_streak_days(self) -> int:
        """Return the all-time best streak."""
        return self.state.get("best_streak", 0)

    def use_streak_freeze(self) -> bool:
        """Use streak freeze if available. Returns True if freeze was used."""
        if self.state.get("streak_frozen", False):
            return False
        self.state["streak_frozen"] = True
        self._save_state()
        return True

    def check_and_apply_freeze(self) -> None:
        """Check if yesterday was missed and apply freeze if available."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        today = date.today().isoformat()
        active = set(self.state.get("active_days", []))
        if yesterday not in active and today not in active:
            if self.state.get("streak_frozen", False):
                self.state["streak_frozen"] = False
                active_list = list(self.state.get("active_days", []))
                active_list.append(yesterday)
                self.state["active_days"] = active_list
                self._save_state()

    def days_elapsed(self) -> int:
        try:
            started = datetime.fromisoformat(self.state["start_date"]).date()
        except Exception:
            started = date.today()
        return max(1, (date.today() - started).days + 1)

    def days_left(self) -> int:
        return max(0, int(self.state["goal_days"]) - self.days_elapsed())

    def completion_percent(self) -> int:
        goal_days = max(1, int(self.state["goal_days"]))
        return min(100, int(self.days_elapsed() * 100 / goal_days))

    def today_minutes(self) -> int:
        today = date.today().isoformat()
        return int(self.state.get("daily_minutes", {}).get(today, 0))

    def daily_goal_met(self) -> bool:
        return self.today_minutes() >= int(self.state.get("daily_goal_minutes", 20))

    def voice_share_percent(self) -> int:
        completed = max(1, int(self.state["completed_sessions"]))
        return int(self.state.get("voice_sessions", 0) * 100 / completed)

    def avg_user_words(self) -> int:
        sessions = self.state.get("sessions", [])
        if not sessions:
            return 0
        return int(sum(item.get("user_words", 0) for item in sessions) / len(sessions))

    def avg_assistant_words(self) -> int:
        sessions = self.state.get("sessions", [])
        if not sessions:
            return 0
        return int(sum(item.get("assistant_words", 0) for item in sessions) / len(sessions))

    def daily_chart_data(self, days: int = 7) -> list[tuple[str, int]]:
        activity = self.state.get("daily_activity", {})
        rows: list[tuple[str, int]] = []
        for offset in range(days - 1, -1, -1):
            current = date.fromordinal(date.today().toordinal() - offset)
            key = current.isoformat()
            rows.append((current.strftime("%d.%m"), int(activity.get(key, 0))))
        return rows

    def daily_minutes_chart_data(self, days: int = 7) -> list[tuple[str, int]]:
        minutes = self.state.get("daily_minutes", {})
        rows: list[tuple[str, int]] = []
        for offset in range(days - 1, -1, -1):
            current = date.fromordinal(date.today().toordinal() - offset)
            key = current.isoformat()
            rows.append((current.strftime("%d.%m"), int(minutes.get(key, 0))))
        return rows

    def heatmap_data(self, weeks: int = 13) -> list[tuple[str, int, int]]:
        """Return (date_iso, day_of_week, minutes) for the last `weeks` weeks.
        day_of_week: 0=Mon .. 6=Sun."""
        minutes = self.state.get("daily_minutes", {})
        total_days = weeks * 7
        today = date.today()
        # Align to start from Monday of the earliest week
        today_dow = today.weekday()  # 0=Mon
        start = today - timedelta(days=today_dow + (weeks - 1) * 7)
        rows: list[tuple[str, int, int]] = []
        for i in range(total_days):
            d = start + timedelta(days=i)
            key = d.isoformat()
            mins = int(minutes.get(key, 0))
            rows.append((key, d.weekday(), mins))
        return rows

    _IDIOMS: list[tuple[str, str, str]] = [
        ("break the ice", "растопить лёд, начать разговор", "She told a joke to break the ice."),
        ("piece of cake", "пара пустяков, очень легко", "The exam was a piece of cake."),
        ("hit the books", "усердно учиться", "I need to hit the books before the test."),
        ("under the weather", "неважно себя чувствовать", "I'm feeling under the weather today."),
        ("cost an arm and a leg", "стоить целое состояние", "That car costs an arm and a leg."),
        ("once in a blue moon", "очень редко", "We see them once in a blue moon."),
        ("let the cat out of the bag", "выдать секрет", "Don't let the cat out of the bag!"),
        ("spill the beans", "разболтать, выдать тайну", "He spilled the beans about the surprise."),
        ("burn the midnight oil", "работать допоздна", "She burned the midnight oil studying."),
        ("jump the gun", "поспешить, начать раньше времени", "Don't jump the gun — wait for instructions."),
        ("bite the bullet", "стиснуть зубы и терпеть", "I had to bite the bullet and apologize."),
        ("on the same page", "быть в согласии, понимать одинаково", "Let's make sure we're on the same page."),
        ("cut corners", "сэкономить на качестве", "Don't cut corners on safety."),
        ("ring a bell", "быть знакомым, напоминать", "That name rings a bell."),
        ("by the skin of one's teeth", "едва-едва, чудом", "I passed by the skin of my teeth."),
        ("hit the nail on the head", "попасть в точку", "You hit the nail on the head!"),
        ("kick the bucket", "умереть (неформально)", "The old machine finally kicked the bucket."),
        ("a blessing in disguise", "скрытое благо", "Losing that job was a blessing in disguise."),
        ("call it a day", "закончить работу", "Let's call it a day and rest."),
        ("the best of both worlds", "лучшее из двух вариантов", "Working from home gives the best of both worlds."),
        ("to get out of hand", "выйти из-под контроля", "The situation is getting out of hand."),
        ("to be on cloud nine", "быть на седьмом небе от счастья", "She was on cloud nine after the news."),
        ("to see eye to eye", "быть согласными", "We don't always see eye to eye."),
        ("to save for a rainy day", "откладывать на чёрный день", "Always save for a rainy day."),
        ("to add insult to injury", "усугубить ситуацию", "To add insult to injury, it started raining."),
        ("no pain, no gain", "без труда не вытащишь и рыбку из пруда", "No pain, no gain — keep practicing!"),
        ("to change one's mind", "передумать", "I changed my mind about the trip."),
        ("to take it easy", "расслабиться, не напрягаться", "Take it easy this weekend."),
        ("to make ends meet", "сводить концы с концами", "They struggle to make ends meet."),
        ("to keep one's fingers crossed", "надеяться на удачу", "Keep your fingers crossed for me!"),
    ]

    def idiom_of_day(self) -> tuple[str, str, str]:
        """Return (idiom, translation, example) for today."""
        day_of_year = date.today().timetuple().tm_yday
        idx = day_of_year % len(self._IDIOMS)
        return self._IDIOMS[idx]

    # ─── XP System ───

    _XP_PER_SESSION = {
        "dialogue": 15,
        "writing_task": 20,
        "roleplay": 20,
        "speaking_drill": 25,
        "grammar_exercise": 15,
        "listening_task": 20,
        "reading_task": 15,
        "dialogue_listening": 20,
        "dictation": 15,
        "shadowing": 20,
        "minimal_pairs": 15,
        "collocation_drill": 15,
        "error_correction": 15,
        "sentence_transformation": 20,
        "phrasal_verbs": 15,
        "dictogloss": 25,
        "input_flood": 15,
        "pushed_output": 25,
        "lexical_chunks": 15,
        "task_repetition": 20,
        "debate": 30,
        "vocab_review": 10,
    }
    _WEEKLY_XP_GOAL = 200

    def award_xp(self, practice_type: str, duration_seconds: int = 0, used_voice: bool = False, base_xp: int = 0) -> int:
        """Award XP for a completed session. Returns XP earned."""
        base = base_xp if base_xp > 0 else self._XP_PER_SESSION.get(practice_type, 10)
        # Bonus for longer sessions
        if duration_seconds > 300:
            base += 5
        if duration_seconds > 600:
            base += 5
        if used_voice:
            base += 5
        # Daily challenge bonus
        if self.daily_challenge_completed():
            pass  # already counted via challenge

        self.state["total_xp"] = int(self.state.get("total_xp", 0)) + base

        # Weekly XP tracking
        today = date.today().isoformat()
        week_key = today  # Track per-day, aggregate for week
        weekly = dict(self.state.get("weekly_xp", {}))
        weekly[today] = weekly.get(today, 0) + base
        # Keep only last 14 days
        cutoff = (date.today() - timedelta(days=14)).isoformat()
        weekly = {k: v for k, v in weekly.items() if k >= cutoff}
        self.state["weekly_xp"] = weekly

        # XP history (last 50)
        history = list(self.state.get("xp_history", []))
        history.append({"date": today, "xp": base, "type": practice_type})
        self.state["xp_history"] = history[-50:]

        self._save_state()
        return base

    def weekly_xp_total(self) -> int:
        """Return total XP earned in the last 7 days."""
        weekly = self.state.get("weekly_xp", {})
        cutoff = (date.today() - timedelta(days=7)).isoformat()
        return sum(v for k, v in weekly.items() if k >= cutoff)

    def weekly_xp_goal(self) -> int:
        return self._WEEKLY_XP_GOAL

    def daily_xp(self) -> int:
        """Return XP earned today."""
        today = date.today().isoformat()
        return int(self.state.get("weekly_xp", {}).get(today, 0))

    def total_xp(self) -> int:
        return int(self.state.get("total_xp", 0))

    def recent_sessions(self, limit: int = 10) -> list[dict]:
        return list(reversed(self.state.get("sessions", [])[-limit:]))

    def recent_speaking_reviews(self, limit: int = 10) -> list[dict]:
        return list(reversed(self.state.get("speaking_reviews", [])[-limit:]))

    def speaking_average_scores(self) -> tuple[int, int, int]:
        reviews = self.state.get("speaking_reviews", [])
        if not reviews:
            return 0, 0, 0
        pronunciation = int(sum(item.get("pronunciation_score", 0) for item in reviews) / len(reviews))
        tempo = int(sum(item.get("tempo_score", 0) for item in reviews) / len(reviews))
        confidence = int(sum(item.get("confidence_score", 0) for item in reviews) / len(reviews))
        return pronunciation, tempo, confidence

    def grammar_progress(self) -> tuple[int, int]:
        level = self.state["level"]
        total = len(grammar_for_level(level))
        completed = len(self.state.get("grammar_completed", []))
        return completed, total

    def current_grammar_point(self) -> GrammarPoint | None:
        level = self.state["level"]
        completed = set(self.state.get("grammar_completed", []))
        for gp in grammar_for_level(level):
            if gp.id not in completed:
                return gp
        return None

    def srs_due_count(self) -> int:
        return self.srs.due_count()

    def srs_new_count(self) -> int:
        return self.srs.new_count()

    def srs_review_session(self, limit: int = 20) -> list[SRSCard]:
        if self.srs_new_count() < 5:
            self._seed_vocab_for_level()
        return self.srs.review_session(limit)

    def db_word_count(self) -> int:
        try:
            from worddb import get_db
            return get_db().count()
        except Exception:
            return 0

    def db_count_by_level(self) -> dict:
        try:
            from worddb import get_db
            return get_db().count_by_level()
        except Exception:
            return {}

    def word_of_day(self) -> dict | None:
        """Return a deterministic word-of-the-day based on date seed."""
        try:
            from worddb import get_db
            import hashlib
            today = date.today().isoformat()
            seed = int(hashlib.md5(today.encode()).hexdigest()[:8], 16)
            db = get_db()
            total = db.count()
            if total == 0:
                return None
            level = self.state.get("level", "B1")
            words = db.random_words(level, 20, category="vocab")
            if not words:
                words = db.random_words(level, 20)
            if not words:
                return None
            return words[seed % len(words)]
        except Exception:
            return None

    def game_high_scores(self) -> list[dict]:
        return self.state.get("game_scores", [])

    def vocab_progress(self) -> tuple[int, int]:
        """Return (learned_count, total_for_level) for vocabulary progress display."""
        learned = sum(1 for c in self.srs.cards.values() if c.repetition >= 3)
        try:
            from worddb import get_db
            level_counts = get_db().count_by_level()
            total = level_counts.get(self.level, 0)
            return (learned, total)
        except Exception:
            return (learned, 0)

    def record_game_score(self, score: int, correct: int, wrong: int) -> None:
        scores = self.state.get("game_scores", [])
        scores.append({"date": date.today().isoformat(), "score": score, "correct": correct, "wrong": wrong})
        scores.sort(key=lambda x: x["score"], reverse=True)
        self.state["game_scores"] = scores[:10]
        self._save_state()

    def survival_game_progress(self) -> list[str]:
        return self.state.get("survival_completed_scenes", [])

    def get_student_profile(self) -> dict:
        return self.state.get("student_profile", {"name": "", "profession": "", "hobbies": [], "goals": "", "notes": []})

    def update_student_profile(self, **kwargs) -> None:
        profile = self.get_student_profile()
        for key, val in kwargs.items():
            if key in profile:
                profile[key] = val
        self.state["student_profile"] = profile
        self._save_state()

    def extract_profile_from_text(self, text: str) -> None:
        """Heuristically extract student info from chat messages."""
        text_lower = text.lower()
        profile = self.get_student_profile()
        updated = False

        if not profile["name"]:
            import re
            m = re.search(r'(?:меня зовут|я\s+|my name is|i am|i\'m)\s+([A-ZА-Я][a-zа-я]{1,20})', text)
            if m:
                profile["name"] = m.group(1)
                updated = True

        if not profile["profession"]:
            prof_keywords = {
                "IT": ["программист", "разработчик", "developer", "programmer", "it ", "software"],
                "дизайнер": ["дизайнер", "designer", "ui ", "ux "],
                "учитель": ["учитель", "teacher", "преподаватель"],
                "врач": ["врач", "doctor", "медик"],
                "менеджер": ["менеджер", "manager", "управлени"],
                "студент": ["студент", "student", "учу"],
                "инженер": ["инженер", "engineer"],
                "маркетинг": ["маркетинг", "marketing", "seo"],
            }
            for prof, keywords in prof_keywords.items():
                if any(kw in text_lower for kw in keywords):
                    profile["profession"] = prof
                    updated = True
                    break

        if not profile["goals"]:
            goal_keywords = {
                "работа за границей": ["relocate", "move to", "работать за", "переезд", "emigrate"],
                "собеседование": ["interview", "собеседован"],
                "IELTS/TOEFL": ["ielts", "toefl", "exam", "экзамен"],
                "путешествия": ["travel", "путешеств", "trip"],
                "карьерный рост": ["career", "promotion", "карьер"],
                "общение": ["communicate", "общение", "разговор"],
            }
            for goal, keywords in goal_keywords.items():
                if any(kw in text_lower for kw in keywords):
                    profile["goals"] = goal
                    updated = True
                    break

        if updated:
            self.state["student_profile"] = profile
            self._save_state()

    def add_session_summary(self, summary: str) -> None:
        summaries = self.state.get("session_summaries", [])
        summaries.append({"date": date.today().isoformat(), "summary": summary})
        self.state["session_summaries"] = summaries[-30:]
        self._save_state()

    def recent_session_summaries(self, limit: int = 5) -> list[dict]:
        return self.state.get("session_summaries", [])[-limit:]

    def profile_context(self) -> str:
        """Return student profile as context string for prompt building."""
        p = self.get_student_profile()
        parts = []
        if p["name"]:
            parts.append(f"Имя ученика: {p['name']}")
        if p["profession"]:
            parts.append(f"Профессия: {p['profession']}")
        if p["hobbies"]:
            parts.append(f"Хобби: {', '.join(p['hobbies'])}")
        if p["goals"]:
            parts.append(f"Цель: {p['goals']}")
        return " | ".join(parts) if parts else ""

    def record_survival_scene(self, scene_id: str, passed: bool, rating: float, words_used: list[str]) -> None:
        scenes = self.state.get("survival_completed_scenes", [])
        if passed and scene_id not in scenes:
            scenes.append(scene_id)
            self.state["survival_completed_scenes"] = scenes
        history = self.state.get("survival_history", [])
        history.append({"date": date.today().isoformat(), "scene": scene_id, "passed": passed, "rating": rating, "words": len(words_used)})
        self.state["survival_history"] = history[-50:]
        self._save_state()

    def detective_game_progress(self) -> list[str]:
        return self.state.get("detective_solved_cases", [])

    def record_detective_case(self, case_title: str, solved: bool, score: int, words_used: list[str]) -> None:
        solved_cases = self.state.get("detective_solved_cases", [])
        if solved and case_title not in solved_cases:
            solved_cases.append(case_title)
            self.state["detective_solved_cases"] = solved_cases
        history = self.state.get("detective_history", [])
        history.append({"date": date.today().isoformat(), "case": case_title, "solved": solved, "score": score, "words": len(words_used)})
        self.state["detective_history"] = history[-50:]
        self._save_state()

    def time_loop_progress(self) -> list[str]:
        return self.state.get("time_loop_broken", [])

    def record_time_loop(self, scenario_id: str, broken: bool, score: int, words_learned: list[str]) -> None:
        broken_loops = self.state.get("time_loop_broken", [])
        if broken and scenario_id not in broken_loops:
            broken_loops.append(scenario_id)
            self.state["time_loop_broken"] = broken_loops
        history = self.state.get("time_loop_history", [])
        history.append({"date": date.today().isoformat(), "scenario": scenario_id, "broken": broken, "score": score, "words": len(words_learned)})
        self.state["time_loop_history"] = history[-50:]
        self._save_state()

    def error_pattern_summary(self) -> list[tuple[str, int]]:
        patterns = self.state.get("error_patterns", {})
        return sorted(patterns.items(), key=lambda x: x[1], reverse=True)[:5]

    def learning_context(self) -> str:
        weakest = self.weakest_skill()
        strongest = self.strongest_skill()
        gp = self.current_grammar_point()
        gp_info = f"Текущая грамматика: {gp.title}." if gp else "Грамматика уровня завершена."
        due = self.srs_due_count()
        return (
            f"Уровень: {self.level}→{self.target_level}. "
            f"Сессий: {self.state['completed_sessions']}. "
            f"Слабая зона: {SKILL_RU.get(weakest, weakest)}. "
            f"Сильная зона: {SKILL_RU.get(strongest, strongest)}. "
            f"{gp_info} "
            f"Карточек к повторению: {due}."
        )

    def recommended_practice(self, topic: str = "") -> tuple[str, str]:
        """Recommend next practice based on interleaving and weakest skill."""
        weakest = self.weakest_skill()
        topic = topic.strip() or "everyday English"

        if self.srs_due_count() >= 5:
            return ("vocab_review", f"Повтори слова через интервальную систему. У тебя {self.srs_due_count()} карточек к повторению.")

        # Error-driven: if recurring errors exist, recommend targeted practice
        error_patterns = self.state.get("error_patterns", {})
        top_error = max(error_patterns, key=error_patterns.get) if error_patterns else None
        if top_error and error_patterns[top_error] >= 3:
            error_practice_map = {
                "tense": ("grammar_exercise", f"Ты часто делаешь ошибки во временах. Давай потренируем tenses: 4 задания на уровнях {self.level}, затем проверка."),
                "article": ("error_correction", f"Повторяющиеся ошибки с артиклями. Дай 5 предложений с ошибками в артиклях для исправления. Уровень {self.level}."),
                "preposition": ("error_correction", f"Ошибки с предлогами. Дай 5 предложений с ошибками в предлогах для исправления. Уровень {self.level}."),
                "word_order": ("sentence_transformation", f"Ошибки в порядке слов. Дай 5 заданий на трансформацию предложений с перестройкой структуры. Уровень {self.level}."),
                "spelling": ("dictation", f"Ошибки в орфографии. Проведи диктант: 5 предложений для проверки написания. Уровень {self.level}."),
                "pronunciation": ("minimal_pairs", f"Ошибки в произношении. Дай 5 пар минимальных слов (minimal pairs) с IPA и примерами. Уровень {self.level}."),
                "collocation": ("collocation_drill", f"Ошибки в словосочетаниях. Дай 5 collocations с пропусками. Уровень {self.level}."),
                "plural": ("grammar_exercise", f"Ошибки с множественным числом. Давай потренируем singular/plural: 4 задания. Уровень {self.level}."),
            }
            if top_error in error_practice_map:
                return error_practice_map[top_error]

        if weakest == "speaking":
            speaking_modes = [
                ("speaking_drill", f"Проведи speaking drill на тему {topic} для уровня {self.level}. Один вопрос за раз, затем короткий разбор на русском."),
                ("shadowing", f"Дай 3 короткие английские фразы на тему {topic} для shadowing-практики. Уровень {self.level}."),
                ("minimal_pairs", f"Дай 5 пар минимальных слов (minimal pairs) для тренировки произношения. Покажи IPA и примеры."),
                ("pushed_output", f"Дай pushed output task на тему {topic}: расскажи историю с грамматическими ограничениями. Уровень {self.level}."),
                ("task_repetition", f"Дай task repetition: коммуникативную задачу на тему {topic}, затем повтори в новом контексте. Уровень {self.level}."),
            ]
            idx = self.state["completed_sessions"] % len(speaking_modes)
            return speaking_modes[idx]
        if weakest == "grammar":
            gp = self.current_grammar_point()
            if gp:
                return ("grammar_exercise", f"Тема: {gp.title}. {gp.summary} Дай 4 задания на уровне {self.level}, затем проверка и объяснение на русском.")
            grammar_modes = [
                ("grammar_exercise", f"Сделай compact grammar exercise на тему {topic} для уровня {self.level}: 4 задания, проверка, объяснение."),
                ("input_flood", f"Дай input flood текст на тему {topic} с насыщенным повторением одной грамматической структуры. Уровень {self.level}."),
                ("sentence_transformation", f"Дай 5 заданий на преобразование предложений (sentence transformation) для уровня {self.level}."),
            ]
            idx = self.state["completed_sessions"] % len(grammar_modes)
            return grammar_modes[idx]
        if weakest == "writing":
            writing_modes = [
                ("writing_task", f"Дай writing task на тему {topic} для уровня {self.level}. Пользователь напишет 50-80 слов, затем ты проверишь и объяснишь ошибки на русском."),
                ("dictogloss", f"Дай dictogloss на тему {topic}: короткий текст для реконструкции по памяти. Уровень {self.level}."),
                ("pushed_output", f"Дай pushed output task на тему {topic}: опиши ситуацию с грамматическими ограничениями. Уровень {self.level}."),
            ]
            idx = self.state["completed_sessions"] % len(writing_modes)
            return writing_modes[idx]
        if weakest == "listening":
            listening_modes = [
                ("listening_task", f"Создай short listening simulation на тему {topic} для уровня {self.level}. Озвучь короткий текст, затем задай 3 вопроса по содержанию."),
                ("dialogue_listening", f"Дай короткий диалог на тему {topic} для практики аудирования. 6-8 реплик. Уровень {self.level}."),
                ("dictogloss", f"Дай dictogloss на тему {topic}: текст для реконструкции после прослушивания. Уровень {self.level}."),
            ]
            idx = self.state["completed_sessions"] % len(listening_modes)
            return listening_modes[idx]
        if weakest == "vocabulary":
            vocab_modes = [
                ("lexical_chunks", f"Дай тренировку лексических чанков и устойчивых выражений на тему {topic}. Уровень {self.level}."),
                ("collocation_drill", f"Дай 5 словосочетаний (collocations) на тему {topic} с пропусками. Уровень {self.level}."),
                ("phrasal_verbs", f"Дай 5 фразовых глаголов на тему {topic} с контекстом и пропусками. Уровень {self.level}."),
            ]
            idx = self.state["completed_sessions"] % len(vocab_modes)
            return vocab_modes[idx]
        return ("reading_task", f"Дай короткий текст для чтения на тему {topic} для уровня {self.level} (80-120 слов). Затем 3 вопроса на понимание и ключевые слова с переводом.")

    def recommended_interleaved_session(self, topic: str = "") -> list[tuple[str, str]]:
        """Return 2-3 practice types for an interleaved session.

        Interleaving mixes different skill areas in one session, which research
        shows improves retention vs. blocked practice (Rohrer & Taylor 2007).
        """
        topic = topic.strip() or "everyday English"
        skills_sorted = sorted(SKILLS, key=lambda s: self.skill_score(s))
        weakest = skills_sorted[0]
        second = skills_sorted[1]

        pt1, txt1 = self.recommended_practice(topic)

        if second == "speaking":
            pt2 = "shadowing"
            txt2 = f"Дай 3 короткие фразы для shadowing на тему {topic}. Уровень {self.level}."
        elif second == "grammar":
            pt2 = "error_correction"
            txt2 = f"Дай 5 предложений с ошибками для исправления. Уровень {self.level}."
        elif second == "writing":
            pt2 = "sentence_transformation"
            txt2 = f"Дай 5 заданий на трансформацию предложений. Уровень {self.level}."
        elif second == "listening":
            pt2 = "dictation"
            txt2 = f"Проведи диктант: 5 коротких предложений. Уровень {self.level}."
        else:
            pt2 = "lexical_chunks"
            txt2 = f"Дай тренировку лексических чанков на тему {topic}. Уровень {self.level}."

        return [(pt1, txt1), (pt2, txt2)]

    # ─── Error journal ───

    def _log_error_journal(self, practice_type: str, error_count: int, assistant_text: str, error_keys, combined: str) -> None:
        """Log errors to persistent journal file."""
        journal = self._load_error_journal()
        detected = []
        for key, keywords in error_keys:
            if any(kw in combined for kw in keywords):
                detected.append(key)
        entry = {
            "date": datetime.now().isoformat(timespec="seconds"),
            "practice_type": practice_type,
            "error_count": error_count,
            "categories": detected,
            "excerpt": assistant_text[:200],
        }
        journal.append(entry)
        journal = journal[-200:]
        self.error_journal_path.write_text(json.dumps(journal, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_error_journal(self) -> list:
        if not self.error_journal_path.exists():
            return []
        try:
            return json.loads(self.error_journal_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def recent_errors(self, limit: int = 20) -> list[dict]:
        """Return recent error journal entries."""
        return self._load_error_journal()[-limit:]

    def error_journal_summary(self) -> dict:
        """Return summary stats from error journal."""
        journal = self._load_error_journal()
        if not journal:
            return {"total": 0, "by_category": {}, "recent_trend": []}
        by_cat: dict[str, int] = {}
        for entry in journal:
            for cat in entry.get("categories", []):
                by_cat[cat] = by_cat.get(cat, 0) + 1
        last_7 = journal[-7:]
        trend = [(e["date"][:10], e["error_count"], e.get("categories", [])) for e in last_7]
        return {"total": len(journal), "by_category": by_cat, "recent_trend": trend}

    # ─── Weekly summary ───

    def weekly_summary(self) -> str:
        """Generate a weekly progress summary string."""
        sessions = self.state.get("sessions", [])
        today = date.today()
        week_ago = today - timedelta(days=7)
        week_sessions = [s for s in sessions if s.get("date", "") >= week_ago.isoformat()]

        total_sessions = len(week_sessions)
        total_minutes = sum(s.get("duration_seconds", 0) for s in week_sessions) // 60
        voice_count = sum(1 for s in week_sessions if s.get("voice"))
        practice_types = {}
        for s in week_sessions:
            pt = s.get("practice_type", "unknown")
            practice_types[pt] = practice_types.get(pt, 0) + 1

        streak = self.streak_days()
        skills = self.state.get("skill_scores", {})
        weakest = self.weakest_skill()
        strongest = self.strongest_skill()

        error_summary = self.error_journal_summary()
        top_errors = sorted(error_summary["by_category"].items(), key=lambda x: x[1], reverse=True)[:3]

        badges = self.all_earned_badges()
        new_badges_count = len(badges)

        lines = [
            f"📊 Недельный отчёт ({week_ago.isoformat()} → {today.isoformat()})",
            f"",
            f"Сессий за неделю: {total_sessions}",
            f"Минут за неделю: {total_minutes}",
            f"Голосовых ответов: {voice_count}",
            f"Текущий streak: {streak} дней",
            f"",
            f"Навыки:",
        ]
        skill_ru = {
            "speaking": "Говорение", "listening": "Аудирование",
            "grammar": "Грамматика", "vocabulary": "Словарь", "writing": "Письмо",
        }
        for skill in SKILLS:
            score = skills.get(skill, 20)
            bar = "█" * (score // 5) + "░" * (20 - score // 5)
            lines.append(f"  {skill_ru.get(skill, skill):12s} {bar} {score}")

        lines.append(f"")
        lines.append(f"Сильная зона: {skill_ru.get(strongest, strongest)}")
        lines.append(f"Слабая зона: {skill_ru.get(weakest, weakest)}")

        if top_errors:
            err_lines = [f"  {cat}: {count} раз" for cat, count in top_errors]
            lines.append(f"")
            lines.append(f"Частые ошибки:")
            lines.extend(err_lines)

        if practice_types:
            pt_ru = PRACTICE_RU
            pt_lines = [f"  {pt_ru.get(pt, pt)}: {count}" for pt, count in sorted(practice_types.items(), key=lambda x: x[1], reverse=True)]
            lines.append(f"")
            lines.append(f"Типы практики:")
            lines.extend(pt_lines)

        lines.append(f"")
        lines.append(f"Достижений получено: {new_badges_count}")

        return "\n".join(lines)

    # ─── Gamification: badges ───

    BADGES = [
        ("first_session", "🎯 Первая сессия", "Завершить первую практику", lambda s: s["completed_sessions"] >= 1),
        ("ten_sessions", "🔥 10 сессий", "Завершить 10 практических сессий", lambda s: s["completed_sessions"] >= 10),
        ("fifty_sessions", "💪 50 сессий", "Завершить 50 практических сессий", lambda s: s["completed_sessions"] >= 50),
        ("hundred_sessions", "🏆 100 сессий", "Завершить 100 практических сессий", lambda s: s["completed_sessions"] >= 100),
        ("streak_3", "📅 3 дня подряд", "Заниматься 3 дня подряд", lambda s: s.get("_streak", 0) >= 3),
        ("streak_7", "📅 7 дней подряд", "Заниматься 7 дней подряд", lambda s: s.get("_streak", 0) >= 7),
        ("streak_30", "📅 30 дней подряд", "Заниматься 30 дней подряд", lambda s: s.get("_streak", 0) >= 30),
        ("streak_100", "📅 100 дней подряд", "Заниматься 100 дней подряд", lambda s: s.get("_streak", 0) >= 100),
        ("voice_10", "🎤 Голосовой практика", "10 голосовых ответов", lambda s: s["voice_sessions"] >= 10),
        ("voice_50", "🎙 Мастер речи", "50 голосовых ответов", lambda s: s["voice_sessions"] >= 50),
        ("vocab_master", "📚 Мастер слов", "Выучить 30 карточек слов", lambda s: s.get("_vocab_learned", 0) >= 30),
        ("grammar_5", "📖 Грамматик", "Освоить 5 грамматических тем", lambda s: len(s["grammar_completed"]) >= 5),
        ("grammar_15", "📖 Грамматик-pro", "Освоить 15 грамматических тем", lambda s: len(s["grammar_completed"]) >= 15),
        ("level_up", "⬆️ Переход уровня", "Повысить свой уровень", lambda s: len(s.get("level_history", [])) >= 2),
        ("minutes_300", "⏱ 5 часов", "Накопить 300 минут практики", lambda s: s["total_minutes"] >= 300),
        ("minutes_1000", "⏱ Марафон", "Накопить 1000 минут практики", lambda s: s["total_minutes"] >= 1000),
        ("all_skills_50", "🌟 Универсал", "Все навыки 50+", lambda s: all(v >= 50 for v in s["skill_scores"].values())),
    ]

    _STREAK_MILESTONE_BONUS = {7: 50, 30: 150, 100: 500}

    def check_badges(self) -> list[tuple[str, str]]:
        """Check for newly earned badges. Returns list of (badge_id, badge_name) for new ones."""
        state = dict(self.state)
        state["_streak"] = self.streak_days()
        state["_vocab_learned"] = sum(1 for c in self.srs.cards.values() if c.repetition >= 3)

        earned = set(self.state.get("earned_badges", []))
        new_badges = []
        for badge_id, badge_name, badge_desc, check_fn in self.BADGES:
            if badge_id not in earned and check_fn(state):
                earned.add(badge_id)
                new_badges.append((badge_id, badge_name))

        if new_badges:
            self.state["earned_badges"] = list(earned)
            # Award bonus XP for streak milestones
            streak = self.streak_days()
            for milestone, bonus in self._STREAK_MILESTONE_BONUS.items():
                if streak >= milestone and f"streak_{milestone}" in [b[0] for b in new_badges]:
                    self.state["total_xp"] = int(self.state.get("total_xp", 0)) + bonus
                    today = date.today().isoformat()
                    weekly = dict(self.state.get("weekly_xp", {}))
                    weekly[today] = weekly.get(today, 0) + bonus
                    self.state["weekly_xp"] = weekly
            self._save_state()

        return new_badges

    def streak_milestone_reached(self) -> tuple[int, int] | None:
        """Check if a streak milestone was just reached. Returns (days, bonus_xp) or None."""
        streak = self.streak_days()
        if streak in self._STREAK_MILESTONE_BONUS:
            milestone_key = f"streak_milestone_{streak}"
            claimed = set(self.state.get("claimed_milestones", []))
            if milestone_key not in claimed:
                claimed.add(milestone_key)
                self.state["claimed_milestones"] = list(claimed)
                bonus = self._STREAK_MILESTONE_BONUS[streak]
                self.state["total_xp"] = int(self.state.get("total_xp", 0)) + bonus
                today = date.today().isoformat()
                weekly = dict(self.state.get("weekly_xp", {}))
                weekly[today] = weekly.get(today, 0) + bonus
                self.state["weekly_xp"] = weekly
                self._save_state()
                return (streak, bonus)
        return None

    def all_earned_badges(self) -> list[tuple[str, str, str]]:
        """Return all earned badges with descriptions."""
        earned = set(self.state.get("earned_badges", []))
        return [(bid, bname, bdesc) for bid, bname, bdesc, _ in self.BADGES if bid in earned]

    def all_badges(self) -> list[tuple[str, str, str, bool]]:
        """Return all badges with earned status."""
        earned = set(self.state.get("earned_badges", []))
        return [(bid, bname, bdesc, bid in earned) for bid, bname, bdesc, _ in self.BADGES]

    # ─── Daily Challenge ───

    _DAILY_CHALLENGES: list[tuple[str, str, str]] = [
        ("writing", "Напиши 5 предложений о своих планах на выходные.", "Письмо"),
        ("speaking", "Опиши свою комнату голосом за 30 секунд.", "Говорение"),
        ("grammar", "Составь 5 вопросов в Present Perfect.", "Грамматика"),
        ("vocab", "Используй 5 новых слов из SRS в мини-диалоге.", "Словарь"),
        ("reading", "Прочитай AI-рассказ и ответь на вопросы.", "Чтение"),
        ("writing", "Напиши короткое письмо другу на английском.", "Письмо"),
        ("speaking", "Расскажи о своём любимом фильме голосом.", "Говорение"),
        ("grammar", "Напиши 5 предложений с Conditional (If I were...).", "Грамматика"),
        ("vocab", "Составь 3 предложения со словами: challenge, improve, achieve.", "Словарь"),
        ("writing", "Опиши свой обычный день от утра до вечера.", "Письмо"),
        ("speaking", "Ответь голосом: What did you do yesterday?", "Говорение"),
        ("grammar", "Напиши 5 предложений в Past Continuous.", "Грамматика"),
        ("reading", "Прочитай веб-статью и найди 3 новых слова.", "Чтение"),
        ("vocab", "Сыграй в Word Battle и выучи 5 новых слов.", "Словарь"),
        ("writing", "Напиши отзыв о книге или фильме (3-5 предложений).", "Письмо"),
    ]

    def daily_challenge(self) -> tuple[str, str, str]:
        """Return (challenge_type, challenge_text, category) for today."""
        day_of_year = date.today().timetuple().tm_yday
        idx = day_of_year % len(self._DAILY_CHALLENGES)
        return self._DAILY_CHALLENGES[idx]

    def daily_challenge_completed(self) -> bool:
        """Check if today's challenge was completed."""
        today = date.today().isoformat()
        completed = set(self.state.get("daily_challenges_completed", []))
        return today in completed

    def complete_daily_challenge(self) -> None:
        """Mark today's challenge as completed and credit practice time."""
        today = date.today().isoformat()
        completed = list(self.state.get("daily_challenges_completed", []))
        if today not in completed:
            completed.append(today)
            # Keep only last 30 entries
            self.state["daily_challenges_completed"] = completed[-30:]
            # Credit 10 minutes toward daily goal
            daily_min = dict(self.state.get("daily_minutes", {}))
            daily_min[today] = daily_min.get(today, 0) + 10
            self.state["daily_minutes"] = daily_min
            self._save_state()

    # ─── CEFR Placement Test ───

    _PLACEMENT_QUESTIONS: list[tuple[str, str, list[str], int]] = [
        ("Choose the correct sentence:", "A) She don't like coffee.  B) She doesn't likes coffee.  C) She doesn't like coffee.  D) She not like coffee.", ["A", "B", "C", "D"], 2),
        ("What ___ you doing yesterday at 5pm?", "A) was  B) were  C) did  D) are", ["A", "B", "C", "D"], 1),
        ("I have ___ to Paris three times.", "A) be  B) been  C) being  D) was", ["A", "B", "C", "D"], 1),
        ("If I ___ rich, I would travel the world.", "A) am  B) was  C) were  D) be", ["A", "B", "C", "D"], 2),
        ("She said she ___ come the next day.", "A) will  B) would  C) is  D) can", ["A", "B", "C", "D"], 1),
        ("The book ___ by millions of people.", "A) read  B) reads  C) has read  D) has been read", ["A", "B", "C", "D"], 3),
        ("I'm looking forward ___ you soon.", "A) to see  B) to seeing  C) seeing  D) see", ["A", "B", "C", "D"], 1),
        ("He's the man ___ car was stolen.", "A) which  B) who's  C) whose  D) that", ["A", "B", "C", "D"], 2),
        ("By the time we arrived, the film ___.", "A) started  B) had started  C) has started  D) is starting", ["A", "B", "C", "D"], 1),
        ("I wish I ___ more time to study.", "A) have  B) had  C) will have  D) would have", ["A", "B", "C", "D"], 1),
    ]

    def needs_placement_test(self) -> bool:
        """Check if the user needs to take the placement test."""
        return not self.state.get("placement_done", False)

    def placement_questions(self) -> list[tuple[str, str, list[str]]]:
        """Return placement test questions (question, options, choices)."""
        return [(q, o, c) for q, o, c, _ in self._PLACEMENT_QUESTIONS]

    def submit_placement_test(self, answers: list[int]) -> str:
        """Score the placement test and set the level. Returns the determined level."""
        correct = 0
        for i, (_, _, _, answer_idx) in enumerate(self._PLACEMENT_QUESTIONS):
            if i < len(answers) and answers[i] == answer_idx:
                correct += 1
        # Map score to CEFR level (minimum B1)
        if correct <= 6:
            level = "B1"
        elif correct <= 8:
            level = "B2"
        else:
            level = "C1"
        self.state["level"] = level
        self.state["placement_done"] = True
        self._save_state()
        return level
