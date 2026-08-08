"""Thin LLM provider client (Gemini primary, Groq fallback)."""

from __future__ import annotations

import asyncio
from enum import StrEnum

from google import genai
from groq import Groq

from app.config import get_settings

GEMINI_MODEL = "gemini-2.5-flash"
GROQ_MODEL = "llama-3.3-70b-versatile"


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
    """Call `provider`. If GEMINI is requested and fails, fall back to Groq once.

    Both failures are folded into one message if the fallback also fails --
    a bare `except Exception: return await _complete_groq(...)` used to
    discard the original Gemini error entirely, so a real cause (e.g. quota
    exhaustion) surfaced everywhere downstream (task_nodes.last_error, the
    UI) as nothing but Groq's own generic "Connection error.", which is what
    it raises for something as unrelated as a missing/empty GROQ_API_KEY.
    """
    if provider == LLMProvider.GEMINI:
        try:
            return await _complete_gemini(prompt, temperature=temperature, max_tokens=max_tokens)
        except Exception as gemini_exc:
            print(f"[llm] gemini failed, falling back to groq: {gemini_exc!r}")
            try:
                return await _complete_groq(prompt, temperature=temperature, max_tokens=max_tokens)
            except Exception as groq_exc:
                raise RuntimeError(
                    f"gemini failed ({gemini_exc!r}); groq fallback also failed ({groq_exc!r})"
                ) from groq_exc
    return await _complete_groq(prompt, temperature=temperature, max_tokens=max_tokens)


async def _complete_gemini(prompt: str, *, temperature: float, max_tokens: int | None) -> str:
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    response = await client.aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={"temperature": temperature, "max_output_tokens": max_tokens},
    )
    return response.text


async def _complete_groq(prompt: str, *, temperature: float, max_tokens: int | None) -> str:
    settings = get_settings()
    client = Groq(api_key=settings.groq_api_key)

    def _call() -> str:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    return await asyncio.to_thread(_call)
