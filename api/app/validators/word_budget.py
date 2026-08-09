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


def check(text: str, budget: int, tolerance: float = 0.30) -> ValidationReport:
    """On failure, repair_hint states the exact word delta.

    Widened from 0.12 to 0.30 deliberately (not a bug fix): observed live
    with Gemini's quota exhausted and Groq's llama-3.3-70b-versatile
    fallback carrying every script generation, which misses word budgets
    far more often than Gemini did. A ~12-18% miss now passes instead of
    exhausting the full retry budget every time; a genuinely broken output
    (e.g. 43 words against a 91-word target, roughly 50% under) still fails
    regardless. Revert toward 0.12 once back on Gemini as the primary if the
    looser bar isn't wanted long-term -- this is a real quality/pass-rate
    trade-off, not a correctness fix.
    """
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


def narration_seconds(word_count: int, tone: str) -> int:
    """How long `word_count` words takes to read aloud at `tone`'s pace."""
    return round(word_count / WPM[tone] * 60)


def check_shot_durations(
    actual_by_section: dict[str, int], expected_by_section: dict[str, int], tolerance: float = 0.35
) -> ValidationReport:
    """Real bug found via live testing: a storyboard can cover every script
    section (content.py's own separate coverage check) while its shots'
    durations are completely disconnected from how long that section's
    script actually takes to read aloud -- nothing enforced it, so a
    573-word section (~229s of narration) was seen live getting assigned
    just 44s of shots, producing a finished video roughly a fifth of its
    intended length despite the script itself being correctly sized.
    Tolerance wider than word_budget.check's: shot duration estimates are a
    step further removed from a hard number (word count) than the script
    itself, so some slack is expected even from a well-behaved model.
    """
    failures: list[str] = []
    hints: list[str] = []
    for section_key, expected in expected_by_section.items():
        actual = actual_by_section.get(section_key, 0)
        lower, upper = expected * (1 - tolerance), expected * (1 + tolerance)
        if lower <= actual <= upper:
            continue
        failures.append(f"{section_key}: shots total {actual}s, expected ~{expected}s of narration")
        hints.append(f"{section_key}'s shots should sum to ~{expected}s, not {actual}s")

    if not failures:
        return ValidationReport(ok=True)
    return ValidationReport(ok=False, failures=failures, repair_hint="; ".join(hints))
