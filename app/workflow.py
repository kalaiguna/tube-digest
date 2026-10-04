"""Pipeline orchestrator: ingestion → synthesis → delivery.

``run_workflow`` is the single entry point called by ``main.py`` inside a
FastAPI ``BackgroundTask``.  It runs after the Telegram webhook has already
returned HTTP 200, so exceptions here do not affect the webhook response —
they are logged and re-raised so the BackgroundTask machinery can record them.
"""

import logging

from agents.delivery import deliver
from agents.ingestion import ingest
from agents.synthesis import synthesize

logger = logging.getLogger(__name__)


async def run_workflow(video_url: str) -> None:
    """End-to-end pipeline for one YouTube URL."""
    logger.info("workflow started url=%s", video_url)

    try:
        # Stage 1 — fetch transcript or transcribe audio
        video_id, transcript = await ingest(video_url)

        # Stage 2 — AI summarisation (Flash structured + Pro prose)
        result = await synthesize(transcript)

        # Stage 3 — diagram render + email delivery
        await deliver(result, video_url=video_url)

        logger.info("workflow complete video_id=%s", video_id)

    except Exception:
        logger.exception("workflow failed url=%s", video_url)
        raise
