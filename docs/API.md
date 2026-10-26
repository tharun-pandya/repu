# API (all JSON; errors: `{"error":{"code","message","action","request_id"}}`)
| Endpoint | Purpose |
|---|---|
| `GET /api/health` | status, version, `demo_mode`, Ollama reachable, model installed |
| `GET /api/model/status?deep=true` | installed check; `deep` runs a tiny real inference |
| `GET /api/demo/sample` | fictional sample chat |
| `POST /api/import/preview` | multipart `file` (.txt) or `text`, optional `date_order` (auto/dmy/mdy) → counts, range, warnings, `session_id` |
| `POST /api/analyze` | `{session_id, display_name?, summary?=true}` → `tasks`, `brief{headline, ai_lines, due[]}`, `stats{messages_read, seconds}`, warnings |
| `POST /api/analyze/start` | same body as analyze; returns `{job_id}` immediately |
| `GET /api/analyze/status/{job_id}` | `{state: running/done/error, done, total, result?, error?, http_status}`; real batch progress |
| `POST /api/export/ics` | `{tasks:[{title,date,time?,task_confirmed,owner_confirmed,deadline_confirmed,export_approved,reminder_minutes?}]}` → `text/calendar`; any false flag → 422 `EXPORT_REJECTED` |
| `DELETE /api/session/{id}` | release session memory; reports honestly whether it existed |

Codes: INVALID_FILE_TYPE 415 · FILE_TOO_LARGE 413 · UNSUPPORTED_ENCODING 422 · NO_MESSAGES 422 · INVALID_REQUEST 422 · INVALID_DATE 422 · EXPORT_REJECTED 422 · SESSION_EXPIRED 404 · DEMO_MODE 403 · MODEL_UNAVAILABLE 503 · MODEL_NOT_INSTALLED 503 · INSUFFICIENT_MEMORY 503 · MODEL_TIMEOUT 504 · INVALID_MODEL_OUTPUT 502 · INTERNAL_ERROR 500.
Validation errors list field names and error types only, never submitted values.
