"""Overnight watcher (MOCKED inference via fake Ollama server)."""
from pathlib import Path

from backend.app.services.llm_client import OllamaClient
from backend.app.watch import scan

SAMPLE = (Path(__file__).resolve().parents[2] / "sample_data" / "synthetic_whatsapp_chat.txt").read_text(encoding="utf-8")


def test_watch_writes_brief_only_and_never_ics(fake, tmp_path):
    (tmp_path / "classgroup.txt").write_text(SAMPLE, encoding="utf-8")
    llm = OllamaClient(fake.url, "gemma3:4b", 5)
    seen: set[str] = set()
    logs: list[str] = []
    assert scan(tmp_path, llm, seen, 20, "gemma3:4b", logs.append) == 1
    brief = (tmp_path / "repu-briefs" / "brief-classgroup.md").read_text(encoding="utf-8")
    assert "Repu morning brief" in brief and "Submit DBMS lab record" in brief and "confirm in the Repu app" in brief
    assert "AM/PM unclear" in brief
    assert not list(tmp_path.rglob("*.ics"))                     # never creates calendar files
    assert scan(tmp_path, llm, seen, 20, "gemma3:4b", logs.append) == 0   # unchanged file is not reprocessed


def test_watch_retries_when_model_down(tmp_path):
    (tmp_path / "c.txt").write_text(SAMPLE, encoding="utf-8")
    llm = OllamaClient("http://127.0.0.1:9", "gemma3:4b", 5)
    seen: set[str] = set()
    logs: list[str] = []
    assert scan(tmp_path, llm, seen, 20, "gemma3:4b", logs.append) == 0
    assert not seen and "MODEL_UNAVAILABLE" in logs[0]           # left unseen -> retried next pass
