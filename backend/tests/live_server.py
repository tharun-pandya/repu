"""Starts fake Ollama + the real app on a free port for browser-level smoke tests. Prints the URL."""
import sys
import socket
import uvicorn
from backend.tests.conftest import FakeOllama
from backend.app.config import Settings
from backend.app.main import create_app

fake = FakeOllama()
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
cfg = Settings(ollama_base_url=fake.url, ollama_model="gemma3:4b", ollama_timeout=5,
               demo_mode="--demo" in sys.argv)
print(f"http://127.0.0.1:{port}", flush=True)
uvicorn.run(create_app(cfg), host="127.0.0.1", port=port, log_level="warning")
