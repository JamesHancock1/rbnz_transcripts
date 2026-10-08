"""Parliament video archives that hold FEC hearings.

* Parliament On Demand (52nd-53rd Parliaments, May 2018 - Aug 2023): a static
  JSON index (files.js) of every committee recording, served from Azure Front Door.
  Entries have dates but no titles, so they're matched to MPS dates.
* Parliament's Vimeo FEC showcase (54th Parliament, late 2023 onward): titled
  videos, read with yt-dlp.
"""
from __future__ import annotations

import csv
import json
import re
from datetime import date, timedelta
from urllib.parse import quote

import requests

from .paths import CONFIG

ONDEMAND_INDEX = "https://ondemand.parliament.nz/files.js"
ONDEMAND_MEDIA = "https://sit-sc-archive-daasadfxamcfb4du.a02.azurefd.net/select-committee-archive-videos/{committee}/{file}"
VIMEO_SHOWCASE = "https://vimeo.com/showcase/10758103"
COMMITTEE = "Finance and Expenditure"
MAX_LAG_DAYS = 8  # hearings are usually the day after the MPS, occasionally the next week


def mps_dates() -> list[tuple[date, str]]:
    with (CONFIG / "mps_dates.csv").open() as f:
        return [(date.fromisoformat(r["date"]), r["statement"]) for r in csv.DictReader(f)]


def _secs(hms: str) -> int:
    h, m, s = hms.split(":")
    return int(h) * 3600 + int(m) * 60 + int(float(s))


def ondemand_recordings() -> list[dict]:
    js = requests.get(ONDEMAND_INDEX, timeout=60).text
    rows = json.loads(js[js.index("`") + 1: js.rindex("`")])
    return [r for r in rows if r["select_committee"] == COMMITTEE]


def ondemand_candidates() -> list[dict]:
    """One candidate per MPS: the FEC sitting the day after it, else same day, else the next 2-8 days.

    A sitting can be split into several files; all of them are kept (in order)
    so the hearing can be located and trimmed later.
    """
    recs = ondemand_recordings()
    by_day: dict[date, list[dict]] = {}
    for r in recs:
        by_day.setdefault(date.fromisoformat(r["date"]), []).append(r)
    out = []
    for mps, stmt in mps_dates():
        for lag in (1, 0, *range(2, MAX_LAG_DAYS + 1)):
            day = mps + timedelta(days=lag)
            if day in by_day:
                files = sorted(by_day[day], key=lambda r: r["file_name"])
                for i, r in enumerate(files):
                    out.append({
                        "event_id": f"{mps:%Y-%m}-fec" + (f"-p{i + 1}" if len(files) > 1 else ""),
                        "date": day.isoformat(), "statement": stmt,
                        "media_url": ONDEMAND_MEDIA.format(committee=quote(COMMITTEE), file=r["file_name"]),
                        "title": f"FEC sitting {day} ({r['file_name']})",
                        "duration_s": str(_secs(r["duration"])),
                        "notes": f"auto: ondemand, MPS {mps} +{lag}d; sitting has {len(files)} file(s)",
                    })
                break
    return out


def vimeo_candidates() -> list[dict]:
    import yt_dlp

    with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True, "ignoreerrors": True}) as y:
        res = y.extract_info(VIMEO_SHOWCASE, download=False) or {}
    mps = mps_dates()
    out = []
    for e in res.get("entries") or []:
        if not e:
            continue
        title = e.get("title") or ""
        m = re.search(r"(\d{1,2})[ /.-](\w+)[ /.-](20\d\d)", title)
        when = None
        if m:
            for fmt in ("%d %B %Y", "%d %b %Y", "%d %m %Y"):
                try:
                    from datetime import datetime
                    when = datetime.strptime(" ".join(m.groups()), fmt).date()
                    break
                except ValueError:
                    pass
        near = when and any(0 <= (when - d).days <= MAX_LAG_DAYS for d, _ in mps)
        if near or re.search(r"reserve bank|monetary policy", title, re.I):
            out.append({"event_id": f"vimeo-{e['id']}", "date": when.isoformat() if when else "",
                        "statement": "MPS", "media_url": e.get("url") or f"https://vimeo.com/{e['id']}",
                        "title": title, "duration_s": str(e.get("duration") or ""),
                        "notes": "auto: vimeo showcase"})
    return out
