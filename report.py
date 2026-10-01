"""Write the digest as a mobile-friendly HTML page and a CSV."""

from __future__ import annotations

import csv
from datetime import date
from html import escape
from itertools import groupby
from pathlib import Path

from models import Listing

_CSS = """
:root{--bg:#faf8f5;--card:#fff;--ink:#222;--muted:#666;--line:#e6e1da;--accent:#8a3b5c;--warn:#b26a00}
@media(prefers-color-scheme:dark){:root{--bg:#161416;--card:#201d20;--ink:#eee;--muted:#a9a3a9;--line:#332f33;--accent:#e08bb0;--warn:#e8a94a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:720px;margin:0 auto;padding:16px}
h1{font-size:1.5rem;margin:.2em 0}h2{font-size:1.1rem;margin:1.8em 0 .6em;color:var(--accent)}
.sub{color:var(--muted);font-size:.9rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:10px 0}
.card h3{font-size:1rem;margin:0 0 4px}.card a{color:var(--accent);text-decoration:none}
.meta{display:flex;flex-wrap:wrap;gap:6px;font-size:.8rem;color:var(--muted);margin-bottom:6px}
.badge{border:1px solid var(--line);border-radius:999px;padding:1px 8px}
.badge.nopay{color:var(--warn);border-color:var(--warn)}.badge.good{color:var(--accent);border-color:var(--accent)}
.snip{margin:0;font-size:.92rem}.why{margin:6px 0 0;font-size:.85rem;color:var(--warn)}
.flagged{border-left:4px solid var(--warn)}
.status{font-size:.8rem;color:var(--muted)}
"""


def _card(item: Listing, flagged: bool = False) -> str:
    badges = []
    if item.date:
        badges.append(f'<span class="badge">{escape(item.date)}</span>')
    if item.pay:
        badges.append(f'<span class="badge">{escape(item.pay)}</span>')
    else:
        badges.append('<span class="badge nopay">pay not listed</span>')
    if item.age:
        badges.append(f'<span class="badge">{escape(item.age)}</span>')
    if item.age_match:
        badges.append('<span class="badge good">age match</span>')
    why = ""
    if flagged and item.reasons:
        why = f'<p class="why">Check carefully: {escape("; ".join(item.reasons))}</p>'
    return (
        f'<div class="card{" flagged" if flagged else ""}">'
        f'<h3><a href="{escape(item.url, quote=True)}">{escape(item.title)}</a></h3>'
        f'<div class="meta">{"".join(badges)}</div>'
        f'<p class="snip">{escape(item.snippet)}</p>{why}</div>'
    )


def write_html(path: Path, listings: list[Listing], source_status: dict[str, str]) -> None:
    keep = sorted((i for i in listings if i.status == "keep"), key=lambda i: i.source)
    flagged = [i for i in listings if i.status == "flag"]

    parts = [
        f"<h1>Casting digest · {date.today():%b %d, %Y}</h1>",
        f'<p class="sub">{len(keep)} new listings, {len(flagged)} flagged. '
        "Free public sources only. Always verify a listing before replying.</p>",
    ]
    if not listings:
        parts.append("<p>No new listings since the last run.</p>")
    for source, group in groupby(keep, key=lambda i: i.source):
        parts.append(f"<h2>{escape(source)}</h2>")
        parts.extend(_card(i) for i in group)
    if flagged:
        parts.append("<h2>Flagged / check carefully</h2>")
        parts.extend(_card(i, flagged=True) for i in flagged)
    parts.append(
        '<p class="status">Source status: '
        + escape("; ".join(f"{k}: {v}" for k, v in source_status.items()))
        + "</p>"
    )

    path.write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>Casting digest</title><style>{_CSS}</style></head>"
        f"<body><main>{''.join(parts)}</main></body></html>",
        encoding="utf-8",
    )


def write_csv(path: Path, listings: list[Listing]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as fh:  # BOM so Excel reads UTF-8
        writer = csv.writer(fh)
        writer.writerow(["status", "source", "title", "date", "pay", "age", "snippet", "url", "flag_reasons"])
        for i in sorted(listings, key=lambda i: (i.status == "flag", i.source)):
            writer.writerow([
                i.status, i.source, i.title, i.date, i.pay or "pay not listed",
                i.age or "", i.snippet, i.url, "; ".join(i.reasons),
            ])
