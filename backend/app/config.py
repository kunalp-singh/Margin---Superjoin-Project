import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
# Vercel's deployed filesystem is read-only apart from /tmp. Persistent
# deployments should provide an external DATABASE_URL and object storage.
RUNNING_ON_VERCEL = any(
    os.getenv(name)
    for name in ("VERCEL", "VERCEL_ENV", "VERCEL_URL")
)
DATA_DIR = Path("/tmp/margin-data") if RUNNING_ON_VERCEL else BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/margin.db")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DISABLE_GEMINI = os.getenv("DISABLE_GEMINI", "0").lower() in {"1", "true", "yes"}
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")
CANDIDATE_SIMILARITY_THRESHOLD = float(os.getenv("CANDIDATE_SIMILARITY_THRESHOLD", "0.30"))
TOP_K_CANDIDATES = int(os.getenv("TOP_K_CANDIDATES", "5"))
PIPELINE_VERSION = os.getenv("PIPELINE_VERSION", "2.0")
GEMINI_TIMEOUT_SECONDS = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "20"))
GEMINI_MAX_RETRIES = max(0, int(os.getenv("GEMINI_MAX_RETRIES", "2")))
GEMINI_RETRY_BASE_SECONDS = min(5.0, max(0.1, float(os.getenv("GEMINI_RETRY_BASE_SECONDS", "0.5"))))
