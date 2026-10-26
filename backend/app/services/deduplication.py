from __future__ import annotations
from difflib import SequenceMatcher
from .chat_parser import normalize


def mark_duplicates(tasks: list, threshold: float = 0.82) -> None:
    """Suggest (never delete) duplicates: same deadline date and similar title."""
    for i, t in enumerate(tasks):
        for prev in tasks[:i]:
            if prev.deadline.date != t.deadline.date:
                continue
            ratio = SequenceMatcher(None, normalize(prev.title), normalize(t.title)).ratio()
            if ratio >= threshold:
                t.duplicate_of = prev.id
                break
