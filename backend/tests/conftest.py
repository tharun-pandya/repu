"""Fixtures: a fake Ollama HTTP server (MOCKED INFERENCE - not a real model)."""
from __future__ import annotations

import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app

LINE = re.compile(r"^\[(?P<id>[^\]]+)\] \([^)]*\) [^:]*: (?P<text>.*)$")


class FakeOllama:
    def __init__(self):
        self.mode = "ok"
        self.models = ["gemma3:4b"]
        self.systems: list[str] = []
        self.prompts: list[str] = []  # lets tests assert what would be sent (local only)
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silence
                pass

            def _send(self, code, obj):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/api/tags":
                    self._send(200, {"models": [{"name": m} for m in outer.models]})
                else:
                    self._send(404, {"error": "not found"})

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(n))
                user = req["messages"][-1]["content"]
                outer.prompts.append(user)
                outer.systems.append(req["messages"][0]["content"])
                if outer.mode == "notfound":
                    return self._send(404, {"error": "model 'x' not found"})
                if outer.mode == "oom":
                    return self._send(500, {"error": "model requires more system memory than is available"})
                if outer.mode == "slow":
                    time.sleep(3)
                if outer.mode == "garbage":
                    return self._send(200, {"message": {"content": "not json {{"}})
                if "two short lines" in req["messages"][0]["content"]:
                    if outer.mode == "summary_fail":
                        return self._send(200, {"message": {"content": "nope"}})
                    return self._send(200, {"message": {"content": json.dumps({"lines": ["Lab record due tomorrow.", "Check the AM/PM."]})}})
                if "Return {\"ok\": true}" in user:
                    return self._send(200, {"message": {"content": '{"ok": true}'}})
                tasks = []
                for ln in user.splitlines():
                    m = LINE.match(ln)
                    if m and "submit cheyyali" in m["text"]:
                        text = m["text"]
                        quote = "this sentence was invented" if outer.mode == "fabricate" else text.split("\n")[0]
                        tasks.append({
                            "message_id": m["id"], "task_title": "Submit DBMS lab record",
                            "normalized_telugu": None, "evidence_quote": quote, "action_type": "submit",
                            "date_phrase": "repu" if "repu" in text else None,
                            "time_phrase": "10 ki" if "10 ki" in text else None,
                            "ownership": "unknown", "is_actionable": True, "uncertainty_reasons": []})
                payload = {"tasks": tasks, "non_actionable_message_ids": [], "warnings": []}
                self._send(200, {"message": {"content": json.dumps(payload)}})

        self.httpd = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


@pytest.fixture()
def fake():
    f = FakeOllama()
    yield f
    f.close()


def make_client(fake: FakeOllama, **kw) -> TestClient:
    s = Settings(ollama_base_url=fake.url, ollama_model="gemma3:4b", ollama_timeout=kw.pop("timeout", 5), **kw)
    return TestClient(create_app(s), raise_server_exceptions=False)


@pytest.fixture()
def client(fake):
    return make_client(fake)
