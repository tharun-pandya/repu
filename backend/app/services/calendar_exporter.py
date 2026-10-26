"""Standards-oriented .ics writer (RFC 5545). Timed events use floating local time (shown at the same wall-clock time in the user's calendar)."""
from __future__ import annotations
import hashlib
import re
from datetime import date, datetime, time, timedelta, UTC

from ..errors import export_rejected, invalid_date

_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def _esc(s: str) -> str:
    s = _CTRL.sub("", s).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return s.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")


def _fold(line: str) -> str:
    out, cur = [], b""
    limit = 75
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > limit:
            out.append(cur.decode("utf-8"))
            cur, limit = b"", 74  # continuation lines start with a space
        cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def validate_export_tasks(tasks: list[dict]) -> None:
    if not tasks:
        raise export_rejected("No tasks selected.")
    for i, t in enumerate(tasks, 1):
        for flag in ("task_confirmed", "owner_confirmed", "deadline_confirmed", "export_approved"):
            if t.get(flag) is not True:
                raise export_rejected(f"Task {i} is missing confirmation: {flag}.")
        if not str(t.get("title", "")).strip():
            raise export_rejected(f"Task {i} has no title.")


def build_ics(tasks: list[dict], default_minutes: int = 30, now: datetime | None = None) -> tuple[bytes, int]:
    validate_export_tasks(tasks)
    stamp = (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Repu//Task Export 0.1//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    seen: dict[str, int] = {}
    for t in tasks:
        try:
            d = date.fromisoformat(str(t.get("date")))
        except (TypeError, ValueError):
            raise invalid_date("A selected task has no valid deadline date.")
        tm = t.get("time")
        title = str(t["title"]).strip()[:200]
        uid_seed = f"{title}|{d.isoformat()}|{tm or ''}"
        h = hashlib.sha256(uid_seed.encode("utf-8")).hexdigest()[:24]
        seen[h] = seen.get(h, 0) + 1
        uid = f"{h}{'-' + str(seen[h]) if seen[h] > 1 else ''}@repu.local"
        lines += ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}", f"SUMMARY:{_esc(title)}"]
        if tm:
            try:
                hh, mm = (int(x) for x in str(tm).split(":")[:2])
                start = datetime.combine(d, time(hh, mm))
            except (ValueError, TypeError):
                raise invalid_date("A selected task has an invalid time.")
            end = start + timedelta(minutes=default_minutes)
            lines += [f"DTSTART:{start:%Y%m%dT%H%M%S}", f"DTEND:{end:%Y%m%dT%H%M%S}"]
        else:
            lines += [f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"DTEND;VALUE=DATE:{d + timedelta(days=1):%Y%m%d}"]
        rm = t.get("reminder_minutes")
        if isinstance(rm, int) and 0 <= rm <= 10080:
            lines += ["BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Repu reminder", f"TRIGGER:-PT{rm}M", "END:VALARM"]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return ("\r\n".join(_fold(l) for l in lines) + "\r\n").encode("utf-8"), len(tasks)
