"""SQLite word database for Olga English Coach.

Replaces in-memory lists with a proper indexed database.
Features: FTS5 full-text search, CEFR filtering, lazy loading, SRS fields.

Usage:
    from worddb import WordDB
    db = WordDB()               # creates ~/.olga_coach/words.db
    db.words_for_level("B1")    # lazy: LIMIT 50
    db.search("app")            # FTS5 instant search
    db.random_words("B2", 10)   # random sample
"""

from __future__ import annotations

import os
import random
import sqlite3
from pathlib import Path

from app_paths import get_user_data_dir

# ── Path setup ────────────────────────────────────────────────
_DB_PATH = get_user_data_dir() / "words.db"

CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS words (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    word        TEXT NOT NULL,
    translation TEXT NOT NULL DEFAULT '',
    pos         TEXT NOT NULL DEFAULT '',
    example     TEXT NOT NULL DEFAULT '',
    ipa         TEXT NOT NULL DEFAULT '',
    collocations TEXT NOT NULL DEFAULT '',
    word_family  TEXT NOT NULL DEFAULT '',
    cefr        TEXT NOT NULL DEFAULT 'A1',
    theme       TEXT NOT NULL DEFAULT 'general',
    source      TEXT NOT NULL DEFAULT 'wordbank',
    category    TEXT NOT NULL DEFAULT 'vocab'
);

CREATE INDEX IF NOT EXISTS idx_cefr   ON words(cefr);
CREATE INDEX IF NOT EXISTS idx_word   ON words(word);
CREATE INDEX IF NOT EXISTS idx_cat    ON words(category);

CREATE VIRTUAL TABLE IF NOT EXISTS words_fts USING fts5(
    word, translation, example, content='words', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS words_ai AFTER INSERT ON words BEGIN
    INSERT INTO words_fts(rowid, word, translation, example)
    VALUES (new.id, new.word, new.translation, new.example);
END;

CREATE TRIGGER IF NOT EXISTS words_ad AFTER DELETE ON words BEGIN
    INSERT INTO words_fts(words_fts, rowid, word, translation, example)
    VALUES ('delete', old.id, old.word, old.translation, old.example);
END;

CREATE TRIGGER IF NOT EXISTS words_au AFTER UPDATE ON words BEGIN
    INSERT INTO words_fts(words_fts, rowid, word, translation, example)
    VALUES ('delete', old.id, old.word, old.translation, old.example);
    INSERT INTO words_fts(rowid, word, translation, example)
    VALUES (new.id, new.word, new.translation, new.example);
END;
"""


class WordDB:
    """SQLite-backed word database with lazy loading and FTS search."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            db_path = _DB_PATH
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._ensure_schema()

    # ── Connection ────────────────────────────────────────────
    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
            self._conn.execute("PRAGMA cache_size=-64000;")  # 64MB
        return self._conn

    def _ensure_schema(self) -> None:
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Populate ──────────────────────────────────────────────
    def bulk_insert(self, rows: list[dict]) -> int:
        """Insert many word rows. Returns count inserted."""
        if not rows:
            return 0
        cols = (
            "word", "translation", "pos", "example", "ipa",
            "collocations", "word_family", "cefr", "theme", "source", "category",
        )
        placeholders = ",".join("?" * len(cols))
        sql = f"INSERT OR IGNORE INTO words ({','.join(cols)}) VALUES ({placeholders})"
        data = [
            tuple(r.get(c, "") for c in cols)
            for r in rows
        ]
        cur = self.conn.executemany(sql, data)
        self.conn.commit()
        return cur.rowcount

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]

    def count_by_level(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT cefr, COUNT(*) FROM words WHERE category='vocab' GROUP BY cefr"
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    # ── Queries (lazy) ────────────────────────────────────────
    def words_for_level(
        self, level: str, limit: int = 50, offset: int = 0,
        category: str = "vocab",
    ) -> list[dict]:
        """Lazy-load words by CEFR level (up to *level*)."""
        level_idx = CEFR_LEVELS.index(level) if level in CEFR_LEVELS else 3
        levels = CEFR_LEVELS[:level_idx + 1]
        placeholders = ",".join("?" * len(levels))
        rows = self.conn.execute(
            f"SELECT * FROM words WHERE category=? AND cefr IN ({placeholders}) "
            f"ORDER BY id LIMIT ? OFFSET ?",
            [category, *levels, limit, offset],
        ).fetchall()
        return [dict(r) for r in rows]

    def random_words(self, level: str, count: int = 10, category: str = "vocab") -> list[dict]:
        """Random sample of words at or below *level*."""
        level_idx = CEFR_LEVELS.index(level) if level in CEFR_LEVELS else 3
        levels = CEFR_LEVELS[:level_idx + 1]
        placeholders = ",".join("?" * len(levels))
        rows = self.conn.execute(
            f"SELECT * FROM words WHERE category=? AND cefr IN ({placeholders}) "
            f"ORDER BY RANDOM() LIMIT ?",
            [category, *levels, count],
        ).fetchall()
        return [dict(r) for r in rows]

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """FTS5 full-text search across word, translation, example."""
        rows = self.conn.execute(
            "SELECT w.* FROM words w JOIN words_fts f ON w.id = f.rowid "
            "WHERE words_fts MATCH ? ORDER BY rank LIMIT ?",
            [query, limit],
        ).fetchall()
        return [dict(r) for r in rows]

    def by_category(self, category: str, limit: int = 50, offset: int = 0) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM words WHERE category=? ORDER BY id LIMIT ? OFFSET ?",
            [category, limit, offset],
        ).fetchall()
        return [dict(r) for r in rows]

    def all_themes(self, level: str | None = None) -> list[str]:
        if level:
            rows = self.conn.execute(
                "SELECT DISTINCT theme FROM words WHERE category='vocab' AND cefr=? ORDER BY theme",
                [level],
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT DISTINCT theme FROM words WHERE category='vocab' ORDER BY theme"
            ).fetchall()
        return [r[0] for r in rows]

    # ── SRS-friendly ──────────────────────────────────────────
    def words_for_review(self, limit: int = 20) -> list[dict]:
        """Placeholder for SRS integration — returns random due words."""
        return self.random_words("B1", limit)

    # ── Convenience for coach.py ──────────────────────────────
    def phrasal_verbs(self, level: str, limit: int = 10) -> list[dict]:
        return self._category_for_level("phrasal_verb", level, limit)

    def collocations(self, level: str, limit: int = 10) -> list[dict]:
        return self._category_for_level("collocation", level, limit)

    def common_errors(self, level: str, limit: int = 8) -> list[dict]:
        return self._category_for_level("common_error", level, limit)

    def idioms(self, level: str, limit: int = 8) -> list[dict]:
        return self._category_for_level("idiom", level, limit)

    def confusing_words(self, level: str, limit: int = 8) -> list[dict]:
        return self._category_for_level("confusing_word", level, limit)

    def prepositions(self, level: str, limit: int = 10) -> list[dict]:
        return self._category_for_level("preposition", level, limit)

    def maritime_terms(self, limit: int = 20) -> list[dict]:
        return self.by_category("maritime", limit)

    def slang_swear(self, severity: str | None = None, limit: int = 20) -> list[dict]:
        if severity:
            rows = self.conn.execute(
                "SELECT * FROM words WHERE category='slang_swear' AND pos=? ORDER BY id LIMIT ?",
                [severity, limit],
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM words WHERE category='slang_swear' ORDER BY id LIMIT ?",
                [limit],
            ).fetchall()
        return [dict(r) for r in rows]

    def _category_for_level(self, category: str, level: str, limit: int) -> list[dict]:
        level_idx = CEFR_LEVELS.index(level) if level in CEFR_LEVELS else 3
        levels = CEFR_LEVELS[:level_idx + 1]
        placeholders = ",".join("?" * len(levels))
        rows = self.conn.execute(
            f"SELECT * FROM words WHERE category=? AND cefr IN ({placeholders}) "
            f"ORDER BY id LIMIT ?",
            [category, *levels, limit],
        ).fetchall()
        return [dict(r) for r in rows]


# ── Singleton ─────────────────────────────────────────────────
_instance: WordDB | None = None


def get_db() -> WordDB:
    global _instance
    if _instance is None:
        _instance = WordDB()
    return _instance


def _db_ready() -> bool:
    """Check if DB exists and has data."""
    try:
        return get_db().count() > 0
    except Exception:
        return False


# ── Compatibility wrappers (match wordbank.py API) ──────────────
# These allow coach.py / curriculum.py to import from worddb
# instead of wordbank, with automatic fallback to wordbank
# if the DB hasn't been populated yet.

def phrasal_verbs_for_level(level: str) -> list[dict]:
    if _db_ready():
        rows = get_db().phrasal_verbs(level, limit=100)
        return [{"verb": r["word"], "meaning": r["translation"],
                 "example": r["example"], "level": r["cefr"]} for r in rows]
    from wordbank import phrasal_verbs_for_level as _fb
    return _fb(level)


def collocations_for_level(level: str) -> list[dict]:
    if _db_ready():
        rows = get_db().collocations(level, limit=100)
        return [{"adjective": r["word"].split(" + ")[0] if " + " in r["word"] else r["word"],
                 "noun": r["word"].split(" + ")[1] if " + " in r["word"] else "",
                 "example": r["example"], "level": r["cefr"]} for r in rows]
    from wordbank import collocations_for_level as _fb
    return _fb(level)


def common_errors_for_level(level: str) -> list[dict]:
    if _db_ready():
        rows = get_db().common_errors(level, limit=100)
        return [{"wrong": r["word"], "correct": r["translation"],
                 "type": r["pos"], "explanation": r["example"],
                 "level": r["cefr"]} for r in rows]
    from wordbank import common_errors_for_level as _fb
    return _fb(level)


def idioms_for_level(level: str) -> list[dict]:
    if _db_ready():
        rows = get_db().idioms(level, limit=100)
        return [{"idiom": r["word"], "meaning": r["translation"],
                 "example": r["example"], "level": r["cefr"]} for r in rows]
    from wordbank import idioms_for_level as _fb
    return _fb(level)


def confusing_words_for_level(level: str) -> list[dict]:
    if _db_ready():
        rows = get_db().confusing_words(level, limit=100)
        result = []
        for r in rows:
            parts = r["word"].split(" vs ")
            pair = (parts[0], parts[1]) if len(parts) >= 2 else (r["word"], "")
            examples = tuple(r["example"].split(" | ")) if " | " in r["example"] else (r["example"],)
            result.append({"pair": pair, "explanation": r["translation"],
                           "examples": examples, "level": r["cefr"]})
        return result
    from wordbank import confusing_words_for_level as _fb
    return _fb(level)


def prepositions_for_level(level: str) -> list[dict]:
    if _db_ready():
        rows = get_db().prepositions(level, limit=100)
        return [{"prep": r["word"], "usage": r["translation"],
                 "example": r["example"], "level": r["cefr"]} for r in rows]
    from wordbank import prepositions_for_level as _fb
    return _fb(level)


def vocabulary_for_level(level: str) -> list:
    """Return VocabSet-like dicts from DB, fallback to wordbank."""
    if _db_ready():
        db = get_db()
        themes = db.all_themes(level)
        from wordbank import VocabSet, VocabCard
        result = []
        for theme in themes:
            rows = db.conn.execute(
                "SELECT * FROM words WHERE category='vocab' AND cefr=? AND theme=? ORDER BY id",
                [level, theme],
            ).fetchall()
            cards = [VocabCard(
                word=r["word"], translation=r["translation"], pos=r["pos"],
                example=r["example"], ipa=r["ipa"],
                collocations=tuple(r["collocations"].split("|")) if r["collocations"] else (),
                word_family=tuple(r["word_family"].split("|")) if r["word_family"] else (),
            ) for r in rows]
            result.append(VocabSet(level=level, theme=theme, cards=cards))
        return result
    from wordbank import vocabulary_for_level as _fb
    return _fb(level)


def all_vocab_cards_for_level(level: str) -> list:
    """Return all VocabCards for a level from DB, fallback to wordbank."""
    if _db_ready():
        sets = vocabulary_for_level(level)
        cards = []
        for s in sets:
            cards.extend(s.cards)
        return cards
    from wordbank import all_vocab_cards_for_level as _fb
    return _fb(level)
