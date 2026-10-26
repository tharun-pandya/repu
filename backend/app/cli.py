"""Quick end-to-end check against the REAL local model:  python -m backend.app.cli sample_data/synthetic_whatsapp_chat.txt"""
import json
import sys
from pathlib import Path

from .config import load_settings
from .services.chat_parser import decode_bytes, parse_chat
from .services.extraction_service import ExtractionService
from .services.llm_client import OllamaClient


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "sample_data/synthetic_whatsapp_chat.txt")
    s = load_settings()
    llm = OllamaClient(s.ollama_base_url, s.ollama_model, s.ollama_timeout)
    st = llm.status()
    print(f"ollama_reachable={st.ollama_reachable} model={st.model} installed={st.installed} -> {st.next_step}")
    if not st.installed:
        sys.exit(1)
    parsed = parse_chat(decode_bytes(path.read_bytes()))
    res = ExtractionService(llm, s.max_messages_per_batch, s.ollama_model).analyze(
        parsed.messages, progress=lambda i, n: print(f"batch {i}/{n}…"))
    for t in res.tasks:
        d = t.to_dict()
        print(json.dumps({k: d[k] for k in ("title", "evidence_status", "deadline", "ownership", "confirmation_reasons")},
                         ensure_ascii=False, indent=1))
    print(f"{len(res.tasks)} candidates, {res.batches_failed} failed batches, warnings={res.warnings}")


if __name__ == "__main__":
    main()
