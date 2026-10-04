"""Mermaid diagram rendering via Kroki.io.

Design constraint (see EXECUTION PLAN):
- Use HTTP POST with the raw Mermaid string as the body.
- Never use GET + base64/zlib — long diagrams exceed URL length limits.
"""

import httpx

KROKI_URL = "https://kroki.io/mermaid/png"
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


async def render_diagram(mermaid_code: str) -> bytes:
    """POST *mermaid_code* to Kroki and return the PNG bytes.

    Kroki accepts plain text bodies for the ``/mermaid/png`` endpoint.
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(
            KROKI_URL,
            content=mermaid_code.encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
        response.raise_for_status()
        return response.content
