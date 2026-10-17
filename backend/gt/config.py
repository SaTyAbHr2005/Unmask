import os
from pathlib import Path

from dotenv import load_dotenv

DATA_DIR = Path(__file__).resolve().parents[2] / "data"   # HackForge/data, independent of cwd

load_dotenv()


def env(name: str) -> str | None:
    return os.getenv(name) or None


ETH_USD = 3000.0
STABLES = {"USDT", "USDC", "DAI"}
ETH_LIKE = {"ETH", "WETH", "stETH", "wstETH"}   # ponytail: staked ETH priced as 1 ETH (wstETH is ~1.15); fine for triage


def usd(asset: str, amount: float) -> float | None:
    """Fixed demo prices; None = unknown token price."""
    if asset in ETH_LIKE:
        return amount * ETH_USD
    return amount if asset in STABLES else None


PRIOR = 0.01
HALF_LIFE_S = 7 * 24 * 3600   # attribution confidence halves after a week without fresh activity
DB_NAME = "unmask"

# OSINT sources (feeds checked live 2026-10-17; drop any that stop answering)
RSS_FEEDS = [
    "https://rekt.news/rss/feed.xml",
    "https://www.web3isgoinggreat.com/feed.xml",
    "https://cointelegraph.com/rss/tag/hacks",
    "https://slowmist.medium.com/feed",
    "https://www.chainalysis.com/blog/feed/",
]
GITHUB_QUERIES = ["flashloan exploit", "drain pool exploit"]   # add the attacker's address prefix during a case
TELEGRAM_CHANNELS: list[str] = []                               # public channel usernames, filled per case
