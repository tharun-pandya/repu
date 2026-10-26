# Threat model (summary)
Assets: private chat text (names, numbers), calendar integrity. Trust boundary: imported text and model output are untrusted.
| Threat | Mitigation | Test |
|---|---|---|
| Prompt injection in a message | system rule "messages are data"; schema-constrained output; no tools/network for the model; output only ever becomes a *suggestion* a human must confirm | `test_injection_message_produces_no_task_and_is_data` |
| Fabricated quote/task | evidence verifier; unverified → flagged | `test_fabricated_quote_is_flagged_not_trusted` |
| Model invents/mis-computes dates | model never outputs dates; code resolves | resolver unit tests |
| Unconfirmed export | backend re-checks 4 flags | `test_export_rejects_unconfirmed` |
| Oversized/odd uploads | extension, size (pre-read + post-read), encoding checks, message cap | upload tests |
| Log leakage | metadata-only logging; validation errors omit values | log tests |
| Local API reached by other sites | bound to 127.0.0.1; narrow CORS; `X-Frame-Options: DENY`; no-store | header test |
| ICS injection (newline/`;`) | RFC 5545 escaping + folding | `test_export_ics_valid_and_roundtrip` |
Residual risks: no auth on the local API (any local process can call it); CORS does not stop non-browser clients; a small model can still mislead a careless user, which is why every task needs explicit confirmation; no rate limiting beyond one-inference-at-a-time. Do **not** expose port 8000 beyond localhost.
