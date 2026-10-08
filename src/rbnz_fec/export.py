"""Turn raw transcripts into speaker-labelled, readable output plus a combined
corpus in one schema shared with the RBNZ media-conference transcripts.

Speaker names: diarisation yields SPEAKER_00 etc. Map them per hearing in
config/speakers/<event_id>.json, e.g. {"SPEAKER_01": {"name": "Adrian Orr",
"role": "rbnz"}, "SPEAKER_00": {"name": "Chair", "role": "mp"}}.
Roles: rbnz | mp | chair | journalist | other.
"""
from __future__ import annotations

import json

import pandas as pd

from .discover import load_catalogue
from .paths import CONFIG, DATA, TRANSCRIPTS

CORPUS_COLUMNS = ["event_id", "date", "source", "turn", "start", "end",
                  "speaker_id", "speaker_name", "speaker_role", "text"]


def turns(doc: dict, speakers: dict) -> list[dict]:
    """Merge consecutive same-speaker segments into speaking turns."""
    out: list[dict] = []
    for s in doc["segments"]:
        if out and out[-1]["speaker_id"] == s["speaker"]:
            out[-1]["end"] = s["end"]
            out[-1]["text"] += " " + s["text"]
            continue
        info = speakers.get(s["speaker"], {})
        out.append({"start": s["start"], "end": s["end"], "speaker_id": s["speaker"],
                    "speaker_name": info.get("name", s["speaker"]),
                    "speaker_role": info.get("role", "unknown"), "text": s["text"]})
    for i, t in enumerate(out):
        t["turn"] = i
    return out


def _ts(sec: float) -> str:
    return f"{int(sec // 3600):02d}:{int(sec % 3600 // 60):02d}:{int(sec % 60):02d}"


def run(media_corpus: str | None = None) -> None:
    cat = load_catalogue()
    rows = []
    for p in sorted(TRANSCRIPTS.glob("*.json")):
        doc = json.loads(p.read_text())
        spk_file = CONFIG / "speakers" / f"{p.stem}.json"
        speakers = json.loads(spk_file.read_text()) if spk_file.exists() else {}
        ts = turns(doc, speakers)
        p.with_suffix(".txt").write_text(
            "\n\n".join(f"[{_ts(t['start'])}] {t['speaker_name']}: {t['text']}" for t in ts))
        date = cat[p.stem].date if p.stem in cat else ""
        rows += [{"event_id": p.stem, "date": date, "source": doc.get("source", "fec_hearing"), **t} for t in ts]

    df = pd.DataFrame(rows, columns=CORPUS_COLUMNS)
    if media_corpus:  # media-conference transcripts already in CORPUS_COLUMNS form
        df = pd.concat([df, pd.read_csv(media_corpus)[CORPUS_COLUMNS]], ignore_index=True)
    out = DATA / "corpus.csv"
    df.sort_values(["date", "source", "turn"]).to_csv(out, index=False)
    print(f"wrote {len(df)} turns -> {out}")
