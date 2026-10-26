# Model setup

Repu uses [Ollama](https://ollama.com) to run an open-weight model locally. The default is `OLLAMA_MODEL=gemma3:4b`
(Gemma 3 4B).

Download size and RAM use depend on the quantization, context length (Repu uses `num_ctx=4096`), your OS and other
running applications. Check the [Ollama library](https://ollama.com/library) for current sizes and tags.

## Setup

1. Install Ollama from <https://ollama.com>.
2. Pull the model: `ollama pull gemma3:4b`.
3. Start Repu. The UI shows "gemma3:4b ready" when the model is installed.
4. Optional: `GET /api/model/status?deep=true` runs a small real inference to confirm everything works.

## Troubleshooting

| Error code | Fix |
|---|---|
| `MODEL_UNAVAILABLE` | Start Ollama and check `OLLAMA_BASE_URL`. |
| `MODEL_NOT_INSTALLED` | Run `ollama pull <model>`. |
| `INSUFFICIENT_MEMORY` / `MODEL_TIMEOUT` | Close other applications, lower `MAX_MESSAGES_PER_BATCH`, raise `OLLAMA_TIMEOUT_SECONDS`, or set `OLLAMA_MODEL` to a smaller model you have pulled. |

Telugu quality varies by model and has not been measured systematically.

## Verifying against a real model

```bash
make local-model-test
python -m evaluation.evaluate --split dev --mode pipeline
```
