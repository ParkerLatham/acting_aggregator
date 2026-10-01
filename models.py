"""Shared data structures."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Listing:
    """One casting/audition listing, normalised across all sources."""

    title: str
    source: str                 # human-readable source name, used for grouping
    url: str                    # canonical link; also the dedupe key
    date: str = ""              # ISO date (event date or posted date), if known
    text: str = ""              # full plain-text description, used for matching
    snippet: str = ""           # short preview shown in the digest
    is_local: bool = False      # True if the source is already Atlanta-specific

    # Filled in by filters.py
    pay: str | None = None      # e.g. "$150/day"; None means "pay not listed"
    age: str | None = None      # e.g. "Ages 18-25"
    age_match: bool = False
    status: str = "keep"        # "keep" or "flag" (excluded listings never reach the digest)
    reasons: list[str] = field(default_factory=list)  # why it was flagged
