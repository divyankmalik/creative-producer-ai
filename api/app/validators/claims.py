"""Claim-grounding checks: flags assertions not traceable to a source in the brief.

Grounding is checked via lexical keyword overlap, not semantic entailment —
cheap and deterministic, at the cost of missing paraphrased grounding.
"""

from __future__ import annotations

import re

from app.models import ValidationReport

_MIN_CLAIM_WORDS = 6
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "of", "to", "in", "on", "for",
    "and", "or", "that", "this", "it", "as", "with", "by", "at", "from", "into",
    "their", "them", "than", "will", "can", "has", "have", "had", "its", "over",
}


def extract_claims(text: str) -> list[str]:
    """Split into sentences and keep the ones that read as factual assertions
    (long enough, and not a question).
    """
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    return [s for s in sentences if not s.endswith("?") and len(s.split()) >= _MIN_CLAIM_WORDS]


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def check_grounding(claims: list[str], sources: list[str], min_overlap: int = 1) -> ValidationReport:
    """A claim is grounded if it shares at least `min_overlap` distinctive
    keywords with at least one source.
    """
    if not claims:
        return ValidationReport(ok=True)

    source_keywords = [_keywords(source) for source in sources]
    ungrounded = [
        claim
        for claim in claims
        if not any(len(_keywords(claim) & sk) >= min_overlap for sk in source_keywords)
    ]

    if not ungrounded:
        return ValidationReport(ok=True)

    return ValidationReport(
        ok=False,
        failures=[f"{len(ungrounded)} of {len(claims)} claim(s) not traceable to any source"],
        repair_hint=(
            "Remove or re-source these claims, they don't match any provided source: "
            + " | ".join(ungrounded)
        ),
    )
