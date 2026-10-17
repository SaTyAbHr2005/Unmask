import os
from pathlib import Path

from dotenv import load_dotenv

DATA_DIR = Path(__file__).resolve().parents[2] / "data"   # HackForge/data, independent of cwd

load_dotenv()


def env(name: str) -> str | None:
    return os.getenv(name) or None


ETH_USD = 3000.0
PRIOR = 0.01
HALF_LIFE_S = 6 * 3600
DB_NAME = "unmask"
