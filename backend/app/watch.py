"""Overnight mode: drop WhatsApp .txt exports into a folder, run this, read the brief in the morning.

    python -m backend.app.watch ~/repu-inbox            # keeps watching (Ctrl+C to stop)
    python -m backend.app.watch ~/repu-inbox --once     # process what is there, then exit

It writes `<folder>/repu-briefs/brief-<name>.md` (a human-readable task list). It NEVER creates calendar
files or reminders: confirmation stays in the app. Briefs contain task titles and quotes from YOUR chat and are
written to YOUR disk, so keep the folder private. Only SHA-256 hashes of processed files are remembered.
"""
from __future__ import annotations

import argparse
import hashlib
import time
from pathlib import Path

from .config import load_settings
from .errors import AppError
from .services.brief_service import ai_summary, build_brief
from .services.chat_parser import decode_bytes, parse_chat
from .services.extraction_service import ExtractionService
from .services.llm_client import OllamaClient


def render_brief(name: str, tasks: list, brief: dict, skipped: int) -> str:
    out = [f"# Repu morning brief: {name}", "", f"**{brief['headline']}**", ""]
    if brief["ai_lines"]:
        out += [f"> {x}" for x in brief["ai_lines"]] + [f"> _({brief['ai_note']})_", ""]
    out += ["## Candidate tasks (suggestions only, confirm in the Repu app before exporting)", ""]
    for t in tasks:
        d = t.deadline
        when = f"{d.date or 'no date'}" + (f" {d.time}" if d.time else (" (AM/PM unclear)" if d.time_ambiguous else ""))
        why = "; ".join(t.confirmation_reasons) or "ready to confirm"
        out += [f"- **{t.title}**: {when} _[{t.evidence_status}]_", f"  - source: \u201c{t.evidence_quote}\u201d", f"  - review: {why}"]
    if not tasks:
        out.append("_No tasks found._")
    if skipped:
        out += ["", f"_{skipped} batch(es) could not be analysed; retry with a smaller MAX_MESSAGES_PER_BATCH._"]
    return "\n".join(out) + "\n"


def process_file(path: Path, llm, out_dir: Path, batch_size: int = 20, model: str = "") -> Path:
    parsed = parse_chat(decode_bytes(path.read_bytes()))
    res = ExtractionService(llm, batch_size, model).analyze(parsed.messages)
    brief = build_brief(res.tasks, ai_summary(llm, parsed.messages))
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"brief-{path.stem}.md"
    dest.write_text(render_brief(path.stem, res.tasks, brief, res.batches_failed), encoding="utf-8")
    return dest


def scan(folder: Path, llm, seen: set[str], batch_size: int, model: str, log=print) -> int:
    done = 0
    for f in sorted(folder.glob("*.txt")):
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        if h in seen:
            continue
        try:
            dest = process_file(f, llm, folder / "repu-briefs", batch_size, model)
        except AppError as e:  # leave unseen so it is retried on the next pass
            log(f"[repu] {f.name}: {e.code} - {e.action}")
            continue
        seen.add(h)
        done += 1
        log(f"[repu] {f.name} -> {dest.name}")
    return done


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=60, help="seconds between scans")
    a = ap.parse_args(argv)
    if not a.folder.is_dir():
        ap.error("folder does not exist")
    S = load_settings()
    llm = OllamaClient(S.ollama_base_url, S.ollama_model, S.ollama_timeout)
    seen: set[str] = set()
    print(f"[repu] watching {a.folder} with model {S.ollama_model} (Ctrl+C to stop)")
    while True:
        scan(a.folder, llm, seen, S.max_messages_per_batch, S.ollama_model)
        if a.once:
            return 0
        time.sleep(a.interval)


if __name__ == "__main__":
    raise SystemExit(main())
