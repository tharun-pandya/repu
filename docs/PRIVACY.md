# Privacy
- Local mode: chat text goes browser → your own FastAPI process (127.0.0.1) → your own Ollama (127.0.0.1). No other network calls are made by Repu code. (Ollama itself contacts its registry only when *you* run `ollama pull`.)
- Nothing is written to disk by Repu. Sessions live in process memory, expire after `SESSION_TTL_MINUTES`, and can be cleared with **Clear session**. Python/OS may keep freed pages until reused; restarting the process clears everything.
- Logs contain operational metadata only (counts, durations, error type, model name). Tested: `test_no_chat_content_in_logs`.
- The browser stores nothing (no localStorage/cookies/analytics).
- `.ics` files contain only the task title/date/time you approved, never the source message.
- Hosted demo (`DEMO_MODE=true`): fictional sample only; uploads and inference are disabled. It does **not** run your local model.
- Not verified here: Ollama's own telemetry/network behaviour — check its documentation if you need an air-gapped guarantee.
