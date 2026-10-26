# Deployment

## Local (primary)

Follow the README quick start. Bind to `127.0.0.1` only; the API has no authentication.

## Hosted demo (Render)

`render.yaml` and the `Dockerfile` run Repu with `DEMO_MODE=true`: a fictional sample chat only, no uploads, no
inference and no Ollama.

1. Create a new Render Blueprint from this repository.
2. Confirm the health check at `/api/health` reports `"demo_mode": true`.

Never point a hosted instance at real chats.
