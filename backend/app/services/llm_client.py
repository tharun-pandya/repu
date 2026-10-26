"""Ollama adapter (stdlib only). Domain code depends on the LLMClient protocol, not on Ollama."""
from __future__ import annotations
import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from ..errors import (model_unavailable, model_not_installed, model_timeout,
                      insufficient_memory, invalid_model_output)


@dataclass
class ModelStatus:
    ollama_reachable: bool
    model: str
    installed: bool
    inference_ok: bool | None
    next_step: str


class LLMClient(Protocol):
    def chat_json(self, system: str, user: str, schema: dict) -> dict: ...
    def status(self, deep: bool = False) -> ModelStatus: ...


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout: int = 90):
        self.base_url, self.model, self.timeout = base_url.rstrip("/"), model, timeout

    def _request(self, path: str, payload: dict | None = None, timeout: int | None = None) -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base_url + path, data=data,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore").lower()
            if e.code == 404 or "not found" in body:
                raise model_not_installed(self.model)
            if "memory" in body:
                raise insufficient_memory()
            raise model_unavailable()
        except TimeoutError:
            raise model_timeout()
        except urllib.error.URLError as e:
            if isinstance(e.reason, (socket.timeout, TimeoutError)):
                raise model_timeout()
            raise model_unavailable()
        except json.JSONDecodeError:
            raise invalid_model_output()

    def chat_json(self, system: str, user: str, schema: dict) -> dict:
        out = self._request("/api/chat", {
            "model": self.model, "stream": False, "format": schema,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"temperature": 0, "num_predict": 1500, "num_ctx": 4096},
        })
        content = (out.get("message") or {}).get("content", "")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            raise invalid_model_output()

    def status(self, deep: bool = False) -> ModelStatus:
        try:
            tags = self._request("/api/tags", timeout=5)
        except Exception:
            return ModelStatus(False, self.model, False, None,
                               "Install and start Ollama (https://ollama.com), then run: ollama serve")
        names = {m.get("name", "") for m in tags.get("models", [])}
        installed = self.model in names or f"{self.model}:latest" in names
        if not installed:
            return ModelStatus(True, self.model, False, None, f"Run: ollama pull {self.model}")
        ok = None
        if deep:
            try:
                self.chat_json("Reply with JSON only.", 'Return {"ok": true}',
                               {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]})
                ok = True
            except Exception:
                ok = False
        step = "Ready." if ok in (None, True) else \
            "Model is installed but failed a test run. Try a smaller model via OLLAMA_MODEL or close other programs."
        return ModelStatus(True, self.model, True, ok, step)
