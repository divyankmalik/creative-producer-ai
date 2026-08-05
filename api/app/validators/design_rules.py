"""Design constraint checks: contrast ratio and overlay text density."""

from __future__ import annotations

from app.models import ValidationReport

MAX_OVERLAY_WORDS = 4
MIN_CONTRAST_RATIO = 4.5  # WCAG AA for normal text


def _linearize(channel: float) -> float:
    return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_color: str) -> float:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))
    r, g, b = _linearize(r), _linearize(g), _linearize(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(foreground_hex: str, background_hex: str) -> float:
    l1 = _relative_luminance(foreground_hex)
    l2 = _relative_luminance(background_hex)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def check_contrast(foreground_hex: str, background_hex: str) -> ValidationReport:
    ratio = contrast_ratio(foreground_hex, background_hex)
    if ratio >= MIN_CONTRAST_RATIO:
        return ValidationReport(ok=True)

    return ValidationReport(
        ok=False,
        failures=[
            f"contrast ratio {ratio:.2f}:1 between {foreground_hex} and {background_hex} "
            f"is below WCAG AA ({MIN_CONTRAST_RATIO}:1)"
        ],
        repair_hint=(
            f"Increase contrast between {foreground_hex} and {background_hex} to at least "
            f"{MIN_CONTRAST_RATIO}:1 (currently {ratio:.2f}:1) -- darken or lighten one of them."
        ),
    )


def check_overlay_word_count(overlay_text: str) -> ValidationReport:
    word_count = len(overlay_text.split())
    if word_count <= MAX_OVERLAY_WORDS:
        return ValidationReport(ok=True)

    return ValidationReport(
        ok=False,
        failures=[f"overlay text has {word_count} words, exceeds the {MAX_OVERLAY_WORDS}-word cap: {overlay_text!r}"],
        repair_hint=f"Cut '{overlay_text}' down to {MAX_OVERLAY_WORDS} words or fewer.",
    )
