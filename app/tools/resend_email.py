"""Email delivery via Resend API with a Jinja2 HTML template.

The module is named ``resend_email`` (not ``resend``) to avoid shadowing
the ``resend`` third-party package imported below.
"""

import asyncio
import base64
import os
from pathlib import Path

import resend
from jinja2 import Environment, FileSystemLoader, select_autoescape

_FROM_EMAIL = os.environ.get("FROM_EMAIL", "digest@yourdomain.com")

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _diagram_data_uri(diagram_bytes: bytes) -> str:
    b64 = base64.b64encode(diagram_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _render_html(
    *,
    tldr: str,
    deep_dive: str,
    video_url: str,
    video_title: str | None,
    diagram_bytes: bytes | None,
) -> str:
    template = _jinja_env.get_template("email.html")
    return template.render(
        tldr=tldr,
        deep_dive=deep_dive,
        video_url=video_url,
        video_title=video_title,
        diagram_data_uri=_diagram_data_uri(diagram_bytes) if diagram_bytes else None,
    )


async def send_digest_email(
    *,
    to: str,
    video_url: str,
    video_title: str | None,
    tldr: str,
    deep_dive: str,
    diagram_bytes: bytes | None = None,
) -> str:
    """Render and send the digest email, returning the Resend email ID."""
    subject = (
        f"Deep-Dive: {video_title}" if video_title else "Your YouTube Deep-Dive Summary"
    )
    html = _render_html(
        tldr=tldr,
        deep_dive=deep_dive,
        video_url=video_url,
        video_title=video_title,
        diagram_bytes=diagram_bytes,
    )

    resend.api_key = os.environ["RESEND_API_KEY"]

    params: resend.Emails.SendParams = {
        "from": _FROM_EMAIL,
        "to": [to],
        "subject": subject,
        "html": html,
    }

    # resend.Emails.send is synchronous — run in a thread to avoid blocking
    # the event loop.
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, lambda: resend.Emails.send(params))
    return result["id"]
