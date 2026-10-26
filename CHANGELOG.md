# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-26

### Added
- WhatsApp export parser (Android/iOS, 12/24 h, multiline, system and attachment lines, UTF-8/BOM/UTF-16).
- Local extraction via Ollama with schema-constrained JSON, validation and one repair retry.
- Evidence verification, deterministic Telugu/Tenglish/English date resolution and ambiguity/ownership policy.
- Review UI with AM/PM chips, four-step confirmation, timeline, dark mode, CSV and `.ics` export.
- Morning brief and overnight folder watcher.
- Hosted demo mode (`DEMO_MODE`), Dockerfile and Render blueprint.
- Test suites (unit, API, watcher, UI smoke) and an evaluation harness with a synthetic dataset.
