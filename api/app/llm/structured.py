"""Structured (schema-constrained) generation on top of llm/client.py."""

from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel

from app.llm.client import complete

ModelT = TypeVar("ModelT", bound=BaseModel)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

# Seen live from Groq's fallback model: it sometimes "emphasizes" a JSON
# string value with markdown bold, e.g. `"overlay_text": **"Update Your
# Wiki"**,` -- valid-looking output to a human, invalid JSON syntax (the **
# markers sit outside the string, not inside it, so this isn't the model
# adding emphasis to the text content). Cheap to strip before parsing; the
# repair-hint retry loop in agents/base.py is the fallback for anything this
# doesn't catch.
_STRAY_BOLD_STRING_RE = re.compile(r'\*\*(\s*"(?:[^"\\]|\\.)*"\s*)\*\*')


async def generate_structured(
    prompt: str,
    *,
    schema: type[ModelT],
    repair_hint: str | None = None,
) -> ModelT:
    """Call the LLM with `prompt` plus `schema`'s JSON schema, then parse and
    validate the response. `repair_hint` (set by BaseAgent.run after a failed
    validation) is folded into the prompt so the retry fixes the specific
    problem instead of regenerating from scratch.
    """
    full_prompt = _build_prompt(prompt, schema, repair_hint)
    raw = await complete(full_prompt)
    return _parse(raw, schema)


def _build_prompt(prompt: str, schema: type[BaseModel], repair_hint: str | None) -> str:
    schema_json = json.dumps(schema.model_json_schema(), indent=2)
    parts = [
        prompt,
        "\nRespond with ONLY a single JSON object matching this schema exactly. "
        "No prose, no markdown code fences.",
        schema_json,
    ]
    if repair_hint:
        parts.append(f"\nThe previous attempt failed validation: {repair_hint}\nFix this specific issue.")
    return "\n".join(parts)


def _parse(raw: str, schema: type[ModelT]) -> ModelT:
    text = _FENCE_RE.sub("", raw.strip()).strip()
    text = _STRAY_BOLD_STRING_RE.sub(r"\1", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response was not valid JSON: {exc}\nRaw response: {raw!r}") from exc
    return schema.model_validate(data)
