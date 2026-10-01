"""Listing sources.

Each source is one small function with the signature::

    fetch_<name>(client: PoliteClient, cfg: dict) -> list[Listing]

``cfg`` is that source's block from config.yaml. Sources only *fetch and
normalise*; filtering happens later in filters.py. To add a source, write a
function and register it in ``SOURCES``.

Sources that were tested and rejected (and why) are listed in the README.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import date, datetime
from typing import Callable

import feedparser
from bs4 import BeautifulSoup

from models import Listing
from polite import PoliteClient

log = logging.getLogger(__name__)

SNIPPET_CHARS = 260


# -- helpers ------------------------------------------------------------------

def html_to_text(raw_html: str) -> str:
    """Strip tags and collapse whitespace."""
    soup = BeautifulSoup(raw_html or "", "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()


def make_snippet(text: str, limit: int = SNIPPET_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


# -- source: Localist university calendars ------------------------------------

_LOCALIST_DATE = re.compile(r"^([A-Z][a-z]{2} \d{1,2}, \d{4}):\s*")


def fetch_localist_calendars(client: PoliteClient, cfg: dict) -> list[Listing]:
    """Audition/casting events from Localist-powered university calendars.

    Localist exposes search results as RSS at ``/search/events.xml?search=...``.
    Titles look like ``"Oct 29, 2026: Event name"``, so the event date is
    parsed from the prefix.
    """
    listings: list[Listing] = []
    for calendar in cfg.get("calendars", []):
        for term in cfg.get("search_terms", ["audition"]):
            try:
                resp = client.get(
                    calendar["base_url"].rstrip("/") + "/search/events.xml",
                    params={"search": term},
                )
            except Exception as exc:  # one bad calendar/term must not stop the rest
                log.warning("%s (%r): %s", calendar["name"], term, exc)
                continue
            feed = feedparser.parse(resp.content)
            for entry in feed.entries:
                title = html.unescape(entry.get("title", "")).strip()
                event_date = ""
                match = _LOCALIST_DATE.match(title)
                if match:
                    event_date = datetime.strptime(match.group(1), "%b %d, %Y").date().isoformat()
                    title = title[match.end():]
                text = html_to_text(entry.get("summary", ""))
                # Drop the "View on site | email" footer Localist appends.
                text = text.split("View on site")[0].strip()
                listings.append(Listing(
                    title=title,
                    source=calendar["name"],
                    url=entry.get("link", ""),
                    date=event_date,
                    text=f"{title}. {text}",
                    snippet=make_snippet(text),
                    is_local=True,
                ))
    return listings


# -- source: Alliance Theatre (Atlanta) ---------------------------------------

ALLIANCE_API = "https://www.alliancetheatre.org/wp-json/tribe/events/v1/events"


def fetch_alliance_theatre(client: PoliteClient, cfg: dict) -> list[Listing]:
    """Upcoming audition events from the Alliance Theatre's public events API."""
    listings: list[Listing] = []
    for term in cfg.get("search_terms", ["audition"]):
        resp = client.get(ALLIANCE_API, params={
            "search": term,
            "per_page": 25,
            "start_date": date.today().isoformat(),
        })
        for event in resp.json().get("events", []):
            title = html.unescape(re.sub(r"<[^>]+>", "", event.get("title", ""))).strip()
            text = html_to_text(event.get("description", ""))
            listings.append(Listing(
                title=title,
                source="Alliance Theatre",
                url=event.get("url", ""),
                date=(event.get("start_date") or "")[:10],
                text=f"{title}. {text}",
                snippet=make_snippet(text),
                is_local=True,
            ))
    return listings


# -- source: AuditionsFree (WordPress JSON API) ---------------------------------

AUDITIONSFREE_API = "https://www.auditionsfree.com/wp-json/wp/v2/posts"


def fetch_auditionsfree(client: PoliteClient, cfg: dict) -> list[Listing]:
    """Recent Atlanta casting posts (film, TV, extras, reality) from AuditionsFree.

    AuditionsFree is a free listing blog that links out to the original casting
    notices. Its WordPress site exposes a public JSON API, which is cleaner and
    kinder to the server than parsing HTML pages. ``tag_id`` 78 is the site's
    "Atlanta" tag.
    """
    resp = client.get(AUDITIONSFREE_API, params={
        "tags": cfg.get("tag_id", 78),
        "per_page": cfg.get("max_posts", 30),
        "_fields": "link,title,date,excerpt,content",
    })
    listings: list[Listing] = []
    for post in resp.json():
        title = html_to_text(post["title"]["rendered"])
        text = html_to_text(post["content"]["rendered"])
        listings.append(Listing(
            title=title,
            source="AuditionsFree (Atlanta)",
            url=post["link"],
            date=post["date"][:10],
            text=f"{title}. {text}",
            snippet=make_snippet(html_to_text(post["excerpt"]["rendered"]).replace("Read More »", "").strip()),
            is_local=True,
        ))
    return listings


# -- registry and runner --------------------------------------------------------

SOURCES: dict[str, Callable[[PoliteClient, dict], list[Listing]]] = {
    "auditionsfree": fetch_auditionsfree,
    "localist_calendars": fetch_localist_calendars,
    "alliance_theatre": fetch_alliance_theatre,
}


def run_sources(client: PoliteClient, sources_cfg: dict) -> tuple[list[Listing], dict[str, str]]:
    """Run every enabled source. A failing source is logged and skipped.

    Returns ``(listings, status)`` where status maps source id to a short
    human-readable result such as ``"12 listings"`` or ``"FAILED: ..."``.
    """
    listings: list[Listing] = []
    status: dict[str, str] = {}
    for name, fetch in SOURCES.items():
        cfg = sources_cfg.get(name, {})
        if not cfg.get("enabled", True):
            status[name] = "disabled"
            continue
        try:
            found = fetch(client, cfg)
        except Exception as exc:
            log.error("Source %s failed: %s", name, exc)
            status[name] = f"FAILED: {exc}"
            continue
        log.info("Source %s returned %d listings", name, len(found))
        status[name] = f"{len(found)} listings"
        listings.extend(found)
    return listings, status
