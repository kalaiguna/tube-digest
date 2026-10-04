import re
from pydantic import BaseModel, field_validator


class SynthesisResult(BaseModel):
    """Structured output produced by the synthesis agent.

    The `visual_map` validator is critical: Gemini frequently wraps Mermaid
    output in a markdown code fence (```mermaid ... ```) even when instructed
    not to.  The validator strips that wrapper so Kroki receives clean code.
    """

    tldr: str
    """One-paragraph executive summary of the video."""

    deep_dive: str
    """Multi-paragraph detailed analysis with key points, quotes, and takeaways."""

    visual_map: str
    """Raw Mermaid graph/flowchart code — no code fence, no leading whitespace."""

    @field_validator("visual_map", mode="before")
    @classmethod
    def strip_mermaid_code_fence(cls, v: object) -> str:
        if not isinstance(v, str):
            return v  # type: ignore[return-value]

        stripped = v.strip()

        # Match an optional ```mermaid or plain ``` fence at both ends.
        match = re.match(
            r"^```(?:mermaid)?\s*\n?([\s\S]*?)\n?```\s*$",
            stripped,
            re.DOTALL,
        )
        if match:
            return match.group(1).strip()

        return stripped
