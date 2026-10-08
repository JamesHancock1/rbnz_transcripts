"""Accuracy-first transcription: WhisperX (Whisper large-v3 + forced word
alignment + pyannote speaker diarisation).

Accuracy choices:
  * large-v3 at beam 5, fp32 on CPU / fp16 on GPU, English forced (no lang-ID drift);
  * a domain prompt so the decoder knows OCR, MPS, NZ names and Te Reo terms;
  * forced alignment gives word timestamps, needed for clean speaker attribution;
  * pyannote 3.1 diarisation (requires HF_TOKEN and accepting the model terms).
"""
from __future__ import annotations

import json
import os

from .paths import AUDIO, CONFIG, TRANSCRIPTS

DEFAULT_PROMPT = (
    "Finance and Expenditure Committee hearing with the Reserve Bank of New Zealand, "
    "Te Pūtea Matua, on the Monetary Policy Statement. Official Cash Rate, OCR, CPI, "
    "Monetary Policy Committee, Governor Adrian Orr, Christian Hawkesby, Karen Silk, "
    "Paul Conway, Anna Breman, Grant Spencer, Graeme Wheeler, John McDermott, "
    "Kia ora, tēnā koe, Chair."
)


def _prompt() -> str:
    p = CONFIG / "asr_prompt.txt"
    return p.read_text().strip() if p.exists() else DEFAULT_PROMPT


def transcribe(event_id: str, model_name: str = "large-v3", diarize: bool = True) -> dict:
    import torch
    import whisperx

    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute = "float16" if device == "cuda" else "float32"
    audio = whisperx.load_audio(str(AUDIO / f"{event_id}.wav"))

    model = whisperx.load_model(
        model_name, device, compute_type=compute, language="en",
        asr_options={"beam_size": 5, "initial_prompt": _prompt(),
                     "condition_on_previous_text": False},  # avoids repetition loops
    )
    result = model.transcribe(audio, batch_size=16 if device == "cuda" else 4)

    align_model, meta = whisperx.load_align_model(language_code="en", device=device)
    result = whisperx.align(result["segments"], align_model, meta, audio, device,
                            return_char_alignments=False)

    if diarize:
        token = os.environ.get("HF_TOKEN")
        if not token:
            raise SystemExit("Set HF_TOKEN (and accept pyannote/speaker-diarization-3.1 terms) or pass --no-diarize")
        from whisperx.diarize import DiarizationPipeline

        dia = DiarizationPipeline(use_auth_token=token, device=device)
        result = whisperx.assign_word_speakers(dia(audio), result)

    doc = {
        "event_id": event_id,
        "source": "fec_hearing",
        "asr": {"model": model_name, "pipeline": "whisperx", "diarized": diarize},
        "segments": [
            {"start": round(s["start"], 2), "end": round(s["end"], 2),
             "speaker": s.get("speaker", "UNKNOWN"), "text": s["text"].strip(),
             "words": s.get("words", [])}
            for s in result["segments"]
        ],
    }
    TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
    (TRANSCRIPTS / f"{event_id}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    return doc


def run(model_name: str = "large-v3", diarize: bool = True, force: bool = False) -> None:
    for wav in sorted(AUDIO.glob("*.wav")):
        if not force and (TRANSCRIPTS / f"{wav.stem}.json").exists():
            continue
        print(f"[transcribe] {wav.stem}")
        transcribe(wav.stem, model_name, diarize)
