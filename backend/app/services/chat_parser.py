"""Deterministic WhatsApp .txt export parser (Android + iOS variants)."""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

from ..errors import unsupported_encoding, no_messages

_DATE = r"(\d{1,4}[/.\-]\d{1,2}[/.\-]\d{1,4})"
_TIME = r"(\d{1,2}[:.]\d{2}(?:[:.]\d{2})?)\s*([APap]\.?[Mm]\.?)?"
_ANDROID = re.compile(rf"^[\u200e\u200f\u202a]*{_DATE},?\s+{_TIME}\s+-\s+(.*)$")
_IOS = re.compile(rf"^[\u200e\u200f\u202a]*\[{_DATE},?\s+{_TIME}\]\s+(.*)$")
_SENDER = re.compile(r"^([^:]{1,60}?):\s(.*)$", re.DOTALL)
_SYSTEM = re.compile(
    r"end-to-end encrypted|created (this )?group|you were added|changed the (group )?(subject|description|icon)|"
    r"security code changed|joined using|left$|was added|were added|removed|changed their phone number|"
    r"this message was deleted|you deleted this message|messages and calls", re.I)
_ATTACH = re.compile(r"^(<media omitted>|<attached:.*>|(image|video|audio|document|sticker|gif|contact card) omitted|\(file attached\))$", re.I)


@dataclass(frozen=True)
class ChatMessage:
    id: str
    order: int
    raw_timestamp: str | None
    timestamp: datetime | None  # naive, chat-local wall clock
    sender: str | None
    text: str            # original, never altered
    normalized: str      # for matching only
    is_system: bool = False
    is_attachment: bool = False
    warnings: tuple = ()


@dataclass
class ParseResult:
    messages: list
    warnings: list = field(default_factory=list)
    skipped_system: int = 0
    skipped_attachments: int = 0
    unparsed_lines: int = 0
    date_order: str = "dmy"

    @property
    def usable(self):
        return [m for m in self.messages if not m.is_system and not m.is_attachment]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip().casefold()


def decode_bytes(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")) or (len(data) > 4 and data[1:2] == b"\x00" and data[3:4] == b"\x00"):
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError:
            raise unsupported_encoding()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise unsupported_encoding()


def _split_date(d: str):
    return [int(p) for p in re.split(r"[/.\-]", d)]


def detect_date_order(date_strs: list, requested: str = "auto"):
    """Return (order, warning|None). order is 'dmy', 'mdy' or 'ymd'."""
    if requested in ("dmy", "mdy"):
        return requested, None
    first = [_split_date(d) for d in date_strs]
    if date_strs and len(re.split(r"[/.\-]", date_strs[0])[0]) == 4:
        return "ymd", None
    if any(p[0] > 12 for p in first):
        return "dmy", None
    if any(p[1] > 12 for p in first):
        return "mdy", None
    return "dmy", "DATE_ORDER_AMBIGUOUS: every date fits day-first and month-first; assumed day-first. Re-import with date order 'mdy' if wrong."


def _to_datetime(d: str, t: str, ampm: str | None, order: str):
    p = _split_date(d)
    if order == "ymd":
        y, m, day = p
    elif order == "mdy":
        m, day, y = p
    else:
        day, m, y = p
    if y < 100:
        y += 2000
    tp = [int(x) for x in re.split(r"[:.]", t)]
    h, mi, s = tp[0], tp[1], (tp[2] if len(tp) > 2 else 0)
    if ampm:
        pm = ampm.lower().startswith("p")
        if not 1 <= h <= 12:
            raise ValueError("bad 12h")
        h = (h % 12) + (12 if pm else 0)
    return datetime(y, m, day, h, mi, s)


def parse_chat(text: str, date_order: str = "auto", max_messages: int = 5000) -> ParseResult:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    heads = []  # (line_idx, date, time, ampm, body, raw)
    for i, ln in enumerate(lines):
        mt = _ANDROID.match(ln) or _IOS.match(ln)
        if mt:
            heads.append((i, mt.group(1), mt.group(2), mt.group(3), mt.group(4), ln[: mt.start(4)].strip()))
    res = ParseResult(messages=[])
    if not heads:
        raise no_messages()
    order, warn = detect_date_order([h[1] for h in heads], date_order)
    res.date_order = order
    if warn:
        res.warnings.append(warn)
    blocks = []
    for n, h in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        body = [h[4]] + lines[h[0] + 1:end]
        blocks.append((h, "\n".join(body).rstrip("\n")))
    res.unparsed_lines = sum(1 for i in range(heads[0][0]) if lines[i].strip())
    if res.unparsed_lines:
        res.warnings.append(f"{res.unparsed_lines} line(s) before the first timestamp were ignored.")
    bad_ts = 0
    for order_no, (h, body) in enumerate(blocks):
        if order_no >= max_messages:
            res.warnings.append(f"Import truncated at {max_messages} messages.")
            break
        _, d, t, ap, _, raw = h
        warns = []
        try:
            ts = _to_datetime(d, t, ap, order)
        except ValueError:
            ts = None
            bad_ts += 1
            warns.append("INVALID_TIMESTAMP")
        sender, msg = None, body
        sm = _SENDER.match(body)
        is_system = False
        if sm:
            sender, msg = sm.group(1).strip(), sm.group(2)
            if re.fullmatch(r"(this message was deleted|you deleted this message)", msg.strip(), re.I):
                is_system = True
        elif _SYSTEM.search(body):
            is_system = True
        is_att = bool(_ATTACH.match(msg.strip()))
        res.skipped_system += is_system
        res.skipped_attachments += is_att
        res.messages.append(ChatMessage(
            id=f"m{order_no + 1:05d}", order=order_no, raw_timestamp=raw, timestamp=ts,
            sender=sender, text=msg, normalized=normalize(msg), is_system=is_system,
            is_attachment=is_att, warnings=tuple(warns)))
    if bad_ts:
        res.warnings.append(f"{bad_ts} message(s) had invalid timestamps; relative dates in them cannot be resolved.")
    if res.skipped_attachments:
        res.warnings.append("Images, audio, video and documents are not analysed in this release.")
    return res
