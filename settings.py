"""Shared paths; loading configuration must not create files or contact services."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")
DATA_DIR = Path(os.environ.get("DATA_DIR") or (
    "/data" if os.getenv("RAILWAY_ENVIRONMENT") else PROJECT_DIR / "data"
)).expanduser().resolve()
DB_PATH = DATA_DIR / "users.db"
