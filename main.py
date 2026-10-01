"""Casting digest: fetch -> filter -> dedupe -> write digest.html / digest.csv.

Usage:
    python main.py              # normal daily run
    python main.py --dry-run    # don't record listings as seen
    python main.py --email      # also email the digest (see emailer.py / README)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import yaml

from emailer import send_digest
from filters import EXCLUDE, classify
from polite import PoliteClient
from report import write_csv, write_html
from sources import run_sources

log = logging.getLogger("casting_digest")

SEEN_RETENTION_DAYS = 120  # forget old URLs so seen.json doesn't grow forever
_TRACKING_PARAMS = ("utm_", "fbclid", "gclid")


def normalize_url(url: str) -> str:
    """Drop fragments and tracking parameters so the same page dedupes reliably."""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.startswith(_TRACKING_PARAMS)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def load_seen(path: Path) -> dict[str, str]:
    """Return {url: first_seen_iso_date}. A missing or corrupt file means 'nothing seen'."""
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("urls", {})
    except (FileNotFoundError, ValueError):
        return {}


def save_seen(path: Path, seen: dict[str, str]) -> None:
    cutoff = (date.today() - timedelta(days=SEEN_RETENTION_DAYS)).isoformat()
    kept = {url: day for url, day in seen.items() if day >= cutoff}
    path.write_text(json.dumps({"urls": kept}, indent=2, sort_keys=True), encoding="utf-8")


def setup_logging(log_path: Path) -> None:
    """Console shows INFO; the log file also records every exclusion (DEBUG)."""
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logfile = logging.FileHandler(log_path, encoding="utf-8")
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[console, logfile],
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--config", default="config.yaml", type=Path)
    parser.add_argument("--out-dir", default=".", type=Path, help="where digest/seen/log files go")
    parser.add_argument("--dry-run", action="store_true", help="write the digest but don't update seen.json")
    parser.add_argument("--email", action="store_true", help="also email the digest (needs GMAIL_* env vars)")
    args = parser.parse_args()

    setup_logging(args.out_dir / "casting_digest.log")
    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))

    client = PoliteClient(
        user_agent=cfg["user_agent"],
        delay=cfg.get("request_delay_seconds", 3),
        timeout=cfg.get("request_timeout_seconds", 20),
    )

    # 1. Sources
    raw, source_status = run_sources(client, cfg.get("sources", {}))

    # 2. Dedupe (against earlier runs and within this run)
    seen_path = args.out_dir / "seen.json"
    seen = load_seen(seen_path)
    oldest = (date.today() - timedelta(days=cfg.get("max_age_days", 45))).isoformat()
    new, this_run = [], set()
    for item in raw:
        item.url = normalize_url(item.url)
        if not item.url or item.url in seen or item.url in this_run:
            continue
        if item.date and item.date < oldest:  # stale; ISO dates compare as strings
            continue
        this_run.add(item.url)
        new.append(item)

    # 3. Filter
    kept = [item for item in new if classify(item, cfg) != EXCLUDE]

    # 4. Digest
    write_html(args.out_dir / "digest.html", kept, source_status)
    write_csv(args.out_dir / "digest.csv", kept)

    # 5. Optional email. If it fails we keep the listings "unseen" so tomorrow's run retries them.
    exit_code = 0
    if args.email and kept:
        try:
            send_digest(kept)
            log.info("Emailed digest")
        except Exception as exc:
            log.error("Email failed: %s", exc)
            return 1
    elif args.email:
        log.info("No new listings; not sending an email")

    # Every new URL counts as seen, including excluded ones, so they aren't re-judged tomorrow.
    if not args.dry_run:
        today = date.today().isoformat()
        seen.update({url: today for url in this_run})
        save_seen(seen_path, seen)

    flagged = sum(1 for i in kept if i.status == "flag")
    log.info("Fetched %d, new %d, kept %d (%d flagged). Wrote digest.html and digest.csv",
             len(raw), len(new), len(kept), flagged)
    failed = [name for name, s in source_status.items() if s.startswith("FAILED")]
    if failed:
        log.warning("Sources that failed this run: %s", ", ".join(failed))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
