# tube-digest

> **Too busy to watch? Just send the link.**

YouTube has some of the best educational content in the world — but most videos run
30, 60, even 90 minutes. Finding time to sit and watch is increasingly rare.

**tube-digest** solves this: send any YouTube URL to a Telegram bot and receive a
structured email digest in minutes — no app to open, no dashboard to check. The email
lands in your inbox and is designed to be read in under two minutes.

Each digest contains three tiers of **original AI-written content**:

- **TL;DR** — the core idea in one paragraph
- **Deep Dive** — key arguments, evidence, and takeaways in full detail
- **Visual Map** — a concept diagram showing how the ideas connect

> **This is not a transcription service.**
> tube-digest never returns the video's words verbatim. Gemini reads the source
> material and writes a completely new synthesis — the way a knowledgeable colleague
> would explain the video to you in their own words.

Works on any YouTube video, even those without captions (audio is transcribed
internally as source material, then discarded — it never appears in the email).

---

## How it works

```
You send a YouTube URL via Telegram
        │
        ▼
Bot replies instantly ("Got it, processing…")
        │
        ▼
Pipeline runs in the background:
  1. Fetches the transcript (or transcribes the audio)
  2. Gemini synthesises TL;DR + Deep Dive + Visual Map
  3. Diagram is rendered to PNG
  4. Polished HTML email is sent to your inbox
```

---

## Architecture

```
Telegram ──► FastAPI webhook ──► BackgroundTask
                                      │
                          ┌───────────▼──────────────┐
                          │       workflow.py          │
                          │  IngestionAgent            │
                          │    ├─ YouTubeTranscriptAPI │
                          │    └─ yt-dlp → Deepgram   │
                          │  SynthesisAgent (Gemini)   │
                          │    ├─ Flash (structured)   │
                          │    └─ Pro (deep dive)      │
                          │  DeliveryAgent             │
                          │    ├─ Kroki (diagram PNG)  │
                          │    └─ Resend (HTML email)  │
                          └───────────────────────────┘
```

```
Telegram ──► FastAPI webhook ──► BackgroundTask
                                      │
                          ┌───────────▼──────────────┐
                          │       workflow.py          │
                          │  IngestionAgent            │
                          │    ├─ YouTubeTranscriptAPI │
                          │    └─ yt-dlp → Deepgram   │
                          │  SynthesisAgent (Gemini)   │
                          │    ├─ Flash (structured)   │
                          │    └─ Pro (deep dive)      │
                          │  DeliveryAgent             │
                          │    ├─ Kroki (diagram PNG)  │
                          │    └─ Resend (HTML email)  │
                          └───────────────────────────┘
```

## Tech Stack

| Layer | Library |
|---|---|
| Orchestration | `google-adk`, `google-genai` |
| Web | `fastapi`, `uvicorn` |
| Telegram | `python-telegram-bot` |
| Transcript | `youtube-transcript-api`, `yt-dlp` |
| Transcription fallback | Deepgram REST API via `httpx` |
| Diagram rendering | Kroki.io REST API via `httpx` |
| Email | `resend`, `jinja2` |
| Validation | `pydantic` v2 |

## Setup

### Prerequisites
- Python 3.12+
- A Telegram Bot token (`@BotFather`)
- Google Cloud project with Vertex AI / Gemini API enabled
- Deepgram API key (for audio fallback)
- Resend API key + verified sending domain

### Environment Variables

Create `app/.env` (never commit this file):

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_WEBHOOK_SECRET=...          # random string for webhook validation

GOOGLE_API_KEY=...                   # OR use GOOGLE_APPLICATION_CREDENTIALS
GOOGLE_CLOUD_PROJECT=...

DEEPGRAM_API_KEY=...

RESEND_API_KEY=...
FROM_EMAIL=digest@yourdomain.com
TO_EMAIL=you@yourdomain.com          # recipient address
```

### Local Development

```bash
cd app
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

uvicorn main:app --reload --port 8080
```

Expose locally with `ngrok http 8080` and set the webhook:

```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<ngrok>.ngrok.io/telegram-webhook"
```

### Docker / Cloud Run

```bash
cd app
docker build -t tube-digest .
docker run --env-file .env -p 8080:8080 tube-digest

# Deploy to Cloud Run
gcloud run deploy tube-digest \
  --source . \
  --region us-central1 \
  --set-env-vars="$(cat .env | tr '\n' ',')"
```

## Project Layout

```
tube-digest/
├── app/
│   ├── agents/
│   │   ├── ingestion.py    # transcript & audio fallback
│   │   ├── synthesis.py    # Gemini Flash + Pro summarisation
│   │   └── delivery.py     # diagram render + email dispatch
│   ├── tools/
│   │   ├── transcript.py   # YouTubeTranscriptAPI wrapper
│   │   ├── deepgram_stream.py  # yt-dlp → Deepgram async stream
│   │   ├── kroki.py        # Mermaid → PNG via Kroki POST
│   │   └── resend.py       # Jinja2 email via Resend API
│   ├── schemas/
│   │   └── summary.py      # Pydantic output schema
│   ├── templates/
│   │   └── email.html      # Jinja2 HTML email template
│   ├── main.py             # FastAPI entry point
│   ├── workflow.py         # ADK agent orchestration
│   ├── requirements.txt
│   └── Dockerfile
├── README.md
├── CHANGELOG.md
└── LICENSE
```

## Cost

tube-digest uses paid APIs. Costs are low for personal use but vary by video length
and whether captions are available.

| Scenario | What runs | Approximate cost per video |
|---|---|---|
| Video has captions | Gemini Flash + Gemini Pro | ~$0.02–0.05 |
| No captions (audio fallback) | Gemini Flash + Gemini Pro + Deepgram | ~$0.20–0.25 |

**Breakdown by service:**

- **Gemini Flash** (`gemini-2.0-flash`) — structured TL;DR + Visual Map. A 30-minute
  video produces ~10–15K input tokens. Cost: fractions of a cent.
- **Gemini Pro** (`gemini-2.5-pro`) — Deep Dive prose. Same input; higher per-token
  price. Dominant cost driver for caption-only runs: ~$0.02–0.05.
- **Deepgram** (`nova-2`) — only invoked when captions are unavailable. Priced per
  minute of audio (~$0.006/min). A 30-minute video costs ~$0.18.
- **Resend** — free tier covers 100 emails/day; well within personal use limits.
- **Cloud Run** — scale-to-zero. Idle cost is zero. A few seconds of CPU per video.

Monthly cost for a heavy personal user (2–3 videos/day, mostly captioned): **~$3–5/month**.

## Documentation

| Document | Contents |
|---|---|
| [docs/spec.md](docs/spec.md) | Architecture, critical constraints, ADK patterns, env vars |
| [docs/guide.md](docs/guide.md) | User guide, developer guide, DevOps deployment |
| [docs/implementation-plan.md](docs/implementation-plan.md) | Phase plan, locked technical decisions, file-level notes |
| [docs/backlog.md](docs/backlog.md) | Milestone map, feature roadmap, future ideas |

## License

MIT — see [LICENSE](LICENSE).
