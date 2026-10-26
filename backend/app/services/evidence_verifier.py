"""Deterministic check that a model-supplied quote really appears in the source message."""
from __future__ import annotations
from .chat_parser import normalize

VERIFIED_EXACT, VERIFIED_NORMALIZED, UNVERIFIED, MISSING = (
    "verified_exact", "verified_normalized", "unverified", "missing")


def verify_evidence(quote: str | None, source_text: str | None) -> str:
    if not quote or not quote.strip() or source_text is None:
        return MISSING
    if quote in source_text:
        return VERIFIED_EXACT
    q = normalize(quote)
    if q and q in normalize(source_text):
        return VERIFIED_NORMALIZED
    return UNVERIFIED


def is_verified(status: str) -> bool:
    return status in (VERIFIED_EXACT, VERIFIED_NORMALIZED)
