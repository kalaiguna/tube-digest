"""Ingestion agent: fetches the video transcript.

Primary path:  youtube-transcript-api (fast, no audio download needed)
Fallback path: yt-dlp audio stream → Deepgram transcription
"""

import logging

from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled

from tools.deepgram_stream import transcribe_audio
from tools.transcript import _extract_video_id, get_transcript

logger = logging.getLogger(__name__)


async def ingest(video_url: str) -> tuple[str, str]:
    """Return ``(video_id, transcript_text)`` for *video_url*.

    Tries the YouTube caption track first. Falls back to yt-dlp + Deepgram
    audio transcription when captions are disabled or unavailable.
    """
    try:
        video_id, text = await get_transcript(video_url)
        logger.info("transcript fetched video_id=%s chars=%d", video_id, len(text))
        return video_id, text

    except (TranscriptsDisabled, NoTranscriptFound) as exc:
        logger.info(
            "no caption track (%s) — falling back to audio transcription",
            type(exc).__name__,
        )

    # _extract_video_id is a cheap URL parse — safe to call again here.
    video_id = _extract_video_id(video_url)
    text = await transcribe_audio(video_url)
    logger.info(
        "audio transcription complete video_id=%s chars=%d", video_id, len(text)
    )
    return video_id, text
