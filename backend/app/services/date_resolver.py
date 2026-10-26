"""Deterministic date/time resolution for Telugu / Tenglish / English phrases.

The LLM only extracts phrases. All calendar arithmetic happens here, relative to the
SOURCE MESSAGE timestamp (not the import time). Statuses: resolved, ambiguous,
missing_reference_time, unsupported_phrase, invalid_timestamp, no_deadline.
"""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta

_W = r"[\w\u0C00-\u0C7F]"

TODAY = ["today", "ivala", "ivvala", "ivaala", "eeroju", "ee roju", "eroju", "ఈరోజు", "ఇవాళ", "నేడు"]
TOMORROW = ["tomorrow", "tomorow", "tmrw", "tmr", "repu", "రేపు"]
DAY_AFTER = ["day after tomorrow", "ellundi", "ellundhi", "ఎల్లుండి"]
WEEKDAYS = {
    0: ["monday", "mon", "somavaram", "somavaaram", "సోమవారం"],
    1: ["tuesday", "tue", "tues", "mangalavaram", "mangalavaaram", "మంగళవారం"],
    2: ["wednesday", "wed", "budhavaram", "budhavaaram", "బుధవారం"],
    3: ["thursday", "thu", "thur", "thurs", "guruvaram", "guruvaaram", "గురువారం"],
    4: ["friday", "fri", "shukravaram", "sukravaram", "శుక్రవారం"],
    5: ["saturday", "sat", "shanivaram", "sanivaram", "శనివారం"],
    6: ["sunday", "sun", "aadivaram", "adivaram", "ఆదివారం"],
}
MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
NUMWORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
MORNING = ["morning", "podduna", "poddunna", "udayam", "ఉదయం", "పొద్దున"]
AFTERNOON = ["afternoon", "madhyanam", "madhyahnam", "మధ్యాహ్నం"]
EVENING = ["evening", "sayantram", "sayantranam", "సాయంత్రం"]
NIGHT = ["night", "rathri", "ratri", "రాత్రి"]


@dataclass(frozen=True)
class Deadline:
    status: str
    date: str | None = None            # ISO yyyy-mm-dd
    time: str | None = None            # HH:MM (24h) only when certain
    time_ambiguous: bool = False
    time_candidates: tuple = ()
    notes: tuple = ()


def _norm(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s)).strip().casefold()


def _has(text: str, key: str) -> bool:
    return re.search(rf"(?<!{_W}){re.escape(key)}(?!{_W})", text) is not None


def _any(text: str, keys) -> bool:
    return any(_has(text, k) for k in keys)


def _daypart(text: str):
    found = [n for n, ks in (("morning", MORNING), ("afternoon", AFTERNOON),
                             ("evening", EVENING), ("night", NIGHT)) if _any(text, ks)]
    return found[0] if len(found) == 1 else (None if not found else "conflict")


def _parse_time(phrase: str, context: str):
    """Return (time|None, ambiguous, candidates, notes, ok)."""
    p = _norm(phrase)
    if not p:
        return None, False, (), (), True
    if _any(p, ["midnight"]):
        return "00:00", False, (), (), True
    if _any(p, ["noon", "madhyahnam"]) and not re.search(r"\d", p):
        return "12:00", False, (), (), True
    m = re.search(r"(\d{1,2})(?:[:.](\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?(?!\d)", p)
    if not m:
        return None, False, (), ("Unsupported time phrase.",), False
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if h > 23 or mi > 59:
        return None, False, (), ("Invalid clock time.",), False
    if ap:
        pm = ap.startswith("p")
        if not 1 <= h <= 12:
            return None, False, (), ("Invalid 12-hour time.",), False
        return f"{(h % 12) + (12 if pm else 0):02d}:{mi:02d}", False, (), (), True
    if h == 0 or h >= 13:
        return f"{h:02d}:{mi:02d}", False, (), (), True
    # 1..12 without AM/PM: only a single, consistent day-part word can settle it
    part = _daypart(p)
    if part is None:
        part = _daypart(_norm(context))
    resolved = None
    if part == "morning" and 1 <= h <= 11:
        resolved = h
    elif part == "afternoon" and (h == 12 or 1 <= h <= 6):
        resolved = 12 if h == 12 else h + 12
    elif part in ("evening", "night") and 4 <= h <= 11:
        resolved = h + 12
    if resolved is not None:
        return f"{resolved:02d}:{mi:02d}", False, (), (f"AM/PM inferred from '{part}' wording.",), True
    c1, c2 = f"{h % 12:02d}:{mi:02d}", f"{(h % 12) + 12:02d}:{mi:02d}"
    return None, True, tuple(sorted((c1, c2))), ("AM or PM is unclear.",), True


def _parse_date(phrase: str, ref: datetime | None):
    """Return (date|None, status, notes)."""
    p = _norm(phrase)
    if not p:
        return None, "no_deadline", ()
    relative = None
    if _any(p, DAY_AFTER):
        relative = 2
    elif _any(p, TOMORROW):
        relative = 1
    elif _any(p, TODAY):
        relative = 0
    if relative is not None:
        if ref is None:
            return None, "missing_reference_time", ("Message has no valid timestamp.",)
        d = ref.date() + timedelta(days=relative)
        if relative >= 1 and ref.hour < 4:
            return d, "ambiguous", ("Message sent after midnight; the relative day may mean something different.",)
        return d, "resolved", ()
    m = re.search(r"\bin (\d{1,2}|one|two|three|four|five|six|seven) days?\b", p) or \
        re.search(r"(?<![\w])(\d{1,2}) (?:rojullo|rojulalo|రోజుల్లో)", p)
    if m:
        if ref is None:
            return None, "missing_reference_time", ("Message has no valid timestamp.",)
        n = NUMWORDS.get(m.group(1)) or int(m.group(1))
        return ref.date() + timedelta(days=n), "resolved", ()
    for wd, keys in WEEKDAYS.items():
        if _any(p, keys):
            if ref is None:
                return None, "missing_reference_time", ("Message has no valid timestamp.",)
            delta = (wd - ref.weekday()) % 7 or 7
            notes, status = (), "resolved"
            if _has(p, "next"):
                status, notes = "ambiguous", ("'next' can mean the coming day or the one after.",)
            return ref.date() + timedelta(days=delta), status, notes
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s*(?:of\s+)?([a-z]{3})[a-z]*(?:[ ,]+(\d{4}))?", p)
    m2 = re.search(r"([a-z]{3})[a-z]*\s+(\d{1,2})(?:st|nd|rd|th)?(?:[ ,]+(\d{4}))?", p)
    day = mon = yr = None
    if m and m.group(2) in MONTHS:
        day, mon, yr = int(m.group(1)), MONTHS[m.group(2)], m.group(3)
    elif m2 and m2.group(1) in MONTHS:
        day, mon, yr = int(m2.group(2)), MONTHS[m2.group(1)], m2.group(3)
    amb = False
    if mon is None:
        n = re.search(r"(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?", p)
        if not n:
            return None, "unsupported_phrase", ("Unsupported date phrase.",)
        a, b, yr = int(n.group(1)), int(n.group(2)), n.group(3)
        if a > 12:
            day, mon = a, b
        elif b > 12:
            day, mon = b, a
        else:
            day, mon, amb = a, b, a != b
    if yr:
        y = int(yr) + (2000 if int(yr) < 100 else 0)
    elif ref is None:
        return None, "missing_reference_time", ("Year missing and message has no timestamp.",)
    else:
        y = ref.year
    try:
        d = date(y, mon, day)
    except ValueError:
        return None, "invalid_timestamp", ("Not a valid calendar date.",)
    notes = []
    if not yr and ref is not None and d < ref.date():
        try:
            d = date(y + 1, mon, day)
            notes.append("Year assumed to be next year.")
        except ValueError:
            return None, "invalid_timestamp", ("Not a valid calendar date.",)
    if amb:
        return d, "ambiguous", ("Numeric date could be day/month or month/day; assumed day first.",) + tuple(notes)
    return d, "resolved", tuple(notes)


def resolve_deadline(date_phrase: str | None, time_phrase: str | None,
                     reference: datetime | None, context_text: str = "") -> Deadline:
    d, d_status, d_notes = _parse_date(date_phrase or "", reference)
    t, t_amb, cands, t_notes, t_ok = _parse_time(time_phrase or "", context_text)
    if not (date_phrase or "").strip() and not (time_phrase or "").strip():
        return Deadline("no_deadline")
    notes = tuple(d_notes) + tuple(t_notes)
    if not t_ok:
        return Deadline("unsupported_phrase", d.isoformat() if d else None, None, False, (), notes)
    if d_status == "no_deadline":  # time but no date
        return Deadline("ambiguous", None, t, t_amb, cands, notes + ("No date phrase found.",))
    if d_status in ("missing_reference_time", "unsupported_phrase", "invalid_timestamp"):
        return Deadline(d_status, None, t, t_amb, cands, notes)
    status = "ambiguous" if (d_status == "ambiguous" or t_amb) else "resolved"
    return Deadline(status, d.isoformat(), t, t_amb, cands, notes)
