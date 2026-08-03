"""Thin LLM provider client (Gemini primary, Groq fallback)."""

from __future__ import annotations

from enum import StrEnum


class LLMProvider(StrEnum):
    GEMINI = "gemini"
    GROQ = "groq"


async def complete(
    prompt: str,
    *,
    provider: LLMProvider = LLMProvider.GEMINI,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> str:
    # TODO: call the given provider's chat/completion API and return raw text.
    raise NotImplementedError
