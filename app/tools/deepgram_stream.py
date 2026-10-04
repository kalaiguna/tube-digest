"""Audio transcription fallback via yt-dlp → Deepgram.

Design constraints (see EXECUTION PLAN):
- No ffmpeg, no /tmp writes.
- yt-dlp streams raw WebM/Opus bytes to stdout with ``-o -``.
- An async generator feeds those bytes directly into an httpx streaming POST.
- Deepgram's pre-recorded endpoint natively accepts ``audio/webm``.
"""

import asyncio
import os
from collections.abc import AsyncGenerator

import httpx

DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"
CHUNK_SIZE = 65_536  # 64 KiB


async def _yt_dlp_audio_stream(
    video_url: str,
) -> AsyncGenerator[bytes, None]:
    """Yield raw audio bytes piped from yt-dlp stdout.

    ``-f bestaudio`` selects the highest-quality audio-only stream (typically
    WebM/Opus for YouTube).  ``-o -`` writes to stdout instead of a file.
    """
    process = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "-f", "bestaudio",
        "-o", "-",
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        video_url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )

    assert process.stdout is not None  # guaranteed by PIPE

    try:
        while True:
            chunk = await process.stdout.read(CHUNK_SIZE)
            if not chunk:
                break
            yield chunk
    finally:
        # Ensure the subprocess is always reaped even on generator close.
        try:
            process.stdout.feed_eof()
        except Exception:
            pass
        await process.wait()


async def transcribe_audio(video_url: str) -> str:
    """Stream audio from *video_url* to Deepgram and return the transcript text.

    Uses Deepgram's ``nova-2`` model with smart formatting and punctuation.
    The HTTP connection timeout is generous (5 min) because a long video may
    take time to pipe through yt-dlp before the response arrives.
    """
    api_key = os.environ["DEEPGRAM_API_KEY"]
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "audio/webm",
    }
    params = {
        "model": "nova-2",
        "smart_format": "true",
        "punctuate": "true",
        "language": "en",
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
        response = await client.post(
            DEEPGRAM_URL,
            params=params,
            headers=headers,
            content=_yt_dlp_audio_stream(video_url),
        )
        response.raise_for_status()

    data = response.json()
    try:
        transcript: str = (
            data["results"]["channels"][0]["alternatives"][0]["transcript"]
        )
    except (KeyError, IndexError) as exc:
        raise RuntimeError(
            f"Unexpected Deepgram response shape: {data}"
        ) from exc

    return transcript
