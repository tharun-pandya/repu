# Architecture
Modular monolith: `chat → parser → batches → Ollama (schema-constrained JSON) → schema validation → evidence verification → date resolution → ambiguity/ownership policy → dedupe → human review → .ics`.

| Module | Responsibility | Trusts model? |
|---|---|---|
| `chat_parser.py` | encodings (UTF-8/BOM/UTF-16), timestamp formats, multiline, system/attachment lines | no model |
| `llm_client.py` | `LLMClient` protocol + `OllamaClient` (health, install check, timeout, typed errors) | adapter only |
| `extraction_service.py` | batching, strict validation, one repair retry, ownership + confirmation reasons | treats output as untrusted |
| `evidence_verifier.py` | quote must exist in the source message | deterministic |
| `date_resolver.py` | Telugu/Tenglish/English phrases → dates relative to the message timestamp | deterministic |
| `deduplication.py` | duplicate *suggestions* only | deterministic |
| `calendar_exporter.py` | RFC 5545 writer; refuses unconfirmed tasks | deterministic |
| `main.py` | `create_app()`, limits, error envelope, in-memory sessions, demo mode | — |

Failure modes: bad batch → recorded as failed batch (others kept); all batches bad → `INVALID_MODEL_OUTPUT`; Ollama down → `MODEL_UNAVAILABLE` (never fabricated results).
Sessions: in-memory dict, TTL, one inference at a time (semaphore).
