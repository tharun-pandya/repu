# Repu (రేపు)

**Local-first task extraction for WhatsApp class groups, in Telugu, Tenglish and English.**

[![CI](https://github.com/OWNER/repu/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/repu/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

*Repu* (రేపు) means "tomorrow" in Telugu. Repu reads an exported WhatsApp chat, proposes deadlines and tasks with a
local open-weight model, verifies every suggestion against the original message, and exports to a calendar (`.ics`)
only the tasks you explicitly confirm. Chat content is never sent to a cloud AI service.

> A message like *"repu 10 ki DBMS lab record submit cheyyali"* ("submit the DBMS lab record tomorrow at 10") is
> ambiguous: is "10" AM or PM, and is the task yours? Repu does not guess. It asks.

## Table of contents

- [Features](#features)
- [How it works](#how-it-works)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Usage](#usage)
- [Development](#development)
- [Testing and evaluation status](#testing-and-evaluation-status)
- [Project structure](#project-structure)
- [Documentation](#documentation)
- [Limitations](#limitations)
- [Contributing](#contributing)
- [Security](#security)
- [License](#license)

## Features

- **Private by design.** Inference runs through [Ollama](https://ollama.com) on your machine (default model: Gemma 3 4B). Sessions live in memory only, and logs never contain chat text.
- **Multilingual parsing.** Android and iOS `.txt` exports, bracketed and dash timestamps, 12/24-hour clocks, multiline messages, system lines and attachments.
- **Evidence verification.** Every suggested task carries a quote that is checked against the source message (`verified_exact`, `verified_normalized` or `missing`).
- **Deterministic date resolution.** The model never produces dates. Code resolves phrases such as *repu*, *ivala*, *ellundi*, *ఎల్లుండి* and *next Monday* relative to the message's own timestamp.
- **Human-in-the-loop export.** Each task needs four confirmations (real task, mine, deadline correct, approved for export). The backend re-checks all four before writing the `.ics`, and source chat text is never written to the calendar.
- **Morning brief.** A code-built headline plus an optional two-line model summary, labelled *AI summary · unverified*.
- **Overnight mode.** A folder watcher turns dropped exports into Markdown briefs. It never creates calendar files.
- **Review UI.** One-tap AM/PM chips, evidence highlighting, a "Coming up" timeline, dark mode, CSV export, drag-and-drop import and real batch-level progress.

## How it works

```
chat export → parser → batches → Ollama (schema-constrained JSON) → schema validation
            → evidence verification → date resolution → ambiguity/ownership policy
            → de-duplication → human review → .ics
```

Design rules:

- The model is an **untrusted interpreter**. It outputs phrases and evidence quotes, never dates.
- Ambiguous AM/PM, ownership, "next Monday" and post-midnight "repu" always require human confirmation.
- Timed events use floating local time (same wall-clock time in your calendar) with a default duration of 30 minutes.
- Chat text is treated as data, not instructions (prompt-injection resistant).
- `DEMO_MODE=true` (hosted demo) serves a fictional sample only: no uploads and no inference.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for module responsibilities and failure modes.

## Quick start

**Prerequisites:** Python 3.11+, [Ollama](https://ollama.com), and about 8 GB of RAM or more for the default model.

```bash
# 1. Pull the model (see docs/MODEL_SETUP.md for low-RAM options)
ollama pull gemma3:4b

# 2. Create an environment and install dependencies
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Start the app (binds to localhost only)
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>, choose **Try sample chat**, then **Preview** and **Extract**.

On Windows, `.\scripts\run.ps1` performs steps 2 and 3 and checks that Ollama is running.

### Docker (hosted demo only)

The provided image runs with `DEMO_MODE=true`: it serves the fictional sample chat and performs no inference.

```bash
docker build -t repu-demo .
docker run --rm -p 8000:8000 repu-demo
```

Do not point a hosted instance at real chats.

## Configuration

All settings are environment variables. Copy `.env.example` as a reference; values below are the defaults.

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama endpoint |
| `OLLAMA_MODEL` | `gemma3:4b` | Model used for extraction and summaries |
| `OLLAMA_TIMEOUT_SECONDS` | `90` | Per-request inference timeout |
| `MAX_UPLOAD_MB` | `10` | Maximum import size |
| `MAX_MESSAGES_PER_IMPORT` | `5000` | Maximum messages parsed per import |
| `MAX_MESSAGES_PER_BATCH` | `20` | Messages sent to the model per batch |
| `SESSION_TTL_MINUTES` | `60` | In-memory session lifetime |
| `DEFAULT_EVENT_MINUTES` | `30` | Duration of exported timed events |
| `DEMO_MODE` | `false` | Disable uploads and inference (fictional sample only) |

## Usage

### Web app

1. Export a chat from WhatsApp (*Export chat → Without media*) and drop the `.txt` file into the app.
2. Review the import preview, then run extraction.
3. Resolve flagged items (AM/PM, ownership, ambiguous dates), edit or dismiss tasks, and tick the four confirmations.
4. Export confirmed tasks to `.ics` or CSV.

### Overnight mode

```bash
python -m backend.app.watch ~/repu-inbox          # keep watching (Ctrl+C to stop)
python -m backend.app.watch ~/repu-inbox --once   # process what is there, then exit
```

Briefs are written to `~/repu-inbox/repu-briefs/brief-<name>.md`. They contain task text from your chat on your own
disk, so keep the folder private. Only file hashes are remembered, in memory.

### API

A JSON API backs the UI. Interactive docs are served at `/docs` when `DEMO_MODE` is off. See [docs/API.md](docs/API.md).

## Development

```bash
make install       # venv, dev dependencies, frontend test dependencies
make test          # pytest + unittest
make test-ui       # jsdom UI smoke tests (mocked inference)
make lint          # ruff
make run           # start the dev server
```

Other targets: `make eval-dev`, `make local-model-test` (opt-in test against a real Ollama model),
`make watch DIR=<folder>`, `make model-check`.

## Testing and evaluation status

| Area | Status |
|---|---|
| Core logic unit tests (`unittest`) | 38 passing |
| API, brief, jobs and watcher tests (`pytest`, real `OllamaClient` against a fake Ollama HTTP server) | 74 passing in total with the above, 1 opt-in real-model test skipped |
| UI smoke tests (jsdom, live server, mocked inference) | passing |
| Lint (`ruff`) | clean |
| Real-model (Gemma 3 4B) inference | **Not covered by CI.** Run `make local-model-test` locally. |
| Real-browser tests (Playwright) | **Not yet implemented.** UI behaviour is tested at the DOM level only. |
| Extraction accuracy on real Telugu/Tenglish chats | **Not measured.** |
| Resolver evaluation (n=110, template-generated) | 83/83. Gold labels and rules share an author, so this is a regression check, not a real-world accuracy estimate. |

Evaluation harness:

```bash
python -m evaluation.generate_dataset                      # 40 dev / 110 test examples, seed 7
python -m evaluation.evaluate --split dev --mode resolver  # deterministic layer, no model needed
python -m evaluation.evaluate --split dev --mode pipeline  # requires Ollama
```

Tune on the dev split only and run the test split once at the end. Reports are written to `evaluation/reports/`.

## Project structure

```
backend/app/        FastAPI app, services (parser, extraction, verifier, resolver, exporter), CLI, watcher
backend/tests/      pytest and unittest suites
frontend/           Dependency-free single-page UI (index.html) and jsdom tests
evaluation/         Dataset generator, metrics, evaluation runner and reports
sample_data/        Fictional sample chat and hand-written expectations
docs/               Architecture, API, privacy, threat model, deployment, model setup
```

## Documentation

[Architecture](docs/ARCHITECTURE.md) · [API](docs/API.md) · [Privacy](docs/PRIVACY.md) ·
[Threat model](docs/THREAT_MODEL.md) · [Model setup](docs/MODEL_SETUP.md) · [Deployment](docs/DEPLOYMENT.md) ·
[Changelog](CHANGELOG.md)

## Limitations

- Images, audio and documents in chats are ignored.
- Evaluation data is template-generated by a single author; real-world accuracy is unmeasured.
- Small local models may struggle on 8 GB machines and vary in Telugu quality.
- Sessions are in memory by design; nothing persists across restarts.
- The local API has no authentication. Bind to `127.0.0.1` only. See the [threat model](docs/THREAT_MODEL.md).
- The UI is a single dependency-free HTML file (no build step); it is less componentized than a framework app.

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first. Never attach real chat exports to
issues or pull requests; use synthetic text.

## Security

Please report vulnerabilities privately. See [SECURITY.md](SECURITY.md).

## License

Released under the [MIT License](LICENSE).
