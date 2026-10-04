# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Phase 1: Project scaffolding — `requirements.txt`, `Dockerfile`, directory structure.
- Phase 2: Core tools — `transcript.py`, `deepgram_stream.py`, `kroki.py`, `resend_email.py`,
  `schemas/summary.py` with Pydantic `@field_validator` for Mermaid code-fence stripping.
- Phase 3: Agents & workflow — `ingestion.py` (transcript → Deepgram fallback),
  `synthesis.py` (Gemini Flash structured + Pro prose two-pass), `delivery.py`
  (Kroki non-fatal + Resend), `workflow.py` sequential pipeline orchestrator.
- `docs/` structure: `spec.md`, `guide.md`, `implementation-plan.md`, `backlog.md`.
