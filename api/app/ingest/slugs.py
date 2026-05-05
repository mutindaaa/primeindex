import re
import unicodedata
from collections.abc import Iterable

_INWORD_STRIP = re.compile(r"['’]")  # apostrophes (ASCII + curly) stripped, not hyphenated
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_TRIM_HYPHENS = re.compile(r"^-+|-+$")


def slugify(name: str) -> str:
    """Lowercase, ASCII-only, hyphenated, punctuation stripped. No city suffix.

    Examples:
        "Bavette's Bar & Boeuf" -> "bavettes-bar-boeuf"
        "RPM Steak"             -> "rpm-steak"
    """
    if not name:
        raise ValueError("slugify: name must be non-empty")
    # Strip apostrophes first so "Bavette's" -> "bavettes", not "bavette-s".
    no_apostrophes = _INWORD_STRIP.sub("", name)
    normalized = unicodedata.normalize("NFKD", no_apostrophes)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower()
    hyphenated = _NON_ALNUM.sub("-", lowered)
    trimmed = _TRIM_HYPHENS.sub("", hyphenated)
    if not trimmed:
        raise ValueError(f"slugify: name {name!r} reduced to empty slug")
    return trimmed


def unique_slug(base: str, existing: Iterable[str], max_attempts: int = 100) -> str:
    """Return base if unused, else base-2, base-3, ... up to max_attempts."""
    existing_set = set(existing)
    if base not in existing_set:
        return base
    for n in range(2, max_attempts + 1):
        candidate = f"{base}-{n}"
        if candidate not in existing_set:
            return candidate
    raise RuntimeError(f"unique_slug: could not resolve collision for {base!r} after {max_attempts} attempts")
