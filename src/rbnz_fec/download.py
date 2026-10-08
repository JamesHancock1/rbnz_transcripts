"""Download audio for catalogue rows as 16 kHz mono WAV (what Whisper expects)."""
from __future__ import annotations

import subprocess

from .discover import load_catalogue
from .paths import AUDIO


def download(event_id: str, url: str, cookies: str | None = None) -> None:
    out = AUDIO / f"{event_id}.wav"
    if out.exists():
        return
    AUDIO.mkdir(parents=True, exist_ok=True)
    cmd = ["yt-dlp", "-f", "bestaudio/best", "-x", "--audio-format", "wav",
           "--postprocessor-args", "ffmpeg:-ar 16000 -ac 1",
           "-o", str(AUDIO / f"{event_id}.%(ext)s"), url]
    if cookies:  # Facebook-hosted hearings (2021-22) usually need a logged-in cookie file
        cmd[1:1] = ["--cookies", cookies]
    print(f"[download] {event_id}: {url}")
    subprocess.run(cmd, check=True)


def run(only_verified: bool = True, cookies: str | None = None) -> None:
    for ev in load_catalogue().values():
        if not ev.media_url or (only_verified and ev.verified != "1"):
            continue
        try:
            download(ev.event_id, ev.media_url, cookies)
        except subprocess.CalledProcessError as e:
            print(f"  ! {ev.event_id} failed: {e}")
