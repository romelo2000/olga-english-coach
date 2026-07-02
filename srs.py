"""FSRS-6 spaced repetition algorithm (backward-compatible with SM-2).

Implements the Free Spaced Repetition Scheduler (FSRS-6), trained on
700M+ reviews. Reduces review count by 20-30% vs SM-2 at the same
retention level, with per-card difficulty/stability modeling.

All existing SM-2 fields (repetition, interval, ease_factor) are kept
and updated for backward compatibility with course.py and UI code.
FSRS-specific fields (difficulty, stability) are added alongside.

Quality scale (unchanged, SM-2 compatible): 0-5
  0-2: complete failure (reset interval)
  3: correct but with serious difficulty
  4: correct with some hesitation
  5: perfect recall
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

# ─── FSRS-6 default parameters (21 weights) ───────────────────────────
# Official values from open-spaced-repetition/py-fsrs (FSRS-6).
# Trained on 700M+ reviews. Produces better scheduling than SM-2
# for 99.6% of users.
_FSRS_W = [
    0.212,    # w0:  initial stability (Again)
    1.2931,   # w1:  initial stability (Hard)
    2.3065,   # w2:  initial stability (Good)
    8.2956,   # w3:  initial stability (Easy)
    6.4133,   # w4:  initial difficulty base
    0.8334,   # w5:  initial difficulty multiplier (e^(w5*(rating-1)))
    3.0194,   # w6:  difficulty update delta multiplier
    0.001,    # w7:  difficulty mean reversion weight
    1.8722,   # w8:  recall stability multiplier (used as e^w8)
    0.1666,   # w9:  recall stability — S power (S^(-w9))
    0.796,    # w10: recall stability — retrievability factor
    1.4835,   # w11: lapse stability base
    0.0614,   # w12: lapse stability — D power (D^(-w12))
    0.2629,   # w13: lapse stability — (S+1) power
    1.6483,   # w14: lapse stability — retrievability factor
    0.6014,   # w15: hard penalty
    1.8729,   # w16: easy bonus
    0.5425,   # w17: short-term stability multiplier
    0.0912,   # w18: short-term stability rating offset
    0.0658,   # w19: short-term stability — S power
    0.1542,   # w20: forgetting curve decay
]

_TARGET_RETENTION = 0.9   # schedule reviews when recall drops to 90%
_DECAY = -_FSRS_W[20]     # forgetting curve exponent = -w20
_FACTOR = 0.9 ** (1.0 / _DECAY) - 1  # ensures R(S, S) = 90%


def _quality_to_grade(quality: int) -> int:
    """Map SM-2 quality (0-5) to FSRS grade (1-4)."""
    if quality <= 2:
        return 1  # again
    elif quality == 3:
        return 2  # hard
    elif quality == 4:
        return 3  # good
    return 4      # easy


def _retrievability(days_since: int, stability: float) -> float:
    """Probability of recall after *days_since* days.

    R(t, S) = (1 + FACTOR * t / S) ^ DECAY
    """
    if stability <= 0:
        return 0.0
    elapsed = max(0, days_since)
    return (1 + _FACTOR * elapsed / stability) ** _DECAY


def _next_interval(stability: float, target: float = _TARGET_RETENTION) -> int:
    """Days until recall drops to *target* (default 90%)."""
    if stability <= 0:
        return 1
    interval = (stability / _FACTOR) * (target ** (1.0 / _DECAY) - 1)
    return max(1, min(36500, round(interval)))


def _init_difficulty(grade: int) -> float:
    # Official FSRS-6: D = w4 - e^(w5 * (rating - 1)) + 1
    d = _FSRS_W[4] - math.exp(_FSRS_W[5] * (grade - 1)) + 1
    return max(1.0, min(10.0, d))


def _init_stability(grade: int) -> float:
    return max(0.001, _FSRS_W[grade - 1])


def _update_difficulty(d: float, grade: int) -> float:
    # Official FSRS-6: linear damping + mean reversion
    delta_d = -(_FSRS_W[6] * (grade - 3))
    # Linear damping: (10 - D) * delta / 9
    d_damped = d + (10.0 - d) * delta_d / 9.0
    # Mean reversion towards initial difficulty of Easy
    d_easy = _init_difficulty(4)  # Rating.Easy = 4
    d_next = _FSRS_W[7] * d_easy + (1 - _FSRS_W[7]) * d_damped
    return max(1.0, min(10.0, d_next))


def _stability_after_recall(s: float, d: float, r: float, grade: int) -> float:
    # Official FSRS-6:
    # S' = S * (1 + e^w8 * (11 - D) * S^(-w9) * (e^((1-R)*w10) - 1) * hard_penalty * easy_bonus)
    hard_penalty = _FSRS_W[15] if grade == 2 else 1.0  # Rating.Hard = 2
    easy_bonus = _FSRS_W[16] if grade == 4 else 1.0    # Rating.Easy = 4
    new_s = s * (
        1
        + math.exp(_FSRS_W[8])
        * (11 - d)
        * (s ** (-_FSRS_W[9]))
        * (math.exp((1 - r) * _FSRS_W[10]) - 1)
        * hard_penalty
        * easy_bonus
    )
    return max(0.001, new_s)


def _stability_after_lapse(s: float, d: float, r: float) -> float:
    # Official FSRS-6: min(long-term, short-term)
    # long-term: w11 * D^(-w12) * ((S+1)^w13 - 1) * e^((1-R)*w14)
    # short-term: S / e^(w17 * w18)
    long_term = (
        _FSRS_W[11]
        * (d ** (-_FSRS_W[12]))
        * (((s + 1) ** _FSRS_W[13]) - 1)
        * math.exp((1 - r) * _FSRS_W[14])
    )
    short_term = s / math.exp(_FSRS_W[17] * _FSRS_W[18])
    return max(0.001, min(long_term, short_term))


def _short_term_stability(s: float, grade: int) -> float:
    # Official FSRS-6 same-day review:
    # S' = S * e^(w17 * (rating - 3 + w18)) * S^(-w19)
    # Ensure SInc >= 1 for Good and Easy (grade >= 3)
    sinc = math.exp(_FSRS_W[17] * (grade - 3 + _FSRS_W[18])) * (s ** (-_FSRS_W[19]))
    if grade >= 3:
        sinc = max(sinc, 1.0)
    return max(0.001, s * sinc)


@dataclass
class SRSCard:
    card_id: str
    front: str
    back: str
    example: str = ""
    ipa: str = ""
    collocations: str = ""
    word_family: str = ""
    # ── SM-2 fields (kept for backward compatibility) ──
    repetition: int = 0
    interval: int = 0
    ease_factor: float = 2.5
    next_review: str = field(default_factory=lambda: date.today().isoformat())
    last_review: str = ""
    total_reviews: int = 0
    correct_reviews: int = 0
    # ── FSRS-6 fields (added; defaults = 0 → initialised on first review) ──
    fsrs_difficulty: float = 0.0   # D: 1 (easy) … 10 (hard)
    fsrs_stability: float = 0.0    # S: memory stability in days

    @property
    def is_due(self) -> bool:
        return date.today().isoformat() >= self.next_review

    @property
    def retrievability(self) -> float:
        """Current probability of recall (FSRS forgetting curve)."""
        if self.fsrs_stability <= 0 or not self.last_review:
            return 0.0
        days_since = (date.today() - date.fromisoformat(self.last_review)).days
        return _retrievability(days_since, self.fsrs_stability)

    @property
    def mastery(self) -> float:
        if self.total_reviews == 0:
            return 0.0
        accuracy = self.correct_reviews / max(self.total_reviews, 1)
        if self.fsrs_stability > 0:
            # FSRS-based: stability / 30 days = long-term retention factor
            retention = min(1.0, self.fsrs_stability / 30.0)
        else:
            retention = min(1.0, self.interval / 30)
        return min(1.0, accuracy * retention)


def review_card(card: SRSCard, quality: int) -> SRSCard:
    """Apply FSRS-6 algorithm to a card after a review.

    Backward-compatible: accepts the same 0-5 quality scale as SM-2 and
    updates all SM-2 fields (repetition, interval, ease_factor) in
    addition to FSRS fields (difficulty, stability).

    Args:
        card: The card being reviewed.
        quality: 0-5 rating of recall quality (SM-2 scale).

    Returns:
        Updated card with new interval, ease factor, and next review date.
    """
    quality = max(0, min(5, quality))
    grade = _quality_to_grade(quality)
    card.total_reviews += 1

    # Save previous review date before overwriting
    prev_last_review = card.last_review
    today_str = date.today().isoformat()
    card.last_review = today_str

    # ── FSRS-6 core ──
    is_first_review = card.fsrs_stability <= 0

    if is_first_review:
        card.fsrs_difficulty = _init_difficulty(grade)
        card.fsrs_stability = _init_stability(grade)
    else:
        days_since = (date.today() - date.fromisoformat(prev_last_review)).days if prev_last_review else 0
        r = _retrievability(max(0, days_since), card.fsrs_stability)
        card.fsrs_difficulty = _update_difficulty(card.fsrs_difficulty, grade)

        if days_since < 1:
            # Same-day review: use short-term formula
            card.fsrs_stability = _short_term_stability(card.fsrs_stability, grade)
        elif grade == 1:
            # Lapse (Again)
            card.fsrs_stability = _stability_after_lapse(card.fsrs_stability, card.fsrs_difficulty, r)
        else:
            # Recall (Hard, Good, Easy)
            card.fsrs_stability = _stability_after_recall(
                card.fsrs_stability, card.fsrs_difficulty, r, grade)

    # FSRS-computed interval
    fsrs_interval = _next_interval(card.fsrs_stability)

    # ── Backward-compatible SM-2 fields ──
    if quality < 3:
        card.repetition = 0
    else:
        card.correct_reviews += 1
        card.repetition += 1
    card.interval = fsrs_interval
    # Keep ease_factor updated with SM-2 formula for mastered_cards() compat
    card.ease_factor = max(1.3, card.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))

    next_date = date.today() + timedelta(days=card.interval)
    card.next_review = next_date.isoformat()

    return card


def quality_from_rating(rating: str) -> int:
    """Map a user-friendly rating to SM-2 quality score."""
    mapping = {
        "again": 1,
        "hard": 3,
        "good": 4,
        "easy": 5,
    }
    return mapping.get(rating.lower(), 3)


class SRSManager:
    """Manages a collection of SRS cards."""

    def __init__(self) -> None:
        self.cards: dict[str, SRSCard] = {}

    def add_card(self, card: SRSCard) -> None:
        self.cards[card.card_id] = card

    def add_or_update(self, card_id: str, front: str, back: str, example: str = "") -> SRSCard:
        if card_id not in self.cards:
            self.cards[card_id] = SRSCard(card_id=card_id, front=front, back=back, example=example)
        return self.cards[card_id]

    def review(self, card_id: str, quality: int) -> SRSCard | None:
        card = self.cards.get(card_id)
        if not card:
            return None
        return review_card(card, quality)

    def due_cards(self) -> list[SRSCard]:
        return [card for card in self.cards.values() if card.is_due]

    def due_count(self) -> int:
        return len(self.due_cards())

    def new_cards(self) -> list[SRSCard]:
        return [card for card in self.cards.values() if card.repetition == 0]

    def new_count(self) -> int:
        return len(self.new_cards())

    def learning_cards(self) -> list[SRSCard]:
        return [card for card in self.cards.values() if 0 < card.repetition < 3]

    def mastered_cards(self) -> list[SRSCard]:
        return [card for card in self.cards.values()
                if card.interval >= 21 and card.ease_factor >= 2.5]

    def mastered_count(self) -> int:
        return len(self.mastered_cards())

    def average_mastery(self) -> float:
        if not self.cards:
            return 0.0
        return sum(card.mastery for card in self.cards.values()) / len(self.cards)

    def to_dict(self) -> dict:
        return {
            "cards": [
                {
                    "card_id": c.card_id,
                    "front": c.front,
                    "back": c.back,
                    "example": c.example,
                    "ipa": c.ipa,
                    "collocations": c.collocations,
                    "word_family": c.word_family,
                    "repetition": c.repetition,
                    "interval": c.interval,
                    "ease_factor": c.ease_factor,
                    "next_review": c.next_review,
                    "last_review": c.last_review,
                    "total_reviews": c.total_reviews,
                    "correct_reviews": c.correct_reviews,
                    "fsrs_difficulty": c.fsrs_difficulty,
                    "fsrs_stability": c.fsrs_stability,
                }
                for c in self.cards.values()
            ]
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SRSManager":
        manager = cls()
        for item in data.get("cards", []):
            fsrs_d = item.get("fsrs_difficulty", 0.0)
            fsrs_s = item.get("fsrs_stability", 0.0)
            # ── Migrate old SM-2 cards to FSRS ──
            # If FSRS fields are missing but card has been reviewed,
            # estimate stability from interval and difficulty from ease_factor.
            if fsrs_s <= 0 and item.get("total_reviews", 0) > 0:
                old_interval = item.get("interval", 0)
                if old_interval > 0:
                    # Stability ≈ interval (since R(S,S) = 90% by definition)
                    fsrs_s = max(0.5, old_interval)
                else:
                    fsrs_s = 0.5
                old_ease = item.get("ease_factor", 2.5)
                # Estimate difficulty from ease_factor:
                # ease 2.5 → D ≈ 2.1 (Good), ease 1.5 → D ≈ 7 (hard), ease 2.8 → D ≈ 1 (easy)
                # Linear approximation: D = clamp(10 - ease * 3.2, 1, 10)
                fsrs_d = max(1.0, min(10.0, 10.0 - old_ease * 3.2))
            card = SRSCard(
                card_id=item["card_id"],
                front=item.get("front", ""),
                back=item.get("back", ""),
                example=item.get("example", ""),
                ipa=item.get("ipa", ""),
                collocations=item.get("collocations", ""),
                word_family=item.get("word_family", ""),
                repetition=item.get("repetition", 0),
                interval=item.get("interval", 0),
                ease_factor=item.get("ease_factor", 2.5),
                next_review=item.get("next_review", date.today().isoformat()),
                last_review=item.get("last_review", ""),
                total_reviews=item.get("total_reviews", 0),
                correct_reviews=item.get("correct_reviews", 0),
                fsrs_difficulty=fsrs_d,
                fsrs_stability=fsrs_s,
            )
            manager.cards[card.card_id] = card
        return manager

    def review_session(self, limit: int = 20) -> list[SRSCard]:
        """Get a mixed review session: due cards first, then new cards (interleaving)."""
        due = self.due_cards()[:limit]
        remaining = limit - len(due)
        if remaining > 0:
            due.extend(self.new_cards()[:remaining])
        return due
