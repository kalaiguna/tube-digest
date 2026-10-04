# tube-digest — Implementation Plan

Based on the execution plan in the project brief and Phase 1–2 implementation.

---

## Technical Decisions (Locked)

| # | Decision | Rationale |
|---|---|---|
| 1 | `FastAPI BackgroundTasks` for webhook handling, not Celery/RQ | Telegram times out after 10s. `BackgroundTasks` returns 200 immediately and runs the workflow in the same process — no extra broker infrastructure needed on Cloud Run. |
| 2 | `yt-dlp -o -` piped via `asyncio.subprocess.PIPE` to an `AsyncGenerator` | Avoids ffmpeg and disk writes. WebM/Opus bytes stream directly to Deepgram. Deepgram natively supports `audio/webm` — no transcoding needed. |
| 3 | Kroki via HTTP POST, not GET + base64/zlib | GET encoding fails for non-trivial diagrams due to URL length limits. POST body has no such constraint. |
| 4 | `@field_validator("visual_map", mode="before")` strips markdown fences | Gemini (Flash and Pro) reliably wraps Mermaid output in code fences regardless of prompting. The validator runs at model-parse time, before Kroki receives the string. |
| 5 | `tools/resend_email.py` (not `tools/resend.py`) | A file named `resend.py` inside the `app/` package shadows the `resend` third-party package on the import path, causing `ImportError`. The rename costs nothing. |
| 6 | Diagram embedded as base64 `data:image/png;base64,…` URI | Makes the email self-contained — no external image host, no link rot, no privacy leak from the recipient's email client prefetching a remote URL. |
| 7 | Two-pass synthesis: Flash for structure, Pro for deep dive | Flash with `response_schema` reliably produces structured JSON for TL;DR + Mermaid. Pro produces higher-quality long-form prose. Splitting the calls isolates reliability from quality. |
| 8 | `youtube-transcript-api` in a thread executor | The library is synchronous. Running it in `asyncio.get_event_loop().run_in_executor(None, ...)` avoids blocking the event loop during network I/O. |
| 9 | `SynthesisResult` is the `response_schema` for Gemini Flash | Pydantic v2 models are directly accepted by `google-genai`'s `response_schema` parameter. The same model validates the JSON string returned by the model, meaning type errors surface immediately. |
| 10 | `containerConcurrency=1` on Cloud Run | Prevents concurrent webhook requests from racing on any shared state inside the FastAPI process. `BackgroundTasks` queuing is sufficient for expected load. |

---

## Phase Plan

| Phase | Version | Status | Deliverables |
|---|---|---|---|
| 1 | v0.1.0 | ✅ Done | Scaffolding: `requirements.txt`, `Dockerfile`, directory structure, `__init__.py` stubs |
| 2 | v0.2.0 | ✅ Done | Core tools: `transcript.py`, `deepgram_stream.py`, `kroki.py`, `resend_email.py`, `schemas/summary.py`, `templates/email.html` |
| 3 | v0.3.0 | ✅ Done | Agents & workflow: `ingestion.py`, `synthesis.py`, `delivery.py`, `workflow.py` |
| 4 | v1.0.0 | 🔜 Next | Entry point: `main.py` — FastAPI webhook + BackgroundTasks wiring |
| 5 | v1.1.0 | Candidate | Unit tests — pytest suite, all external services mocked |

---

## File-Level Implementation Notes

### Phase 3 — Agents & Workflow

**`app/agents/ingestion.py`**
```python
# Try transcript first; fall back to audio on these exceptions:
from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled

async def ingest(video_url: str) -> tuple[str, str]:
    # Returns (video_id, transcript_text)
    try:
        return await get_transcript(video_url)
    except (TranscriptsDisabled, NoTranscriptFound):
        video_id = _extract_video_id(video_url)
        text = await transcribe_audio(video_url)
        return video_id, text
```

**`app/agents/synthesis.py`**

Two separate Gemini calls:

1. **Flash + `response_schema`** — produces `tldr` and `visual_map` as structured JSON:
   ```python
   config = types.GenerateContentConfig(
       response_mime_type="application/json",
       response_schema=SynthesisResult,
   )
   ```
2. **Pro — standard generation** — produces `deep_dive` prose with a richer prompt
   that references the TL;DR to stay consistent.

The two results are merged into a single `SynthesisResult` before passing to delivery.

**`app/agents/delivery.py`**
```python
async def deliver(result: SynthesisResult, video_url: str, video_title: str | None):
    diagram_bytes = await render_diagram(result.visual_map)  # may be None on error
    await send_digest_email(
        to=os.environ["TO_EMAIL"],
        video_url=video_url,
        video_title=video_title,
        tldr=result.tldr,
        deep_dive=result.deep_dive,
        diagram_bytes=diagram_bytes,
    )
```

**`app/workflow.py`**
```python
async def run_workflow(video_url: str):
    video_id, transcript = await ingest(video_url)
    result = await synthesize(transcript)
    await deliver(result, video_url, video_title=None)
```

---

### Phase 4 — Entry Point

**`app/main.py`**
- `POST /telegram-webhook` — validates `X-Telegram-Bot-Api-Secret-Token`, extracts the
  URL from `message.text`, adds `run_workflow(url)` to `BackgroundTasks`, returns
  `{"ok": True}`.
- `GET /health` — returns `{"status": "ok"}` for Cloud Run health checks.
- Startup: validates that all required env vars are present; logs a startup message.

```python
@app.post("/telegram-webhook")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if x_telegram_bot_api_secret_token != os.environ.get("TELEGRAM_WEBHOOK_SECRET"):
        raise HTTPException(status_code=403)
    payload = await request.json()
    url = payload["message"]["text"].strip()
    background_tasks.add_task(run_workflow, url)
    return {"ok": True}
```

---

## Phase 5 — Unit Tests

Written after Phase 4. All external services (Gemini, Deepgram, Kroki, Resend, YouTube)
are mocked — no real API calls in the test suite.

**Setup files:**
- `pytest.ini` — `asyncio_mode = auto` so async tests need no decorator
- `tests/conftest.py` — shared fixtures (mock env vars, sample transcript, fake HTTP responses)

### Test cases

**`tests/test_schema.py`**

| ID | Case | Assert |
|---|---|---|
| T01 | `visual_map` with ` ```mermaid…``` ` fence | Fence stripped, clean code returned |
| T02 | `visual_map` with plain ` ``` ` fence | Fence stripped |
| T03 | `visual_map` with no fence | Value returned unchanged |
| T04 | `visual_map` non-string value | Returned as-is (no crash) |

**`tests/test_transcript.py`**

| ID | Case | Assert |
|---|---|---|
| T05 | `_extract_video_id` — `watch?v=` URL | Correct ID |
| T06 | `_extract_video_id` — `youtu.be/` URL | Correct ID |
| T07 | `_extract_video_id` — `/shorts/` URL | Correct ID |
| T08 | `_extract_video_id` — `/embed/` URL | Correct ID |
| T09 | `_extract_video_id` — unrecognised URL | Raises `ValueError` |
| T10 | `get_transcript` — `NoTranscriptFound` propagates to caller | Exception not swallowed |

**`tests/test_deepgram.py`**

| ID | Case | Assert |
|---|---|---|
| T11 | `_yt_dlp_audio_stream` — yields chunks, reaps process on EOF | All bytes yielded; `process.wait()` called |
| T12 | `transcribe_audio` — valid Deepgram JSON | Returns transcript string |
| T13 | `transcribe_audio` — malformed Deepgram response | Raises `RuntimeError` |
| T14 | `transcribe_audio` — HTTP 4xx from Deepgram | `raise_for_status` propagates |

**`tests/test_kroki.py`**

| ID | Case | Assert |
|---|---|---|
| T15 | `render_diagram` — POST body is raw Mermaid string | `Content-Type: text/plain` |
| T16 | `render_diagram` — 200 response | Returns PNG bytes |
| T17 | `render_diagram` — 4xx response | `HTTPStatusError` raised |

**`tests/test_resend_email.py`**

| ID | Case | Assert |
|---|---|---|
| T18 | `_diagram_data_uri` | Returns valid `data:image/png;base64,…` string |
| T19 | `send_digest_email` — with diagram | HTML contains `data:image/png` |
| T20 | `send_digest_email` — without diagram | HTML renders without diagram block; no crash |
| T21 | `send_digest_email` — returns email ID | Resend mock `{"id": "…"}` threaded through |

**`tests/test_ingestion.py`**

| ID | Case | Assert |
|---|---|---|
| T22 | Caption path — `get_transcript` succeeds | Returns `(video_id, text)` |
| T23 | Fallback — `TranscriptsDisabled` triggers audio path | `transcribe_audio` called |
| T24 | Fallback — `NoTranscriptFound` triggers audio path | `transcribe_audio` called |

**`tests/test_synthesis.py`**

| ID | Case | Assert |
|---|---|---|
| T25 | Flash returns empty text | Raises `RuntimeError` with `finish_reason` |
| T26 | Pro call fails | Flash `deep_dive` retained in result |
| T27 | Both passes succeed | `SynthesisResult` has Pro `deep_dive` |

**`tests/test_delivery.py`**

| ID | Case | Assert |
|---|---|---|
| T28 | Kroki succeeds | `diagram_bytes` passed to email |
| T29 | Kroki raises | Email sent with `diagram_bytes=None` |
| T30 | `TO_EMAIL` missing from env | Raises `KeyError` before email send |

**`tests/test_main.py`**

| ID | Case | Assert |
|---|---|---|
| T31 | Wrong secret token | 403 response |
| T32 | Valid URL + correct token | 200 response; `run_workflow` queued |
| T33 | Non-URL text | 400 response |
| T34 | `GET /health` | 200 `{"status": "ok"}` |

**`tests/test_workflow.py`**

| ID | Case | Assert |
|---|---|---|
| T35 | All stages succeed | `deliver` called with `SynthesisResult` |
| T36 | `ingest` raises | Exception logged and re-raised |
| T37 | `synthesize` raises | Exception logged and re-raised |
