"""Optional: email the digest through Gmail.

Nothing secret lives in this repo. Credentials are read from environment
variables, which GitHub Actions fills in from encrypted "Secrets":

    GMAIL_ADDRESS        the Gmail account that sends the email
    GMAIL_APP_PASSWORD   a 16-character Google *app password* (not your real password)
    DIGEST_RECIPIENTS    one or more addresses, comma-separated

Only used when you run ``python main.py --email``.
"""

from __future__ import annotations

import os
import smtplib
from datetime import date
from email.message import EmailMessage
from html import escape

from models import Listing


class EmailConfigError(Exception):
    """A required environment variable is missing."""


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EmailConfigError(f"Environment variable {name} is not set")
    return value


def _line(item: Listing) -> str:
    bits = [item.date, item.pay or "pay not listed", item.age or ""]
    return " | ".join(b for b in bits if b)


def build_message(listings: list[Listing], sender: str, recipients: list[str]) -> EmailMessage:
    """Build a plain-text + inline-styled HTML email (Gmail ignores most <style> rules)."""
    keep = [i for i in listings if i.status == "keep"]
    flagged = [i for i in listings if i.status == "flag"]

    text = [f"Casting digest, {date.today():%b %d, %Y}", ""]
    html = [
        '<div style="font-family:system-ui,Arial,sans-serif;max-width:640px;margin:auto;color:#222">',
        f'<h2 style="margin-bottom:4px">Casting digest · {date.today():%b %d, %Y}</h2>',
        '<p style="color:#666;margin-top:0">Verify every listing before replying. '
        "Never pay to audition.</p>",
    ]

    def add_section(title: str, items: list[Listing], note: bool = False) -> None:
        if not items:
            return
        text.extend([title.upper(), ""])
        html.append(f'<h3 style="color:#8a3b5c;border-bottom:1px solid #eee">{escape(title)}</h3>')
        for i in items:
            text.extend([i.title, f"  {i.source} | {_line(i)}", f"  {i.url}"])
            if note and i.reasons:
                text.append(f"  Check: {'; '.join(i.reasons)}")
            text.append("")
            why = (f'<div style="color:#b26a00;font-size:13px">Check: {escape("; ".join(i.reasons))}</div>'
                   if note and i.reasons else "")
            html.append(
                '<div style="margin:12px 0">'
                f'<a href="{escape(i.url, quote=True)}" style="font-weight:600;color:#8a3b5c">{escape(i.title)}</a>'
                f'<div style="color:#666;font-size:13px">{escape(i.source)} · {escape(_line(i))}</div>'
                f'<div style="font-size:14px">{escape(i.snippet)}</div>{why}</div>'
            )

    add_section("New listings", keep)
    add_section("Flagged / check carefully", flagged, note=True)
    html.append("</div>")

    msg = EmailMessage()
    msg["Subject"] = f"Casting digest: {len(keep)} new, {len(flagged)} flagged ({date.today():%b %d})"
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content("\n".join(text))
    msg.add_alternative("".join(html), subtype="html")
    return msg


def send_digest(listings: list[Listing]) -> None:
    """Send the digest. Raises on missing config or SMTP failure."""
    sender = _env("GMAIL_ADDRESS")
    password = _env("GMAIL_APP_PASSWORD")
    recipients = [r.strip() for r in _env("DIGEST_RECIPIENTS").split(",") if r.strip()]
    msg = build_message(listings, sender, recipients)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
        server.login(sender, password)
        server.send_message(msg)
