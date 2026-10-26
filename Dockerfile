# Hosted DEMO image (synthetic data only, no inference).
# For real use, run Repu locally with Ollama (see README).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEMO_MODE=true

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend/index.html ./frontend/index.html
COPY sample_data ./sample_data

RUN useradd --system --no-create-home repu
USER repu

EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
