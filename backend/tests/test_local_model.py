"""REAL local-model smoke test. Skipped unless REPU_LOCAL_MODEL_TEST=1 and Ollama + model are available.

Run:  REPU_LOCAL_MODEL_TEST=1 python -m pytest -m local_model -s
Asserts invariants that must hold for ANY model (schema validity, evidence honesty, injection safety),
not exact task lists, because output depends on the model.
"""
import os
from pathlib import Path

import pytest

from backend.app.config import load_settings
from backend.app.services.chat_parser import parse_chat
from backend.app.services.extraction_service import ExtractionService
from backend.app.services.llm_client import OllamaClient

pytestmark = [pytest.mark.local_model,
              pytest.mark.skipif(os.environ.get("REPU_LOCAL_MODEL_TEST") != "1", reason="opt-in: set REPU_LOCAL_MODEL_TEST=1")]
SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "synthetic_whatsapp_chat.txt"


def test_real_model_end_to_end():
    S = load_settings()
    llm = OllamaClient(S.ollama_base_url, S.ollama_model, S.ollama_timeout)
    st = llm.status(deep=True)
    assert st.ollama_reachable and st.installed and st.inference_ok, st.next_step
    parsed = parse_chat(SAMPLE.read_text(encoding="utf-8"))
    res = ExtractionService(llm, S.max_messages_per_batch, S.ollama_model).analyze(parsed.messages)
    print(f"model={S.ollama_model} tasks={len(res.tasks)} failed_batches={res.batches_failed}")
    for t in res.tasks:  # evidence honesty: unverified quotes must be flagged for the user
        if t.evidence_status not in ("verified_exact", "verified_normalized"):
            assert t.needs_review
        assert not t.deadline.status == "resolved" or t.deadline.date  # resolved => has a code-computed date
    assert not any("system prompt" in t.title.lower() for t in res.tasks)  # injection message is data
