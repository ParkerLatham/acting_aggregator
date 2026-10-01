"""A small, polite HTTP client.

Every request made by this project goes through :class:`PoliteClient`, which

* sends a clear, honest User-Agent,
* checks the site's robots.txt before fetching (and refuses if disallowed),
* waits a minimum delay between requests to the same host (or the site's
  declared Crawl-delay, if longer), and
* backs off once if the server answers 429 Too Many Requests.

robots.txt is parsed with Protego rather than the standard library's
``urllib.robotparser``: Protego understands wildcards and "longest match wins"
precedence, which sites like calendar.gsu.edu rely on (``Disallow: /search``
followed by ``Allow: /search/events.xml``).
"""

from __future__ import annotations

import logging
import time
from urllib.parse import urlsplit

import requests
from protego import Protego

log = logging.getLogger(__name__)

_ALLOW_ALL = ""
_DISALLOW_ALL = "User-agent: *\nDisallow: /"


class RobotsDisallowed(Exception):
    """Raised when robots.txt does not permit fetching a URL."""


class PoliteClient:
    def __init__(self, user_agent: str, delay: float = 3.0, timeout: float = 20.0):
        self.user_agent = user_agent
        # robots.txt matches on the product token, e.g. "CastingDigestBot".
        self._robots_token = user_agent.split("/")[0].split()[0]
        self.delay = delay
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._robots: dict[str, Protego] = {}
        self._last_request: dict[str, float] = {}

    # -- robots.txt -----------------------------------------------------------

    def _robots_for(self, origin: str) -> Protego:
        """Fetch and cache robots.txt for an origin like 'https://example.com'."""
        if origin in self._robots:
            return self._robots[origin]

        try:
            resp = self._send(origin + "/robots.txt", origin)
            if resp.status_code == 200:
                body = resp.text
            elif resp.status_code in (401, 403):
                log.warning("robots.txt at %s is forbidden; treating site as off limits", origin)
                body = _DISALLOW_ALL
            elif 400 <= resp.status_code < 500:
                body = _ALLOW_ALL  # no robots.txt means no restrictions
            else:
                body = _DISALLOW_ALL  # server trouble: stay on the safe side
        except requests.RequestException as exc:
            log.warning("Could not read robots.txt at %s (%s); skipping site", origin, exc)
            body = _DISALLOW_ALL

        self._robots[origin] = Protego.parse(body)
        return self._robots[origin]

    # -- fetching -------------------------------------------------------------

    def get(self, url: str, params: dict | None = None) -> requests.Response:
        """GET a URL politely. Raises RobotsDisallowed or requests exceptions."""
        prepared = requests.Request("GET", url, params=params).prepare().url
        parts = urlsplit(prepared)
        origin = f"{parts.scheme}://{parts.netloc}"

        robots = self._robots_for(origin)
        if not robots.can_fetch(prepared, self._robots_token):
            raise RobotsDisallowed(f"robots.txt disallows {prepared}")

        resp = self._send(prepared, origin, robots)
        if resp.status_code == 429:
            wait = min(_retry_after(resp), 30)
            log.info("429 from %s; waiting %.0fs and retrying once", origin, wait)
            time.sleep(wait)
            resp = self._send(prepared, origin, robots)
        resp.raise_for_status()
        return resp

    def _send(self, url: str, origin: str, robots: Protego | None = None) -> requests.Response:
        crawl_delay = robots.crawl_delay(self._robots_token) if robots else None
        wait = max(self.delay, crawl_delay or 0)
        elapsed = time.monotonic() - self._last_request.get(origin, float("-inf"))
        if elapsed < wait:
            time.sleep(wait - elapsed)
        try:
            return self.session.get(url, timeout=self.timeout)
        finally:
            self._last_request[origin] = time.monotonic()


def _retry_after(resp: requests.Response) -> float:
    try:
        return float(resp.headers.get("Retry-After", ""))
    except ValueError:
        return 10.0
