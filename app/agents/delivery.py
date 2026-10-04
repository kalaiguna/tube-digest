"""Delivery agent: renders the Mermaid diagram and dispatches the digest email.

Kroki failures are non-fatal — the email is sent without the diagram rather
than failing the whole pipeline.  The email template gracefully omits the
diagram section when ``diagram_bytes`` is ``None``.
"""

import logging
import os

from schemas.summary import SynthesisResult
from tools.kroki import render_diagram
from tools.resend_email import send_digest_email

logger = logging.getLogger(__name__)


async def deliver(
    result: SynthesisResult,
    *,
    video_url: str,
    video_title: str | None = None,
) -> str:
    """Render the diagram and send the digest email.

    Returns the Resend email ID on success.
    """
    diagram_bytes: bytes | None = None
    try:
        diagram_bytes = await render_diagram(result.visual_map)
        logger.info("diagram rendered bytes=%d", len(diagram_bytes))
    except Exception as exc:
        logger.warning(
            "Kroki render failed (%s) — sending email without diagram", exc
        )

    to = os.environ["TO_EMAIL"]
    email_id = await send_digest_email(
        to=to,
        video_url=video_url,
        video_title=video_title,
        tldr=result.tldr,
        deep_dive=result.deep_dive,
        diagram_bytes=diagram_bytes,
    )
    logger.info("email dispatched to=%s email_id=%s", to, email_id)
    return email_id
