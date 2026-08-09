"""Tests for llm/structured.py's response parsing."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.llm.structured import _parse


class Concept(BaseModel):
    name: str
    overlay_text: str


def test_parse_strips_code_fences() -> None:
    raw = '```json\n{"name": "a", "overlay_text": "b"}\n```'
    result = _parse(raw, Concept)
    assert result == Concept(name="a", overlay_text="b")


def test_parse_strips_stray_markdown_bold_around_string_value() -> None:
    """Regression test for a real failure seen live from Groq's fallback
    model: it sometimes wraps a JSON string value in markdown bold --
    `**"text"**` -- which is invalid JSON syntax since the ** markers sit
    outside the string, not inside it (not the model emphasizing the text
    content, just breaking JSON around it).
    """
    raw = '{"name": "a", "overlay_text": **"Update Your Wiki"**}'
    result = _parse(raw, Concept)
    assert result.overlay_text == "Update Your Wiki"


def test_parse_still_raises_on_genuinely_invalid_json() -> None:
    with pytest.raises(ValueError, match="not valid JSON"):
        _parse("{not json at all", Concept)
