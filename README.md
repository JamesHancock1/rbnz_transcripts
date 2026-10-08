# RBNZ FEC hearing transcripts

Gets audio from the Finance and Expenditure Committee (FEC) hearings with the
Reserve Bank of New Zealand that follow each Monetary Policy Statement (MPS) or
Monetary Policy Review. It transcribes each hearing and builds a corpus in the
same schema as the RBNZ media-conference transcripts.

## Pipeline

```bash
pip install -e '.[asr]'           # whisperx + torch; a GPU is strongly recommended
export HF_TOKEN=...               # accept pyannote/speaker-diarization-3.1 terms on HF first

rbnz-fec discover --crawl-from 2015   # -> data/catalogue.csv (review rows, set verified=1)
rbnz-fec download [--cookies fb_cookies.txt]   # -> data/audio/<event_id>.wav
rbnz-fec transcribe                   # -> data/transcripts/<event_id>.json
# name the speakers: config/speakers/<event_id>.json
rbnz-fec export --media-corpus media_turns.csv  # -> data/corpus.csv + .txt per hearing
```

## Where the hearings are hosted

| Period | Host | Notes |
|---|---|---|
| 2021 – mid-2022 | FEC Facebook page | `yt-dlp` needs a logged-in `--cookies` file |
| late 2022 – 2023 | Vimeo (embedded on RBNZ event pages) | |
| 2024 – present | Parliament website livestream archive / Parliament YouTube | |
| pre-2021 | Parliament "In the House" / Parliament YouTube / Vimeo | found by the `discover` YouTube search; check each one |

`config/seed_events.csv` lists the hand-curated hearings. It always wins over
auto-discovered rows. Paste a confirmed `media_url` there to mark a hearing verified.
Committee videos often include unrelated business, so trim or check start times.

## Accuracy notes

- Whisper large-v3, beam 5, English forced, `condition_on_previous_text=False` (stops repetition loops).
- A domain prompt with RBNZ, OCR and MP names and te reo terms. Override it in `config/asr_prompt.txt`.
- WhisperX forced alignment gives word timestamps. pyannote 3.1 diarisation then assigns speakers.
- Check the first transcripts by hand against the audio before running the whole archive.
