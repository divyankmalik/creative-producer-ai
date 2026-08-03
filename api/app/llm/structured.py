"""Structured (schema-constrained) generation on top of llm/client.py."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


async def generate_structured(
    prompt: str,
    *,
    schema: type[ModelT],
    repair_hint: str | None = None,
) -> ModelT:
    # TODO: call llm/client.py, parse/validate the response against `schema`,
    # folding `repair_hint` into the prompt when retrying after a validation failure.
    raise NotImplementedError
