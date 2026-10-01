"""Keyword filtering and light field extraction.

``classify`` decides whether a listing is kept, flagged for a closer look, or
excluded, using only the keyword lists in config.yaml. It also extracts pay and
age text so the digest can show them.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache

from models import Listing

log = logging.getLogger(__name__)

EXCLUDE = "exclude"

# A dollar amount only counts as "pay" if a pay-ish word is nearby; otherwise
# "$10 tickets" or "$25 parking" would be misread as compensation.
_MONEY = re.compile(r"\$\s?\d[\d,]*(?:\.\d{2})?(?:\s?(?:/|per)\s?(?:hr|hour|day|session|show))?", re.I)
_PAY_CONTEXT = re.compile(r"\b(pay|paid|rate|compensation|stipend|honorarium|per day|per hour|/hr|/day|wage)\b", re.I)
_AGE_RANGE = re.compile(r"\b(?:ages?\s*)?(\d{2})\s*(?:-|–|—|to)\s*(\d{2})\b", re.I)
_AGE_PLUS = re.compile(r"\b(\d{2})\s*\+")


@lru_cache(maxsize=None)
def _term_regex(term: str) -> re.Pattern:
    """Whole-word, case-insensitive pattern for a config term."""
    return re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.I)


def find_terms(text: str, terms: list[str]) -> list[str]:
    """Return the config terms that appear in ``text``."""
    return [t for t in terms if _term_regex(t).search(text)]


def extract_pay(text: str) -> str | None:
    """Best-effort pay description, or None if the listing doesn't say."""
    for match in _MONEY.finditer(text):
        window = text[max(0, match.start() - 40): match.end() + 40]
        if _PAY_CONTEXT.search(window):
            return match.group(0).strip()
    if re.search(r"\b(?<!un)paid\b", text, re.I):
        return "Paid (amount not listed)"
    if re.search(r"\bstipend\b", text, re.I):
        return "Stipend"
    return None


def extract_age(text: str) -> str | None:
    match = _AGE_RANGE.search(text)
    if match and 5 <= int(match.group(1)) < int(match.group(2)) <= 99:
        return f"Ages {match.group(1)}–{match.group(2)}"
    match = _AGE_PLUS.search(text)
    if match and 10 <= int(match.group(1)) <= 40:
        return f"Ages {match.group(1)}+"
    return None


def classify(listing: Listing, cfg: dict) -> str:
    """Fill in derived fields on ``listing`` and return its status.

    Returns ``"keep"``, ``"flag"`` or ``"exclude"``. The reason for an exclusion
    is logged so nothing disappears silently.
    """
    text = f"{listing.title}. {listing.text}"
    include = cfg.get("include", {})

    listing.pay = extract_pay(text)
    listing.age = extract_age(text)
    listing.age_match = bool(find_terms(text, include.get("age_terms", [])))

    if not find_terms(text, include.get("role_terms", [])):
        return _exclude(listing, "no acting/casting term")
    noise = find_terms(text, include.get("noise_terms", []))
    if noise:
        return _exclude(listing, f"not an acting role: {', '.join(noise)}")
    if not listing.is_local and not find_terms(text, include.get("location_terms", [])):
        return _exclude(listing, "no Atlanta/Georgia location term")

    red = find_terms(text, cfg.get("red_flags", []))
    if red:
        return _exclude(listing, f"red flag: {', '.join(red)}")

    flags = find_terms(text, cfg.get("flag_terms", []))
    if flags:
        listing.reasons = [f"mentions “{t}”" for t in flags]
        listing.status = "flag"
        return "flag"

    listing.status = "keep"
    return "keep"


def _exclude(listing: Listing, reason: str) -> str:
    log.debug("Excluded %r (%s): %s", listing.title, reason, listing.url)
    return EXCLUDE
