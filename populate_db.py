"""Populate SQLite word database with 4000+ words from all sources.

Run: python3 populate_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from worddb import WordDB, CEFR_LEVELS
from wordbank import (
    VocabCard, VocabSet, VOCABULARY_SETS,
    PHRASAL_VERBS, COLOCATIONS, COMMON_ERRORS,
    IDIOMS, CONFUSING_WORDS, PREPOSITIONS,
)


def vocab_sets_to_rows() -> list[dict]:
    rows = []
    for level, vsets in VOCABULARY_SETS.items():
        for vset in vsets:
            for card in vset.cards:
                rows.append({
                    "word": card.word, "translation": card.translation,
                    "pos": card.pos, "example": card.example,
                    "ipa": card.ipa,
                    "collocations": "|".join(card.collocations) if card.collocations else "",
                    "word_family": "|".join(card.word_family) if card.word_family else "",
                    "cefr": level, "theme": vset.theme,
                    "source": "wordbank", "category": "vocab",
                })
    return rows


def phrasal_verbs_to_rows() -> list[dict]:
    return [{"word": pv["verb"], "translation": pv.get("meaning", ""),
             "pos": "phrasal verb", "example": pv.get("example", ""),
             "ipa": "", "collocations": "", "word_family": "",
             "cefr": pv.get("level", "A2"), "theme": "phrasal verbs",
             "source": "wordbank", "category": "phrasal_verb"} for pv in PHRASAL_VERBS]


def collocations_to_rows() -> list[dict]:
    return [{"word": f"{c['adjective']} + {c['noun']}", "translation": "",
             "pos": "collocation", "example": c.get("example", ""),
             "ipa": "", "collocations": "", "word_family": "",
             "cefr": c.get("level", "A2"), "theme": "collocations",
             "source": "wordbank", "category": "collocation"} for c in COLOCATIONS]


def common_errors_to_rows() -> list[dict]:
    return [{"word": e["wrong"], "translation": e["correct"],
             "pos": e.get("type", "grammar"), "example": e.get("explanation", ""),
             "ipa": "", "collocations": "", "word_family": "",
             "cefr": e.get("level", "A2"), "theme": "common errors",
             "source": "wordbank", "category": "common_error"} for e in COMMON_ERRORS]


def idioms_to_rows() -> list[dict]:
    return [{"word": i["idiom"], "translation": i.get("meaning", ""),
             "pos": "idiom", "example": i.get("example", ""),
             "ipa": "", "collocations": "", "word_family": "",
             "cefr": i.get("level", "B1"), "theme": "idioms",
             "source": "wordbank", "category": "idiom"} for i in IDIOMS]


def confusing_words_to_rows() -> list[dict]:
    rows = []
    for cw in CONFUSING_WORDS:
        pair = cw.get("pair", ("", ""))
        word = f"{pair[0]} vs {pair[1]}" if isinstance(pair, (list, tuple)) else str(pair)
        examples = cw.get("examples", ("", ""))
        example_text = " | ".join(examples) if isinstance(examples, (list, tuple)) else str(examples)
        rows.append({"word": word, "translation": cw.get("explanation", ""),
                      "pos": "confusing pair", "example": example_text,
                      "ipa": "", "collocations": "", "word_family": "",
                      "cefr": cw.get("level", "B1"), "theme": "confusing words",
                      "source": "wordbank", "category": "confusing_word"})
    return rows


def prepositions_to_rows() -> list[dict]:
    return [{"word": p["prep"], "translation": p.get("usage", ""),
             "pos": "preposition", "example": p.get("example", ""),
             "ipa": "", "collocations": "", "word_family": "",
             "cefr": p.get("level", "A1"), "theme": "prepositions",
             "source": "wordbank", "category": "preposition"} for p in PREPOSITIONS]


def ext_vocab_to_rows() -> list[dict]:
    rows = []
    try:
        from wordbank_ext import A1_EXTRA, A2_EXTRA
        for vset in A1_EXTRA + A2_EXTRA:
            for card in vset.cards:
                rows.append({"word": card.word, "translation": card.translation,
                             "pos": card.pos, "example": card.example,
                             "ipa": card.ipa,
                             "collocations": "|".join(card.collocations) if card.collocations else "",
                             "word_family": "|".join(card.word_family) if card.word_family else "",
                             "cefr": vset.level, "theme": vset.theme,
                             "source": "wordbank_ext", "category": "vocab"})
    except ImportError:
        pass
    return rows


def ext2_vocab_to_rows() -> list[dict]:
    rows = []
    try:
        from wordbank_ext2 import B2_EXTRA, MARITIME_ENGLISH, SLANG_SWEAR
        for vset in B2_EXTRA:
            for card in vset.cards:
                rows.append({"word": card.word, "translation": card.translation,
                             "pos": card.pos, "example": card.example,
                             "ipa": card.ipa,
                             "collocations": "|".join(card.collocations) if card.collocations else "",
                             "word_family": "|".join(card.word_family) if card.word_family else "",
                             "cefr": vset.level, "theme": vset.theme,
                             "source": "wordbank_ext2", "category": "vocab"})
        for m in MARITIME_ENGLISH:
            rows.append({"word": m["term"], "translation": m["meaning"],
                         "pos": "maritime", "example": m.get("example", ""),
                         "ipa": "", "collocations": "", "word_family": "",
                         "cefr": "B1", "theme": m.get("category", "maritime"),
                         "source": "IMO_SMCP", "category": "maritime"})
        for s in SLANG_SWEAR:
            rows.append({"word": s["term"], "translation": s["meaning"],
                         "pos": s.get("severity", "mild"), "example": s.get("example", ""),
                         "ipa": "", "collocations": "", "word_family": "",
                         "cefr": "B1", "theme": "slang & swear",
                         "source": "slang_list", "category": "slang_swear"})
    except ImportError:
        pass
    return rows


def freq_words_to_rows() -> list[dict]:
    """Import frequency-based words from freq_words*.py (NGSL/Oxford 3000)."""
    rows = []
    importers = []
    try:
        from freq_words import FREQUENCY_WORDS
        importers.append(("freq_words", FREQUENCY_WORDS))
    except ImportError:
        pass
    try:
        from freq_words2 import get_frequency_words2
        importers.append(("freq_words2", get_frequency_words2()))
    except ImportError:
        pass
    try:
        from freq_words3 import get_frequency_words3
        importers.append(("freq_words3", get_frequency_words3()))
    except ImportError:
        pass
    try:
        from freq_words4 import get_frequency_words4
        importers.append(("freq_words4", get_frequency_words4()))
    except ImportError:
        pass

    for src_name, fw_list in importers:
        for fw in fw_list:
            rows.append({"word": fw[0], "translation": fw[1],
                         "pos": fw[2], "example": fw[3],
                         "ipa": "", "collocations": "", "word_family": "",
                         "cefr": fw[4] if len(fw) > 4 else "A1",
                         "theme": "frequency list",
                         "source": src_name, "category": "vocab"})
    return rows


def main() -> None:
    db = WordDB()

    # Clear existing data
    db.conn.execute("DELETE FROM words")
    db.conn.commit()

    all_rows: list[dict] = []
    sources = [
        ("VOCABULARY_SETS", vocab_sets_to_rows),
        ("PHRASAL_VERBS", phrasal_verbs_to_rows),
        ("COLOCATIONS", collocations_to_rows),
        ("COMMON_ERRORS", common_errors_to_rows),
        ("IDIOMS", idioms_to_rows),
        ("CONFUSING_WORDS", confusing_words_to_rows),
        ("PREPOSITIONS", prepositions_to_rows),
        ("EXT_VOCAB", ext_vocab_to_rows),
        ("EXT2_VOCAB", ext2_vocab_to_rows),
        ("FREQ_WORDS", freq_words_to_rows),
    ]

    for name, fn in sources:
        rows = fn()
        all_rows.extend(rows)
        print(f"  {name}: {len(rows)} rows")

    # Deduplicate by word+category
    seen = set()
    unique = []
    for r in all_rows:
        key = (r["word"].lower(), r["category"])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    count = db.bulk_insert(unique)
    print(f"\nInserted {count} unique rows (from {len(all_rows)} total)")

    # Stats
    total = db.count()
    print(f"Total in DB: {total}")
    by_level = db.count_by_level()
    for lvl in CEFR_LEVELS:
        print(f"  {lvl}: {by_level.get(lvl, 0)} vocab words")
    cats = db.conn.execute(
        "SELECT category, COUNT(*) FROM words GROUP BY category ORDER BY COUNT(*) DESC"
    ).fetchall()
    print("\nBy category:")
    for cat, cnt in cats:
        print(f"  {cat}: {cnt}")

    db.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
