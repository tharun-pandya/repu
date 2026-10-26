# Contributing to Repu

Thanks for your interest in improving Repu.

## Ground rules

- **Privacy first.** Never commit or attach real chat exports. Use the fictional data in `sample_data/` or synthetic text.
- **The model is untrusted.** Changes must keep dates, evidence checks and export gating in deterministic code.
- **No chat content in logs.** Log counts, durations and error types only.

## Development setup

```bash
git clone https://github.com/OWNER/repu.git && cd repu
make install
```

## Before opening a pull request

```bash
make lint      # ruff
make test      # pytest + unittest (mocked inference, no model download)
make test-ui   # jsdom UI tests
```

CI runs the same checks on every push and pull request. Add or update tests for any behaviour change, and update the
relevant file in `docs/` and `CHANGELOG.md`.

## Pull request guidelines

- Keep changes focused; one logical change per pull request.
- Describe what changed and why, and how you tested it.
- Note whether you ran the opt-in real-model test (`make local-model-test`).

## Reporting bugs and requesting features

Use the issue templates. For security issues, follow [SECURITY.md](SECURITY.md) instead.

## Code of conduct

Participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md).
