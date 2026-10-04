# tube-digest — Backlog & Roadmap

---

## Milestone map

| Version | Theme | Status |
|---|---|---|
| v0.1.0 | Scaffolding — `requirements.txt`, Dockerfile, directory structure | ✅ Done |
| v0.2.0 | Core tools — transcript, Deepgram stream, Kroki, Resend, Pydantic schema | ✅ Done |
| v0.3.0 | Agents & workflow — ADK ingestion → synthesis → delivery pipeline | ✅ Done |
| v1.0.0 | Entry point — FastAPI webhook, BackgroundTasks, health endpoint | 🔜 Next |
| v1.1.0 | Unit tests — pytest suite covering tools, schema, agents, and main | Candidate |
| v1.2.0 | Reliability — retry logic, error Telegram replies, structured logging | Candidate |
| v1.3.0 | Multi-user — per-user email config stored in Firestore / env map | Candidate |
| v2.0.0 | Playlist support — batch-digest a YouTube playlist into one email | Future |
| v2.1.0 | Notion export — push digest blocks into a Notion page via API | Future |
| v3.0.0 | Web companion — dashboard showing digest history from Firestore | Future |

---

## v0.1.0 — Scaffolding ✅

- `requirements.txt` with pinned versions
- `Dockerfile` — multi-stage, non-root user, Cloud Run `$PORT`
- `.dockerignore`
- Full directory structure: `agents/`, `tools/`, `schemas/`, `templates/`
- Empty `__init__.py` stubs for all packages
- Phase 3/4 stub files (`main.py`, `workflow.py`, agent files)
- Project-level files: `README.md`, `CHANGELOG.md`, `LICENSE`, `.gitignore`
- `docs/` structure: `spec.md`, `guide.md`, `implementation-plan.md`, `backlog.md`

---

## v0.2.0 — Core Tools ✅

- `schemas/summary.py` — `SynthesisResult` with `@field_validator` stripping Mermaid
  code fences
- `tools/transcript.py` — YouTube transcript extraction; handles all URL formats;
  runs sync library in thread executor; strips `[Music]` noise
- `tools/deepgram_stream.py` — `yt-dlp -o -` → async generator → Deepgram HTTP POST;
  zero disk I/O; zero ffmpeg; 64 KiB chunked reads
- `tools/kroki.py` — Mermaid → PNG via Kroki HTTP POST (no base64/zlib GET)
- `tools/resend_email.py` — Jinja2 render + base64 diagram embedding + Resend SDK
- `templates/email.html` — responsive HTML email with TL;DR card, deep-dive section,
  diagram block, and footer

---

## v0.3.0 — Agents & Workflow ✅

- `agents/ingestion.py` — transcript → Deepgram fallback chain; re-uses `_extract_video_id` on the fallback path
- `agents/synthesis.py` — Flash pass with `response_schema=_TierOneOutput`; Pro pass overrides `deep_dive`; Flash draft retained as fallback if Pro fails
- `agents/delivery.py` — Kroki non-fatal (email sent without diagram on failure); `TO_EMAIL` injected from env
- `workflow.py` — `run_workflow(video_url)` sequential pipeline; exceptions logged and re-raised for BackgroundTask visibility

See [implementation-plan.md — Phase 3](implementation-plan.md#phase-3--agents--workflow)
for file-level notes.

---

## v1.0.0 — Entry Point 🔜

- `main.py` — FastAPI `/telegram-webhook` with `BackgroundTasks`
- `X-Telegram-Bot-Api-Secret-Token` validation
- `/health` endpoint for Cloud Run probes
- Startup env-var validation

See [implementation-plan.md — Phase 4](implementation-plan.md#phase-4--entry-point)
for file-level notes.

---

## v1.1.0 — Unit Tests (Candidate)

**Scope:** pytest suite with no real API calls — all external services mocked.

| Module | Test cases |
|---|---|
| `schemas/summary.py` | Validator strips ` ```mermaid…``` `, plain ` ``` `, and passes through clean code |
| `tools/transcript.py` | `_extract_video_id` for all URL formats (watch, youtu.be, shorts, embed); `NoTranscriptFound` propagates |
| `tools/deepgram_stream.py` | Async generator yields chunks and reaps subprocess on EOF; response JSON parsed correctly; malformed response raises `RuntimeError` |
| `tools/kroki.py` | POST body is raw Mermaid string; `raise_for_status` triggers on 4xx |
| `tools/resend_email.py` | Base64 data URI generated correctly; Jinja2 renders without diagram when `diagram_bytes=None` |
| `agents/ingestion.py` | Caption path returns `(video_id, text)`; fallback triggered on `TranscriptsDisabled` and `NoTranscriptFound` |
| `agents/synthesis.py` | Empty Flash response raises `RuntimeError`; Pro failure retains Flash `deep_dive` |
| `agents/delivery.py` | Kroki failure → email sent without diagram; `TO_EMAIL` read from env |
| `main.py` | Wrong secret token → 403; valid URL → 200 + task queued; missing `message.text` → 400 |
| `workflow.py` | Full pipeline with all tools mocked; exception in any stage propagates |

**Setup:** `pytest` + `pytest-asyncio` (`asyncio_mode = auto`). Add `pytest.ini` and `tests/` directory.

---

## v1.2.0 — Reliability (Candidate)

- Retry with exponential backoff for Kroki and Deepgram calls
- Send a Telegram error message to the user when the pipeline fails (instead of silent
  failure)
- Structured JSON logging for Cloud Logging compatibility
- `PIPELINE_TIMEOUT_SECONDS` env var to cap runaway long videos

---

## v1.3.0 — Multi-user (Candidate)

**Problem:** `TO_EMAIL` is a single static env var — every Telegram user sends their
digest to the same address.

**Solution:**
- Store `{telegram_user_id: email_address}` in Firestore (or a JSON env var for small
  deploys)
- Webhook handler looks up the sender's user ID and routes the email accordingly
- Fall back to `TO_EMAIL` if no mapping exists (single-user mode preserved)

---

## v2.0.0 — Playlist Support (Future)

Accept a YouTube playlist URL and send one combined email with a digest per video,
ordered chronologically. Cap at configurable `MAX_PLAYLIST_VIDEOS`.

---

## v2.1.0 — Notion Export (Future)

After synthesising, push the TL;DR, deep-dive, and diagram to a Notion page via the
Notion API. Useful for building a personal knowledge base from watched videos.

---

## v3.0.0 — Web Companion (Future)

A Firestore-backed web dashboard showing:
- Recent digests (title, TL;DR preview, date)
- Visual map thumbnails
- Full deep-dive view per video

---

## Dev tooling (not versioned)

### Google Cloud MCP (candidate)

`gcloud-mcp` (`googleapis/gcloud-mcp`) in Claude Code sessions would allow inspecting
Cloud Run logs, env vars, and Cloud Scheduler jobs without leaving the editor. No app
code changes required — this is a dev workflow improvement only.

### ADK dev UI

`adk web` (ships with `google-adk`) provides a local browser UI for inspecting agent
runs and tool call events. Useful for debugging synthesis prompts without triggering
the full Telegram → email pipeline.

---

## Out of scope

- Storing transcripts or summaries in Firestore (v1.x is stateless)
- Support for non-YouTube video URLs (Vimeo, Loom, etc.)
- On-device/local model inference
