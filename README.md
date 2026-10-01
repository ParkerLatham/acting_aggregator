# Casting Digest

A small Python tool that checks a few **free, public** sources for acting and audition listings in the Atlanta area, filters out junk and likely scams, remembers what it has already shown, and produces a clean daily digest (`digest.html` + `digest.csv`) or an email.

## The problem and who it's for

Paid casting platforms (Backstage, Actors Access) aren't an option for everyone, and free listings are scattered across university calendars, theatre sites, and community pages. Free listings also attract scams ("pay to audition", "registration fee"). This tool is built for an early-career actor in Atlanta who wants **one short list of new, plausible opportunities per day**, with risky ones separated out rather than hidden.

It deliberately uses only free public sources and **no logins, no scraping behind walls, no credentials in the code.**

## How it works

```
sources  ->  filter  ->  dedupe  ->  digest
```

1. **Sources** (`sources.py`): one small function per source. If one fails, it is logged and the rest still run.
2. **Filter** (`filters.py`, keywords in `config.yaml`):
   - must mention an acting term (actor, audition, casting, extras...), and for non-local sources an Atlanta/Georgia term
   - noise like recitals, career fairs, and talent shows is dropped
   - **red flags** (`pay to audition`, `registration fee`, `send money`, `upfront fee`, `pay for headshots`) are excluded, and the reason is written to `casting_digest.log`
   - **flag terms** (`unpaid`, `no pay`, `copy credit`, `venmo`, ...) keep the listing but move it to a **"Flagged / check carefully"** section
   - listings with no pay information show a **"pay not listed"** badge instead of being dropped
3. **Dedupe** (`main.py`): every URL shown is saved to `seen.json`, so each run only shows new listings.
4. **Digest** (`report.py`, `emailer.py`): a mobile-friendly `digest.html`, a `digest.csv`, and optionally an email. Listings are grouped by source, with flagged ones at the bottom.

Politeness (`polite.py`): a clear User-Agent, a delay between requests, and `robots.txt` is checked before every fetch (a disallowed URL is never requested).

## Sources: what was tested

Tested on 1 Oct 2026. Sites change, so re-check before relying on this.

| Source | Result |
|---|---|
| AuditionsFree (WordPress JSON API, "Atlanta" tag) | **Used.** Biggest source: film/TV extras and open calls, usually with pay. Open robots.txt, public API, and no terms-of-use page or automation clause found. It is a curator that links to the original notices, so always click through. |
| GSU event calendar (Localist RSS) | **Used.** robots.txt explicitly allows the RSS export. |
| Kennesaw State event calendar (Localist RSS) | **Used.** Works, but rate-limits quickly; the client backs off and retries. |
| Alliance Theatre events API | **Used.** Public API, but often returns zero audition events. |
| Craigslist Atlanta gigs RSS | Rejected: returns 403 to bots and its terms prohibit automated access. |
| Casting Call Club, AllCasting | Rejected: robots.txt is open, but their terms of service ban bots and scrapers. |
| BroadwayWorld, AtlantaFi | Not used: no terms page found for BroadwayWorld; AtlantaFi's casting list is loaded dynamically. Worth revisiting. |
| Project Casting (RSS works) | Rejected: its terms prohibit robots, spiders, and scrapers. |
| Mandy, SCAD | Rejected: 403 to bots. |
| Reddit | Rejected: 429 rate limiting without an authenticated API. |
| FOX 5 Atlanta casting posts | Rejected: connection refused for automated clients. |
| castingatl.com | Rejected: homepage is dead (404). |
| Filming in Georgia | Rejected: industry news, not casting listings. |
| UGA Campus Casting | Rejected: breakdown tables load via JavaScript (no static data); also Athens, not Atlanta. |
| Horizon Theatre auditions page | Rejected: password protected. |
| Facebook groups | Not touched: login required. |

**Honest expectation:** expect roughly 5-15 new listings a week, mostly film/TV extras and open calls from AuditionsFree, plus the occasional university or theatre audition. Free, bot-friendly sources are limited, so treat this as a supplement to browsing casting sites by hand.

## Setup (from scratch, no coding experience needed)

You need **Python 3.10 or newer**. Check by opening a terminal and typing `python --version`. If it isn't installed, get it from <https://www.python.org/downloads/> (on Windows, tick "Add python.exe to PATH").

A *terminal* is a text window where you type commands. On Windows, open **PowerShell**; on Mac, open **Terminal**. Then, from inside this project's folder:

```bash
python -m venv .venv
```

This creates a private "virtual environment" so the project's libraries don't mix with other things on your computer. Activate it:

```bash
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Mac / Linux
```

(You'll see `(.venv)` at the start of your prompt.) Then install the libraries:

```bash
pip install -r requirements.txt
```

## Run it

```bash
python main.py
```

Open `digest.html` in your browser. To preview without marking listings as "seen", use `python main.py --dry-run`.

Other files created: `digest.csv` (open in Excel/Sheets), `seen.json` (memory of past listings), `casting_digest.log` (what happened, including why things were excluded). To start fresh, delete `seen.json`.

Run the tests with `python -m unittest discover tests`.

## Customising

Everything lives in `config.yaml`: sources on/off, search terms, include terms, noise terms, red flags, and flag terms. Matching is whole-word and case-insensitive, so "actor" does not match "actors"; list both.

## Optional: fully automatic daily email (GitHub Actions + Gmail)

GitHub can run this for free on a schedule, even when your computer is off. Nothing secret is stored in the code: credentials go in GitHub **Secrets**, which are encrypted and never visible in the repo.

1. **Make a Gmail app password** (a one-purpose password so your real one is never used). Turn on 2-Step Verification for the sending Gmail account, then go to <https://myaccount.google.com/apppasswords>, create one, and copy the 16-character code. Use a throwaway or dedicated Gmail account, not your main one.
2. **Put the project on GitHub** (a new repo). `.gitignore` already keeps `seen.json`, digests, and logs out.
3. In the repo go to **Settings > Secrets and variables > Actions > New repository secret** and add three secrets:
   - `GMAIL_ADDRESS`: the sending address
   - `GMAIL_APP_PASSWORD`: the 16-character app password
   - `DIGEST_RECIPIENTS`: who receives it (comma-separated for several)
4. **Test with yourself as the only recipient first.** Go to the **Actions** tab, choose "Daily casting digest", and press **Run workflow**. Check the email, and only then switch the recipient to your friend.
5. It then runs daily at 9 AM Eastern (`.github/workflows/daily-digest.yml`).

Notes: GitHub pauses scheduled runs on repos with no activity for 60 days (re-enable in the Actions tab). It only emails when there is something new. If sending fails, listings are not marked as seen, so tomorrow's run retries them. Email is for review by a human, so keep a person in the loop before anyone applies to anything.

You can also run it by hand locally with the same three values set as environment variables and `python main.py --email`.

## Safety note for the actor

Real casting calls never ask you to pay to audition, pay for headshots, cash a check and send money back, or move to WhatsApp/Telegram. Meet in public, tell a friend where you're going, and verify the production company independently.

## Ideas for next steps

- More sources: any new Localist-based college calendar is a one-line addition in `config.yaml`; other theatres with public audition pages.
- Ask a site owner for permission, then add sources like Project Casting properly (e.g. via an official feed or partnership).
- Score listings (age, gender, paid vs. unpaid) and sort by relevance.
- Add per-source tests using saved sample feeds.
- A tiny web page of the digest published to GitHub Pages instead of email.

## Project layout

```
main.py        run order: sources -> dedupe -> filter -> digest -> (email)
sources.py     one function per source + a runner that isolates failures
filters.py     keyword matching, pay/age extraction
polite.py      User-Agent, robots.txt, delays, retry on 429
report.py      digest.html and digest.csv
emailer.py     optional Gmail sender (env vars only)
models.py      the Listing data structure
config.yaml    all keywords and source settings
tests/         unit tests
.github/workflows/daily-digest.yml   optional daily automation
```
