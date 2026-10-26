"""API integration tests. Inference is MOCKED by a fake Ollama HTTP server (see conftest.py);
the real OllamaClient adapter and full FastAPI stack are exercised."""
from __future__ import annotations

import logging
from pathlib import Path

from backend.app.config import Settings
from backend.tests.conftest import make_client

SAMPLE = (Path(__file__).resolve().parents[2] / "sample_data" / "synthetic_whatsapp_chat.txt").read_text(encoding="utf-8")


def preview(client, text=SAMPLE):
    r = client.post("/api/import/preview", data={"text": text})
    assert r.status_code == 200, r.text
    return r.json()


def confirmed(**over):
    t = {"title": "Submit DBMS lab record", "date": "2026-10-27", "time": "10:00", "task_confirmed": True,
         "owner_confirmed": True, "deadline_confirmed": True, "export_approved": True}
    t.update(over)
    return t


# ---------- health / model status ----------
def test_health_and_model_ready(client):
    h = client.get("/api/health").json()
    assert h["ollama_reachable"] and h["inference_available"] and h["status"] == "ok"
    m = client.get("/api/model/status?deep=true").json()
    assert m["installed"] and m["inference_ok"] is True


def test_model_not_installed(fake):
    fake.models = ["other:1b"]
    m = make_client(fake).get("/api/model/status").json()
    assert m["ollama_reachable"] and not m["installed"] and "ollama pull gemma3:4b" in m["next_step"]


def test_ollama_down():
    s = Settings(ollama_base_url="http://127.0.0.1:9", ollama_timeout=5)
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    c = TestClient(create_app(s), raise_server_exceptions=False)
    assert c.get("/api/health").json()["ollama_reachable"] is False
    sid = preview(c)["session_id"]
    r = c.post("/api/analyze", json={"session_id": sid})
    assert r.status_code == 503 and r.json()["error"]["code"] == "MODEL_UNAVAILABLE"


# ---------- import ----------
def test_preview_sample(client):
    p = preview(client)
    assert p["message_count"] >= 10 and p["skipped_attachments"] == 1 and p["skipped_system"] == 1
    assert p["date_range"] and p["session_id"]


def test_preview_file_upload_utf16(client):
    data = SAMPLE.encode("utf-16")
    r = client.post("/api/import/preview", files={"file": ("chat.txt", data, "text/plain")})
    assert r.status_code == 200 and r.json()["message_count"] >= 10


def test_wrong_extension(client):
    r = client.post("/api/import/preview", files={"file": ("chat.pdf", b"x", "application/pdf")})
    assert r.status_code == 415 and r.json()["error"]["code"] == "INVALID_FILE_TYPE"


def test_empty_input(client):
    r = client.post("/api/import/preview", data={"text": "   "})
    assert r.status_code == 422 and r.json()["error"]["code"] == "NO_MESSAGES"


def test_oversize_file(fake):
    c = make_client(fake, max_upload_mb=1)
    r = c.post("/api/import/preview", files={"file": ("c.txt", b"a" * (2 * 1024 * 1024), "text/plain")})
    assert r.status_code == 413 and r.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_large_paste_over_1mb_default_form_limit(fake):
    c = make_client(fake, max_upload_mb=5)
    big = "26/10/2026, 8:05 pm - Ravi: hello world filler\n" * 30000  # ~1.4 MB
    r = c.post("/api/import/preview", data={"text": big})
    assert r.status_code == 200, r.text


def test_not_a_chat(client):
    r = client.post("/api/import/preview", data={"text": "just a random paragraph\nwith no timestamps"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "NO_MESSAGES"


# ---------- analyze (mocked inference) ----------
def test_analyze_flow(client, fake):
    sid = preview(client)["session_id"]
    r = client.post("/api/analyze", json={"session_id": sid, "display_name": "Anil"})
    assert r.status_code == 200, r.text
    body = r.json()
    t = body["tasks"][0]
    assert t["evidence_status"] in ("verified_exact", "verified_normalized")
    assert t["deadline"]["date"] == "2026-10-27"          # repu relative to message timestamp (26 Oct)
    assert t["deadline"]["status"] == "ambiguous"          # "10 ki" AM/PM unresolved -> must confirm
    assert t["needs_review"] and t["confirmation_reasons"]
    assert any("duplicate" in " ".join(x["confirmation_reasons"]).lower() for x in body["tasks"])


def test_fabricated_quote_is_flagged_not_trusted(client, fake):
    fake.mode = "fabricate"
    sid = preview(client)["session_id"]
    tasks = client.post("/api/analyze", json={"session_id": sid}).json()["tasks"]
    assert tasks and all(t["evidence_status"] in ("missing", "unverified") for t in tasks)
    assert all("could not be verified" in " ".join(t["confirmation_reasons"]) for t in tasks)


def test_injection_message_produces_no_task_and_is_data(client, fake):
    sid = preview(client)["session_id"]
    tasks = client.post("/api/analyze", json={"session_id": sid}).json()["tasks"]
    assert not any("system prompt" in t["title"].lower() or "ignore all" in t["evidence_quote"].lower() for t in tasks)
    assert any("ignore all previous instructions" in p for p in fake.prompts)  # sent only to the LOCAL fake as data


def test_invalid_model_output(client, fake):
    fake.mode = "garbage"
    sid = preview(client)["session_id"]
    r = client.post("/api/analyze", json={"session_id": sid})
    assert r.status_code == 502 and r.json()["error"]["code"] == "INVALID_MODEL_OUTPUT"


def test_model_missing_during_analyze(client, fake):
    fake.mode = "notfound"
    sid = preview(client)["session_id"]
    r = client.post("/api/analyze", json={"session_id": sid})
    assert r.status_code == 503 and r.json()["error"]["code"] == "MODEL_NOT_INSTALLED"


def test_out_of_memory(client, fake):
    fake.mode = "oom"
    sid = preview(client)["session_id"]
    r = client.post("/api/analyze", json={"session_id": sid})
    assert r.status_code == 503 and r.json()["error"]["code"] == "INSUFFICIENT_MEMORY"


def test_timeout(fake):
    fake.mode = "slow"
    c = make_client(fake, timeout=1)
    sid = preview(c)["session_id"]
    r = c.post("/api/analyze", json={"session_id": sid})
    assert r.status_code == 504 and r.json()["error"]["code"] == "MODEL_TIMEOUT"


def test_unknown_session_and_bad_body(client):
    r = client.post("/api/analyze", json={"session_id": "does-not-exist"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "SESSION_EXPIRED"
    r = client.post("/api/analyze", json={"session_id": "abcdefgh12", "evil": 1})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_REQUEST"


def test_session_delete(client):
    sid = preview(client)["session_id"]
    assert client.delete(f"/api/session/{sid}").json()["deleted"] is True
    assert client.delete(f"/api/session/{sid}").json()["deleted"] is False
    assert client.post("/api/analyze", json={"session_id": sid}).status_code == 404


# ---------- export ----------
def test_export_rejects_unconfirmed(client):
    for flag in ("task_confirmed", "owner_confirmed", "deadline_confirmed", "export_approved"):
        r = client.post("/api/export/ics", json={"tasks": [confirmed(**{flag: False})]})
        assert r.status_code == 422 and r.json()["error"]["code"] == "EXPORT_REJECTED", flag


def test_export_rejects_empty_and_bad_date(client):
    assert client.post("/api/export/ics", json={"tasks": []}).status_code == 422
    r = client.post("/api/export/ics", json={"tasks": [confirmed(date="2026-13-45")]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_DATE"
    r = client.post("/api/export/ics", json={"tasks": [confirmed(time="25:99")]})
    assert r.status_code == 422


def test_export_ics_valid_and_roundtrip(client):
    title = "Submit lab; record, with\nnewline & తెలుగు"
    r = client.post("/api/export/ics", json={"tasks": [confirmed(title=title, reminder_minutes=30),
                                                      confirmed(title="Fee payment", time=None, date="2026-11-02")]})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar")
    assert r.headers["x-exported-count"] == "2" and ".ics" in r.headers["content-disposition"]
    raw = r.content
    assert b"\r\n" in raw and raw.count(b"BEGIN:VEVENT") == 2 and raw.endswith(b"\r\n")
    assert b"\n" not in raw.replace(b"\r\n", b"")
    for line in raw.split(b"\r\n"):
        assert len(line) <= 75
    text = raw.decode().replace("\r\n ", "")  # unfold
    assert "DTSTART:20261027T100000" in text and "DTSTART;VALUE=DATE:20261102" in text
    assert "TRIGGER:-PT30M" in text
    assert "తెలుగు" in text and "\\;" in text and "\\n" in text
    uids = [l for l in text.split("\r\n") if l.startswith("UID:")]
    assert len(set(uids)) == 2
    assert "evidence" not in text.lower()  # source chat text is never exported


def test_export_rejects_extra_fields(client):
    r = client.post("/api/export/ics", json={"tasks": [confirmed(evidence_quote="secret chat")]})
    assert r.status_code == 422


def test_security_headers_and_no_store(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["cache-control"] == "no-store"
    assert r.headers["x-frame-options"] == "DENY"


# ---------- privacy ----------
def test_no_chat_content_in_logs(client, caplog):
    caplog.set_level(logging.DEBUG)
    secret = "26/10/2026, 8:05 pm - Zorblax Quux: topsecretword repu 10 ki submit cheyyali\n"
    sid = client.post("/api/import/preview", data={"text": secret}).json()["session_id"]
    client.post("/api/analyze", json={"session_id": sid, "display_name": "Zorblax"})
    client.post("/api/export/ics", json={"tasks": [confirmed(title="x"), {"bad": 1}]})
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "topsecretword" not in logged and "Zorblax" not in logged


def test_validation_errors_do_not_echo_input(client):
    r = client.post("/api/analyze", json={"session_id": "SECRETVALUE-12345", "evil": "leakme"})
    assert "SECRETVALUE" not in r.text and "leakme" not in r.text


# ---------- demo mode ----------
def test_demo_mode_blocks_real_data_and_inference(fake):
    c = make_client(fake, demo_mode=True)
    assert c.post("/api/import/preview", files={"file": ("c.txt", b"x", "text/plain")}).status_code == 403
    assert c.post("/api/import/preview", data={"text": "26/10/2026, 8:05 pm - A: private"}).status_code == 403
    sid = preview(c)["session_id"]  # the fictional sample is allowed
    r = c.post("/api/analyze", json={"session_id": sid})
    assert r.status_code == 403 and r.json()["error"]["code"] == "DEMO_MODE"
    assert fake.prompts == []  # nothing ever reached a model


# ---------- morning brief / jobs (mocked inference) ----------
def test_brief_has_deterministic_headline_and_labelled_ai_lines(client):
    sid = preview(client)["session_id"]
    r = client.post("/api/analyze", json={"session_id": sid}).json()
    b = r["brief"]
    assert "candidate task" in b["headline"] and b["ai_lines"] == ["Lab record due tomorrow.", "Check the AM/PM."]
    assert "not verified" in b["ai_note"]
    assert b["due"] and b["due"][0]["date"] == "2026-10-27" and b["due"][0]["weekday"] == "Tue"
    assert r["stats"]["messages_read"] >= 8 and r["stats"]["seconds"] >= 0


def test_summary_failure_never_breaks_analysis(client, fake):
    fake.mode = "summary_fail"
    sid = preview(client)["session_id"]
    r = client.post("/api/analyze", json={"session_id": sid})
    assert r.status_code == 200 and r.json()["brief"]["ai_lines"] == [] and r.json()["tasks"]


def test_summary_can_be_disabled(client, fake):
    sid = preview(client)["session_id"]
    r = client.post("/api/analyze", json={"session_id": sid, "summary": False}).json()
    assert r["brief"]["ai_lines"] == [] and fake.systems and not any("two short lines" in x for x in fake.systems)
    client.post("/api/analyze", json={"session_id": sid})
    assert any("two short lines" in x for x in fake.systems)  # and it IS sent when enabled


def _wait(client, job_id):
    import time
    for _ in range(100):
        j = client.get(f"/api/analyze/status/{job_id}").json()
        if j["state"] != "running":
            return j
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_job_progress_flow(client):
    sid = preview(client)["session_id"]
    jid = client.post("/api/analyze/start", json={"session_id": sid}).json()["job_id"]
    j = _wait(client, jid)
    assert j["state"] == "done" and j["done"] == j["total"] >= 1 and j["result"]["tasks"]


def test_job_reports_model_error_with_code(client, fake):
    fake.mode = "oom"
    sid = preview(client)["session_id"]
    j = _wait(client, client.post("/api/analyze/start", json={"session_id": sid}).json()["job_id"])
    assert j["state"] == "error" and j["error"]["code"] == "INSUFFICIENT_MEMORY" and j["http_status"] == 503


def test_job_unknown_and_deleted_with_session(client):
    assert client.get("/api/analyze/status/nope").status_code == 404
    sid = preview(client)["session_id"]
    jid = client.post("/api/analyze/start", json={"session_id": sid}).json()["job_id"]
    _wait(client, jid)
    client.delete(f"/api/session/{sid}")
    assert client.get(f"/api/analyze/status/{jid}").status_code == 404  # job data released with the session


def test_demo_mode_blocks_job_start(fake):
    c = make_client(fake, demo_mode=True)
    sid = preview(c)["session_id"]
    assert c.post("/api/analyze/start", json={"session_id": sid}).status_code == 403
