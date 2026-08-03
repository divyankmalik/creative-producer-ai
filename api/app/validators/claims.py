"""Claim-grounding checks: flags assertions not traceable to a source in the brief."""

from __future__ import annotations

from app.models import ValidationReport


def extract_claims(text: str) -> list[str]:
    # TODO: pull out factual/verifiable assertions from generated text.
    raise NotImplementedError


def check_grounding(claims: list[str], sources: list[str]) -> ValidationReport:
    # TODO: verify each claim is supported by at least one source; ungrounded
    # claims go into ValidationReport.failures with a repair_hint listing them.
    raise NotImplementedError
