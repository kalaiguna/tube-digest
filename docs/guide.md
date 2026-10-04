# tube-digest — Guide

---

## 1. For Users

### What is this?

Send any YouTube URL to the bot on Telegram and receive an email with:

- **TL;DR** — one paragraph capturing the core idea
- **Deep Dive** — detailed multi-paragraph analysis with key points and takeaways
- **Visual Map** — a Mermaid concept diagram rendered as a PNG image

The bot replies immediately to confirm it received your request. The email arrives
within 1–3 minutes depending on video length.

### What this is NOT

**tube-digest is not a transcription service.** It does not return the video's
words, captions, or any verbatim excerpt.

What it does: Gemini reads the source transcript as input material, then writes a
completely original synthesis — the same way a knowledgeable colleague would explain
the video to you in their own words. The transcript is internal scaffolding; it never
appears in the email.

If you need the raw transcript of a video, this is the wrong tool.

### Usage

1. Send the bot a YouTube URL (any format works):
   - `https://www.youtube.com/watch?v=...`
   - `https://youtu.be/...`
   - `https://www.youtube.com/shorts/...`
2. The bot acknowledges your request instantly.
3. Check your inbox — the digest email arrives shortly.

### Audio fallback

If a video has no captions, the system automatically fetches the audio via `yt-dlp`
and transcribes it through Deepgram. This path takes a bit longer but requires no
action on your part. The audio bytes are streamed and discarded — Deepgram returns
text only, which becomes the internal source material for Gemini.

### Cost per video

tube-digest calls paid APIs. Costs are low but not zero.

| Scenario | Services called | Approx. cost |
|---|---|---|
| Video has captions | Gemini Flash + Gemini Pro | ~$0.02–0.05 |
| No captions (audio fallback) | + Deepgram audio transcription | ~$0.20–0.25 |

**Gemini Flash** handles structured output (TL;DR + Visual Map) — fractions of a
cent for a typical video. **Gemini Pro** handles the Deep Dive prose and is the
main cost driver on caption-only runs. **Deepgram** (`nova-2`, ~$0.006/minute) only
runs when there are no captions — a 30-minute video costs ~$0.18.

Resend's free tier (100 emails/day) comfortably covers personal use. Cloud Run
scales to zero — no idle cost.

A heavy personal user watching 2–3 videos a day (mostly captioned) can expect
roughly **$3–5/month** in API spend.

---

## 2. Security

### Webhook validation

The Telegram webhook endpoint validates the `X-Telegram-Bot-Api-Secret-Token` header
against `TELEGRAM_WEBHOOK_SECRET`. Requests without a matching token are rejected with
`403`.

### Audio data

- Audio bytes are streamed directly from `yt-dlp` to Deepgram — they are never written
  to disk or stored in memory beyond the active stream.
- Deepgram receives and processes the audio bytes, then returns text only. No audio is
  retained by this service.

### API keys

API keys (`DEEPGRAM_API_KEY`, `RESEND_API_KEY`, `GOOGLE_API_KEY`) are loaded from
environment variables injected by Cloud Run Secret Manager at runtime. They are never
embedded in the container image or logged.

---

## 3. For Developers

### Tech stack

| Layer | Technology |
|---|---|
| AI orchestration | `google-adk`, `google-genai` |
| Structured output | Gemini Flash with `response_schema=SynthesisResult` |
| Web framework | `fastapi`, `uvicorn` |
| Telegram | `python-telegram-bot` (webhook mode) |
| Transcript | `youtube-transcript-api` |
| Audio fallback | `yt-dlp` (subprocess pipe) + Deepgram REST via `httpx` |
| Diagram rendering | Kroki.io REST API (HTTP POST) |
| Email | `resend` SDK + Jinja2 |
| Validation | Pydantic v2 |
| Runtime | Python 3.12, Cloud Run |

### File structure

```
tube-digest/
├── app/
│   ├── agents/
│   │   ├── ingestion.py       transcript → audio fallback chain
│   │   ├── synthesis.py       Gemini Flash (structured) + Pro (prose)
│   │   └── delivery.py        Kroki diagram + Resend email
│   ├── tools/
│   │   ├── transcript.py      YouTubeTranscriptApi wrapper
│   │   ├── deepgram_stream.py yt-dlp → Deepgram async stream
│   │   ├── kroki.py           Mermaid → PNG via Kroki POST
│   │   └── resend_email.py    Jinja2 email via Resend API
│   ├── schemas/
│   │   └── summary.py         SynthesisResult Pydantic model
│   ├── templates/
│   │   └── email.html         Jinja2 HTML email template
│   ├── main.py                FastAPI entry point + webhook handler
│   ├── workflow.py            Orchestrates ingestion → synthesis → delivery
│   ├── requirements.txt
│   └── Dockerfile
├── docs/
│   ├── spec.md                Architecture & constraint spec
│   ├── guide.md               This file
│   ├── implementation-plan.md Phase plan + technical decisions
│   └── backlog.md             Milestone map + roadmap
├── README.md
├── CHANGELOG.md
└── LICENSE
```

### Running locally

```bash
cd app
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # fill in your keys
uvicorn main:app --reload --port 8080
```

Expose to Telegram with ngrok, then register the webhook:

```bash
ngrok http 8080
curl "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://<ngrok-id>.ngrok.io/telegram-webhook" \
  -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>"
```

### How to add a new tool

1. Create `app/tools/<tool_name>.py` with an `async` function.
2. Import it in the relevant agent (`ingestion.py`, `synthesis.py`, or `delivery.py`).
3. Add the function to the agent's tool list (ADK `tools=[]` parameter).

### How to add a new agent

1. Create `app/agents/<skill>.py` exporting an ADK `Agent` instance.
2. Import and call it in `app/workflow.py` in the correct pipeline position.
3. Wire any new environment variables to `app/main.py` startup validation.

### Observability

| Signal | Where to look |
|---|---|
| Workflow errors | Cloud Run logs — filter `severity=ERROR` |
| Deepgram transcription | Log the `transcript` length in `deepgram_stream.py` |
| Kroki failures | `response.raise_for_status()` propagates; logged by FastAPI exception handler |
| Email delivery | Resend dashboard → email log |

---

## 4. For DevOps

### Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.12 | Runtime |
| Docker | Container builds |
| `gcloud` CLI | Authenticated, project set |
| Telegram Bot Token | From `@BotFather` |
| Google API key | Gemini API (Google AI Studio) or Vertex AI ADC |
| Deepgram API key | `deepgram.com` |
| Resend API key + domain | `resend.com` — domain must be verified |

### Environment variables

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_WEBHOOK_SECRET=...          # any long random string

GOOGLE_API_KEY=...                   # OR use Application Default Credentials
GOOGLE_CLOUD_PROJECT=...

DEEPGRAM_API_KEY=...

RESEND_API_KEY=...
FROM_EMAIL=digest@yourdomain.com
TO_EMAIL=you@yourdomain.com
```

### Building and deploying to Cloud Run

```bash
# Build and push
cd app
gcloud builds submit --tag gcr.io/PROJECT_ID/tube-digest .

# Deploy (first time)
gcloud run deploy tube-digest \
  --image gcr.io/PROJECT_ID/tube-digest \
  --region us-central1 \
  --allow-unauthenticated \
  --max-instances 1 \
  --concurrency 1 \
  --set-secrets "TELEGRAM_BOT_TOKEN=telegram-bot-token:latest,\
TELEGRAM_WEBHOOK_SECRET=telegram-webhook-secret:latest,\
GOOGLE_API_KEY=google-api-key:latest,\
DEEPGRAM_API_KEY=deepgram-api-key:latest,\
RESEND_API_KEY=resend-api-key:latest" \
  --set-env-vars "FROM_EMAIL=digest@yourdomain.com,TO_EMAIL=you@yourdomain.com"

# Register Telegram webhook
SERVICE_URL=$(gcloud run services describe tube-digest --region us-central1 --format 'value(status.url)')
curl "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=${SERVICE_URL}/telegram-webhook" \
  -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>"
```

### Updating after a code change

```bash
cd app
gcloud builds submit --tag gcr.io/PROJECT_ID/tube-digest .
gcloud run services update tube-digest \
  --image gcr.io/PROJECT_ID/tube-digest \
  --region us-central1
```

### Concurrency model

`--max-instances 1` and `--concurrency 1` keep a single Cloud Run instance active. This
prevents any shared in-memory state from being split across replicas. Scale-to-zero
means no idle cost — the instance spins up on the first incoming webhook.

The `FastAPI BackgroundTasks` pattern means the heavy workflow runs after the 200
response is sent, so Telegram never sees a timeout even for long videos.
