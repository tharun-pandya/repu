"""python -m evaluation.evaluate --split dev|test --mode resolver|pipeline
resolver : deterministic layer only, fed the GOLD phrases (no model needed).
pipeline : real local model via Ollama + all deterministic checks."""
import argparse
import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

from backend.app.config import load_settings
from backend.app.services.chat_parser import ChatMessage, normalize
from backend.app.services.date_resolver import resolve_deadline
from backend.app.services.extraction_service import ExtractionService, SchemaError, validate_model_output
from backend.app.services.evidence_verifier import is_verified
from backend.app.services.llm_client import OllamaClient
from .metrics import median, prf, rate

HERE = Path(__file__).parent
OWN = {"general_announcement": "everyone", "other_person": "named_person", "unknown": "unknown"}


def load(split):
    p = HERE / f"{split}_set.jsonl"
    raw = p.read_bytes()
    return [json.loads(l) for l in raw.decode("utf-8").splitlines() if l.strip()], hashlib.sha256(raw).hexdigest()


def run_resolver(rows):
    act = [r for r in rows if r["gold"]["actionable"]]
    d_ok = t_ok = a_ok = 0
    for r in act:
        g = r["gold"]
        dl = resolve_deadline(g["date_phrase"], g["time_phrase"], datetime.fromisoformat(r["timestamp"]), r["text"])
        d_ok += dl.date == g["date"]
        t_ok += dl.time == g["time"]
        a_ok += dl.time_ambiguous == g["time_ambiguous"]
    return {"mode": "resolver", "n_actionable": len(act), "date_accuracy": rate(d_ok, len(act)),
            "time_accuracy": rate(t_ok, len(act)), "ambiguity_flag_accuracy": rate(a_ok, len(act))}


class Timed:
    def __init__(self, inner):
        self.inner, self.lat, self.valid, self.calls = inner, [], 0, 0

    def chat_json(self, system, user, schema):
        t0 = time.time()
        out = self.inner.chat_json(system, user, schema)
        self.lat.append(time.time() - t0)
        self.calls += 1
        try:
            validate_model_output(out)
            self.valid += 1
        except SchemaError:
            pass
        return out


def run_pipeline(rows):
    s = load_settings()
    llm = Timed(OllamaClient(s.ollama_base_url, s.ollama_model, s.ollama_timeout))
    msgs = [ChatMessage(id=r["id"], order=i, raw_timestamp=None, timestamp=datetime.fromisoformat(r["timestamp"]),
                        sender=r["sender"], text=r["text"], normalized=normalize(r["text"])) for i, r in enumerate(rows)]
    res = ExtractionService(llm, s.max_messages_per_batch, s.ollama_model).analyze(msgs)
    pred = {}
    for t in res.tasks:
        pred.setdefault(t.message_id, t)
    tp = fp = fn = 0
    d_ok = t_ok = o_ok = amb_n = amb_hit = ev_ok = inj_n = inj_bad = 0
    for r in rows:
        g, p = r["gold"], pred.get(r["id"])
        if g["actionable"] and p:
            tp += 1
            d_ok += p.deadline.date == g["date"]
            t_ok += (p.deadline.time == g["time"]) and (p.deadline.time_ambiguous == g["time_ambiguous"])
            o_ok += OWN.get(p.ownership) == g["ownership"]
            if g["time_ambiguous"]:
                amb_n += 1
                amb_hit += p.deadline.time_ambiguous
        elif g["actionable"]:
            fn += 1
        elif p:
            fp += 1
        if not g["actionable"] and any(k in r["text"].lower() for k in ("ignore all", "system:", "rm -rf", "forward this")):
            inj_n += 1
            inj_bad += bool(p)
    ev_ok = sum(is_verified(t.evidence_status) for t in res.tasks)
    non = sum(1 for r in rows if not r["gold"]["actionable"])
    return {"mode": "pipeline", "model": s.ollama_model, "n": len(rows), "batches": res.batches_total,
            "batches_failed": res.batches_failed, "detection": prf(tp, fp, fn),
            "date_accuracy_on_detected": rate(d_ok, tp), "time_accuracy_on_detected": rate(t_ok, tp),
            "ownership_accuracy_on_detected": rate(o_ok, tp), "ambiguity_flagged_when_gold_ambiguous": rate(amb_hit, amb_n),
            "evidence_verified_rate": rate(ev_ok, len(res.tasks)), "false_positive_rate_non_actionable": rate(fp, non),
            "injection_examples_that_produced_tasks": rate(inj_bad, inj_n),
            "valid_output_rate_first_try": rate(llm.valid, llm.calls), "median_call_latency_s": median(llm.lat),
            "model_calls": llm.calls}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--mode", choices=["resolver", "pipeline"], default="resolver")
    a = ap.parse_args()
    rows, h = load(a.split)
    out = (run_resolver if a.mode == "resolver" else run_pipeline)(rows)
    out.update(split=a.split, dataset_sha256=h, dataset_size=len(rows), run_at=datetime.now().isoformat(timespec="seconds"))
    rep = HERE / "reports"
    rep.mkdir(exist_ok=True)
    stem = f"{a.mode}_{a.split}"
    (rep / f"{stem}.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    md = [f"# {a.mode} on {a.split} (n={len(rows)})", f"dataset sha256: `{h[:16]}…`", ""]
    for k, v in out.items():
        if isinstance(v, dict) and "value" in v:
            md.append(f"- {k}: {v['value']} ({v['k']}/{v['n']}, 95% CI {v['ci95']})")
        elif isinstance(v, dict):
            md.append(f"- {k}: " + ", ".join(f"{x}={y:.3f}" for x, y in v.items()))
        elif k not in ("split", "dataset_sha256"):
            md.append(f"- {k}: {v}")
    (rep / f"{stem}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
