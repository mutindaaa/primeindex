"""Thin Anthropic SDK wrapper for sentence-level review classification.

System prompt is verbatim from spec §6. Strategy:
  - First call uses the model's default temperature.
  - On JSON parse / schema failure, retry once at temperature=0 (per spec §6).
  - Raises ClassifierError if both attempts fail; the caller decides whether
    to log-and-continue or abort.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic

from app.config import settings
from app.logging_setup import get_logger

log = get_logger(__name__)

SYSTEM_PROMPT = """You are a review analyst. You will receive a single restaurant review. Break it into sentences. For each sentence, return:
- "text": the sentence verbatim
- "pillar": exactly one of "quality", "service", "ambiance", or "other"
- "sentiment": a float from -1.0 (very negative) to 1.0 (very positive); 0.0 means neutral or factual

Pillar definitions:
- "quality" = the food itself, including taste, preparation, portions, ingredients, and whether the price is justified by the food
- "service" = waitstaff, hosts, sommelier, kitchen pacing, attentiveness, knowledge, friendliness
- "ambiance" = decor, noise level, lighting, cleanliness (including bathrooms), crowd, vibe
- "other" = anything that doesn't fit the three above (parking, location, reservations, etc.)

Return ONLY a JSON object of the form: {"sentences": [{"text": "...", "pillar": "...", "sentiment": 0.0}, ...]}
No prose, no markdown fencing."""

VALID_PILLARS = {"quality", "service", "ambiance", "other"}
MAX_TOKENS = 2000

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


@dataclass
class SentenceClass:
    text: str
    pillar: str
    sentiment: float


class ClassifierError(RuntimeError):
    pass


def _client() -> Anthropic:
    if not settings.anthropic_api_key:
        raise ClassifierError("ANTHROPIC_API_KEY is not set in environment")
    return Anthropic(api_key=settings.anthropic_api_key)


def _strip_fences(text: str) -> str:
    """Defensive: spec says 'no markdown fencing' but real LLMs sometimes ignore that."""
    return _FENCE_RE.sub("", text).strip()


def _validate_sentence(item: Any) -> SentenceClass:
    if not isinstance(item, dict):
        raise ValueError(f"sentence is not a dict: {item!r}")
    text = item.get("text")
    pillar = item.get("pillar")
    sentiment = item.get("sentiment")
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"sentence missing/empty 'text': {item!r}")
    if pillar not in VALID_PILLARS:
        raise ValueError(f"sentence has invalid pillar={pillar!r}: {item!r}")
    if not isinstance(sentiment, (int, float)):
        raise ValueError(f"sentence sentiment is not a number: {item!r}")
    s = float(sentiment)
    if s < -1.0 or s > 1.0:
        # Soft-clamp slight overshoots; reject wild values.
        if -1.5 <= s <= 1.5:
            s = max(-1.0, min(1.0, s))
        else:
            raise ValueError(f"sentence sentiment out of range: {s}")
    return SentenceClass(text=text.strip(), pillar=pillar, sentiment=s)


def _parse_response(raw: str) -> list[SentenceClass]:
    cleaned = _strip_fences(raw)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ClassifierError(f"response is not valid JSON: {e}; raw[:200]={raw[:200]!r}") from e
    sentences = payload.get("sentences") if isinstance(payload, dict) else None
    if not isinstance(sentences, list):
        raise ClassifierError(f"response missing 'sentences' list: {cleaned[:200]!r}")
    out: list[SentenceClass] = []
    for i, item in enumerate(sentences):
        try:
            out.append(_validate_sentence(item))
        except ValueError as e:
            raise ClassifierError(f"sentence #{i} invalid: {e}") from e
    return out


def _call_claude(client: Anthropic, body: str, *, temperature: float | None) -> str:
    kwargs: dict = {
        "model": settings.anthropic_model,
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": body}],
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    response = client.messages.create(**kwargs)
    if not response.content:
        raise ClassifierError("Claude returned empty content list")
    block = response.content[0]
    text = getattr(block, "text", None)
    if not text:
        raise ClassifierError(f"Claude returned non-text block: {block!r}")
    return text


def classify_review(body: str, client: Anthropic | None = None) -> list[SentenceClass]:
    """Send a single review body to Claude. Retries once at temp=0 on parse failure."""
    if not body or not body.strip():
        return []

    c = client or _client()

    try:
        raw = _call_claude(c, body, temperature=None)
        return _parse_response(raw)
    except ClassifierError as first_err:
        log.warning("classifier first attempt failed (%s); retrying at temperature=0", first_err)
        raw = _call_claude(c, body, temperature=0.0)
        return _parse_response(raw)
