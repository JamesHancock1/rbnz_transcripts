"""Build data/catalogue.csv: one row per FEC (or predecessor) hearing on a
Monetary Policy Statement, with the best media URL we can find.

Sources, in priority order:
  1. config/seed_events.csv (hand-curated; always wins on conflicts)
  2. RBNZ event / speech pages mentioning the Finance and Expenditure Committee
  3. YouTube / Vimeo search via yt-dlp (Parliament's own channels)

Every auto-found candidate is flagged `verified=0` until a human checks it, since
committee sessions are often bundled with unrelated business.
"""
from __future__ import annotations

import csv
import re
import time
from dataclasses import dataclass, asdict, field

import requests
from bs4 import BeautifulSoup

from .paths import CATALOGUE, CONFIG

UA = {"User-Agent": "Mozilla/5.0 (research; rbnz-fec transcript project)"}
RBNZ = "https://www.rbnz.govt.nz"
MEDIA_HOSTS = ("vimeo.com", "youtube.com", "youtu.be", "facebook.com", "parliament.nz", "inthehouse.nz")

# Search queries run through yt-dlp. Older hearings (pre-2019 "Monetary Policy
# Statement" era, and Monetary Policy Reviews 2020-21) used the same committee.
SEARCHES = [
    "Finance and Expenditure Committee Reserve Bank Monetary Policy Statement",
    "Finance and Expenditure Committee Monetary Policy Review Reserve Bank",
    "Reserve Bank Governor select committee Monetary Policy Statement",
]

FIELDS = ["event_id", "date", "statement", "body", "source_page", "media_url",
          "title", "duration_s", "verified", "notes"]


@dataclass
class Event:
    event_id: str
    date: str = ""
    statement: str = "MPS"
    body: str = "FEC"
    source_page: str = ""
    media_url: str = ""
    title: str = ""
    duration_s: str = ""
    verified: str = "0"
    notes: str = ""
    extra: dict = field(default_factory=dict, repr=False)


def _get(url: str) -> str | None:
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        print(f"  ! {url}: {e}")
        return None


def media_links(html: str) -> list[str]:
    """Video links (anchors and iframes) on a page."""
    soup = BeautifulSoup(html, "html.parser")
    urls = [t.get("href") or t.get("src") or "" for t in soup.find_all(["a", "iframe"])]
    urls = [u if u.startswith("http") else "https:" + u if u.startswith("//") else u for u in urls]
    return list(dict.fromkeys(u for u in urls if any(h in u for h in MEDIA_HOSTS)))


def page_date(html: str) -> str:
    m = re.search(r"\b(\d{1,2}) (January|February|March|April|May|June|July|August|"
                  r"September|October|November|December) (20\d\d)\b", html)
    if not m:
        return ""
    return time.strftime("%Y-%m-%d", time.strptime(" ".join(m.groups()), "%d %B %Y"))


def enrich_from_rbnz(ev: Event) -> None:
    if not ev.source_page:
        return
    html = _get(ev.source_page)
    if not html:
        return
    ev.date = ev.date or page_date(html)
    links = media_links(html)
    if links and not ev.media_url:
        ev.media_url = links[0]
        ev.notes = (ev.notes + f" | candidates: {' '.join(links)}").strip(" |")


def crawl_rbnz_events(years: range) -> list[Event]:
    """Find FEC hearing pages under the RBNZ events listing for each month."""
    found = []
    months = ["january", "february", "march", "april", "may", "june", "july",
              "august", "september", "october", "november", "december"]
    for y in years:
        for m in months:
            listing = _get(f"{RBNZ}/news-and-events/events/{y}/{m}")
            if not listing:
                continue
            for a in BeautifulSoup(listing, "html.parser").find_all("a", href=True):
                h = a["href"]
                if re.search(r"fec|finance-and-expenditure", h, re.I):
                    url = h if h.startswith("http") else RBNZ + h
                    found.append(Event(event_id=f"{y}-{months.index(m)+1:02d}-fec", source_page=url))
    return found


def search_video_platforms(max_per_query: int = 50) -> list[Event]:
    import yt_dlp

    out = []
    opts = {"quiet": True, "extract_flat": True, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        for q in SEARCHES:
            try:
                res = ydl.extract_info(f"ytsearch{max_per_query}:{q}", download=False)
            except Exception as e:  # network / extractor failures shouldn't kill discovery
                print(f"  ! search '{q}': {e}")
                continue
            for e in res.get("entries") or []:
                title = e.get("title") or ""
                if not re.search(r"finance and expenditure|select committee|\bFEC\b", title, re.I):
                    continue
                if not re.search(r"reserve bank|monetary policy|RBNZ", title, re.I):
                    continue
                out.append(Event(event_id=f"yt-{e['id']}", media_url=e.get("url") or "",
                                 title=title, duration_s=str(e.get("duration") or ""),
                                 notes="auto: youtube search"))
    return out


def load_catalogue() -> dict[str, Event]:
    if not CATALOGUE.exists():
        return {}
    with CATALOGUE.open() as f:
        return {r["event_id"]: Event(**{k: r.get(k, "") for k in FIELDS}) for r in csv.DictReader(f)}


def save_catalogue(events: dict[str, Event]) -> None:
    CATALOGUE.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(events.values(), key=lambda e: (e.date or "9999", e.event_id))
    with CATALOGUE.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for e in rows:
            d = asdict(e)
            d.pop("extra")
            w.writerow(d)
    print(f"wrote {len(rows)} events -> {CATALOGUE}")


def run(crawl_years: range | None = None, search: bool = True) -> None:
    events = load_catalogue()
    with (CONFIG / "seed_events.csv").open() as f:
        for r in csv.DictReader(f):
            ev = events.get(r["event_id"]) or Event(event_id=r["event_id"])
            for k in ("date", "statement", "body", "source_page", "media_url", "notes"):
                if r.get(k):
                    setattr(ev, k, r[k])
            if r.get("media_url"):
                ev.verified = "1"
            events[ev.event_id] = ev
    if crawl_years:
        for ev in crawl_rbnz_events(crawl_years):
            events.setdefault(ev.event_id, ev)
    for ev in events.values():
        enrich_from_rbnz(ev)
    if search:
        for ev in search_video_platforms():
            if not any(e.media_url == ev.media_url for e in events.values()):
                events[ev.event_id] = ev
    save_catalogue(events)
