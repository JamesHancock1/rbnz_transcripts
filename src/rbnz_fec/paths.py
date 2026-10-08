from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
DATA = ROOT / "data"
CATALOGUE = DATA / "catalogue.csv"
AUDIO = DATA / "audio"
TRANSCRIPTS = DATA / "transcripts"
