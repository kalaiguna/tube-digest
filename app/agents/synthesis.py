"""Synthesis agent: two-pass Gemini summarisation.

Pass 1 — Gemini Flash with ``response_schema``:
    Produces a structured ``_TierOneOutput`` — TL;DR, a first-draft Deep Dive
    (retained as fallback), and the Mermaid Visual Map.

Pass 2 — Gemini Pro, standard generation:
    Produces a higher-quality Deep Dive prose piece that replaces the Flash
    draft.  If the Pro call fails, the Flash Deep Dive is kept so the pipeline
    always completes.
"""

import logging
import os
import re

from google import genai
from google.genai import types
from pydantic import BaseModel, field_validator

from schemas.summary import SynthesisResult

logger = logging.getLogger(__name__)

FLASH_MODEL = os.environ.get("GEMINI_FLASH_MODEL", "gemini-2.0-flash")
PRO_MODEL = os.environ.get("GEMINI_PRO_MODEL", "gemini-2.5-pro")

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
    return _client


# ── Intermediate schema for the Flash structured pass ────────────────────────

class _TierOneOutput(BaseModel):
    """All three summary fields — Flash generates them; Pro overrides deep_dive."""

    tldr: str
    deep_dive: str
    visual_map: str

    @field_validator("visual_map", mode="before")
    @classmethod
    def strip_fence(cls, v: object) -> str:
        if not isinstance(v, str):
            return v  # type: ignore[return-value]
        stripped = v.strip()
        match = re.match(
            r"^```(?:mermaid)?\s*\n?([\s\S]*?)\n?```\s*$", stripped, re.DOTALL
        )
        return match.group(1).strip() if match else stripped


# ── Prompts ──────────────────────────────────────────────────────────────────

_FLASH_PROMPT = """\
You are a knowledge distillation engine. Given the YouTube video transcript below, \
produce a structured JSON summary with three fields.

Rules:
- tldr: 3-5 sentences for a busy professional. Lead with the core claim, \
include the key evidence, end with the single most important takeaway.
- deep_dive: 400-600 words of flowing prose — no bullet lists, no headers. \
Open with the thesis, walk through the main arguments, surface the most surprising \
or counterintuitive points, close with 2-3 actionable takeaways.
- visual_map: A Mermaid `graph TD` diagram showing the main concepts and how they \
relate. Use concise node labels (3-5 words each). Output ONLY the raw Mermaid code — \
no code fence, no markdown wrapper of any kind.

TRANSCRIPT:
{transcript}
"""

_PRO_PROMPT = """\
You are an expert analyst writing the Deep Dive section of a YouTube video digest \
email for a busy professional who couldn't watch the video but wants genuine depth.

Write 450-600 words of flowing prose. NO bullet lists. NO headers. NO markdown.

Weave these naturally into the prose:
1. Open with the core thesis in 1-2 punchy sentences.
2. Walk through the main arguments in logical order.
3. Surface the most insightful or counterintuitive points.
4. Quote the speaker directly where the transcript contains memorable lines \
   (use quotation marks).
5. Close with 2-3 concrete, actionable takeaways.

CONTEXT — TL;DR already produced:
{tldr}

FULL TRANSCRIPT:
{transcript}
"""


# ── Public interface ──────────────────────────────────────────────────────────

async def synthesize(transcript: str) -> SynthesisResult:
    """Run both model passes and return a complete ``SynthesisResult``.

    The Flash pass is authoritative for ``tldr`` and ``visual_map``.
    The Pro pass produces the final ``deep_dive``; the Flash draft is the fallback.
    """
    client = _get_client()

    # ── Pass 1: Flash structured output ──────────────────────────────────────
    logger.info("synthesis pass 1 — Flash model=%s", FLASH_MODEL)
    flash_response = await client.aio.models.generate_content(
        model=FLASH_MODEL,
        contents=_FLASH_PROMPT.format(transcript=transcript),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_TierOneOutput,
        ),
    )
    if not flash_response.text:
        raise RuntimeError(
            f"Flash model returned an empty response (finish_reason="
            f"{flash_response.candidates[0].finish_reason if flash_response.candidates else 'unknown'})"
        )
    tier_one = _TierOneOutput.model_validate_json(flash_response.text)
    logger.info("pass 1 complete tldr_chars=%d", len(tier_one.tldr))

    # ── Pass 2: Pro deep-dive (Pro fallback to Flash draft on failure) ────────
    deep_dive = tier_one.deep_dive
    try:
        logger.info("synthesis pass 2 — Pro model=%s", PRO_MODEL)
        pro_response = await client.aio.models.generate_content(
            model=PRO_MODEL,
            contents=_PRO_PROMPT.format(
                tldr=tier_one.tldr,
                transcript=transcript,
            ),
        )
        deep_dive = pro_response.text.strip()
        logger.info("pass 2 complete deep_dive_chars=%d", len(deep_dive))
    except Exception as exc:
        logger.warning(
            "Pro deep-dive call failed (%s) — retaining Flash draft as fallback", exc
        )

    # SynthesisResult.visual_map validator runs here, stripping any residual fences.
    return SynthesisResult(
        tldr=tier_one.tldr,
        deep_dive=deep_dive,
        visual_map=tier_one.visual_map,
    )
