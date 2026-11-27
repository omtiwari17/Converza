from pathlib import Path

BASE = Path(__file__).resolve().parent
UPLOAD_DIR = BASE / 'uploads'
OUTPUT_DIR = BASE / 'outputs'
MAX_UPLOAD_MB = 500
JOB_TTL_SECONDS = 3600
CONVERT_TIMEOUT = 900  # seconds per conversion


def ensure_dirs() -> None:
    """Create runtime upload and output directories if missing."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
