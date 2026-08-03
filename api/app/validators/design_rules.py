"""Design constraint checks: contrast ratio and overlay text density."""

from __future__ import annotations

from app.models import ValidationReport

MAX_OVERLAY_WORDS = 4
MIN_CONTRAST_RATIO = 4.5  # WCAG AA for normal text


def contrast_ratio(foreground_hex: str, background_hex: str) -> float:
    # TODO: compute WCAG relative-luminance contrast ratio between two hex colors.
    raise NotImplementedError


def check_contrast(foreground_hex: str, background_hex: str) -> ValidationReport:
    # TODO: use contrast_ratio() against MIN_CONTRAST_RATIO.
    raise NotImplementedError


def check_overlay_word_count(overlay_text: str) -> ValidationReport:
    # TODO: enforce overlay_text has at most MAX_OVERLAY_WORDS words.
    raise NotImplementedError
