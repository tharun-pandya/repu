"""Stable, user-facing error codes. Messages never contain chat content."""
from __future__ import annotations


class AppError(Exception):
    def __init__(self, code: str, message: str, action: str = "", status: int = 400):
        super().__init__(message)
        self.code, self.message, self.action, self.status = code, message, action, status

    def to_dict(self, request_id: str = "") -> dict:
        return {"error": {"code": self.code, "message": self.message,
                          "action": self.action, "request_id": request_id}}


def invalid_file_type(): return AppError("INVALID_FILE_TYPE", "Only .txt WhatsApp exports are supported.", "Export the chat as text (without media).", 415)
def file_too_large(mb): return AppError("FILE_TOO_LARGE", f"File is larger than {mb} MB.", "Export a shorter date range or paste selected messages.", 413)
def unsupported_encoding(): return AppError("UNSUPPORTED_ENCODING", "Could not decode the file as UTF-8 or UTF-16.", "Re-export the chat or paste the text instead.", 422)
def no_messages(): return AppError("NO_MESSAGES", "No chat messages could be parsed.", "Check that this is a WhatsApp .txt export, or paste messages.", 422)
def session_expired(): return AppError("SESSION_EXPIRED", "This import session no longer exists.", "Import the chat again.", 404)
def model_unavailable(): return AppError("MODEL_UNAVAILABLE", "The local model is not available.", "Start Ollama and check the configured model (see /api/model/status).", 503)
def model_not_installed(m): return AppError("MODEL_NOT_INSTALLED", f"Model '{m}' is not installed in Ollama.", f"Run: ollama pull {m}", 503)
def model_timeout(): return AppError("MODEL_TIMEOUT", "The local model took too long to answer.", "Retry with a smaller batch size or a smaller model.", 504)
def invalid_model_output(): return AppError("INVALID_MODEL_OUTPUT", "The model returned output that failed validation.", "Retry, or use a smaller batch size.", 502)
def insufficient_memory(): return AppError("INSUFFICIENT_MEMORY", "The model could not be loaded (likely out of memory).", "Close other programs or choose a smaller model in OLLAMA_MODEL.", 503)
def invalid_date(msg): return AppError("INVALID_DATE", msg, "Fix the deadline and try again.", 422)
def export_rejected(msg): return AppError("EXPORT_REJECTED", msg, "Confirm task, owner, deadline and export approval for every selected task.", 422)
