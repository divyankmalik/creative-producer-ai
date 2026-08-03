"""Word-count budgeting for scripts: seconds -> word targets, and enforcement."""

from __future__ import annotations

from app.models import ValidationReport

WPM = {"conversational": 150, "educational": 135, "energetic": 170}

HOOK_SHARE = 0.08
OUTRO_SHARE = 0.06


def allocate(total_seconds: int, section_weights: dict[str, float], tone: str) -> dict[str, int]:
    """Hook 8%, outro 6%, body split by weight."""
    wpm = WPM[tone]
    total_words = (total_seconds / 60) * wpm

    hook_words = round(total_words * HOOK_SHARE)
    outro_words = round(total_words * OUTRO_SHARE)
    body_words = total_words - hook_words - outro_words

    weight_sum = sum(section_weights.values())
    allocation = {"hook": hook_words, "outro": outro_words}
    for section, weight in section_weights.items():
        allocation[section] = round(body_words * (weight / weight_sum))

    return allocation


def check(text: str, budget: int, tolerance: float = 0.12) -> ValidationReport:
    """On failure, repair_hint states the exact word delta."""
    word_count = len(text.split())
    lower_bound = budget * (1 - tolerance)
    upper_bound = budget * (1 + tolerance)

    if lower_bound <= word_count <= upper_bound:
        return ValidationReport(ok=True)

    delta = word_count - budget
    direction = "over" if delta > 0 else "under"
    return ValidationReport(
        ok=False,
        failures=[
            f"word count {word_count} is outside the ±{tolerance:.0%} band "
            f"[{lower_bound:.0f}, {upper_bound:.0f}] for budget {budget}"
        ],
        repair_hint=f"{'Cut' if delta > 0 else 'Add'} {abs(delta)} words ({direction} budget by {abs(delta)}).",
    )
