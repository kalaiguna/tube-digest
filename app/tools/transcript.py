import asyncio
import re
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)


def _extract_video_id(url: str) -> str:
    """Parse a YouTube URL and return the video ID."""
    parsed = urlparse(url)

    # youtu.be/<id>
    if parsed.netloc in ("youtu.be", "www.youtu.be"):
        return parsed.path.lstrip("/")

    # youtube.com/watch?v=<id>  or  /shorts/<id>  or  /embed/<id>  or  /v/<id>
    if "youtube.com" in parsed.netloc:
        qs = parse_qs(parsed.query)
        if "v" in qs:
            return qs["v"][0]
        path_parts = [p for p in parsed.path.split("/") if p]
        if len(path_parts) >= 2 and path_parts[0] in ("shorts", "embed", "v"):
            return path_parts[1]

    raise ValueError(f"Cannot extract video ID from URL: {url}")


async def get_transcript(video_url: str) -> tuple[str, str]:
    """Return ``(video_id, transcript_text)`` for *video_url*.

    Raises ``TranscriptsDisabled`` or ``NoTranscriptFound`` when no captions
    are available, so the caller can fall back to the audio transcription path.
    """
    video_id = _extract_video_id(video_url)

    loop = asyncio.get_running_loop()
    transcript_list = await loop.run_in_executor(
        None,
        lambda: YouTubeTranscriptApi.get_transcript(
            video_id,
            languages=["en", "en-US", "en-GB"],
        ),
    )

    text = " ".join(entry["text"] for entry in transcript_list)
    # Collapse artefacts like "[Music]" and "[Applause]"
    text = re.sub(r"\[[^\]]+\]", "", text)
    text = re.sub(r"\s{2,}", " ", text).strip()

    return video_id, text
