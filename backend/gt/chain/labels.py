import csv
from pathlib import Path

from gt.chain.normalize import norm_addr
from gt.config import DATA_DIR


def load_labels(folder: str | Path = DATA_DIR / "labels") -> dict[str, str]:
    """Merge every `address,label` CSV in folder. Lines starting with '#' are comments."""
    out: dict[str, str] = {}
    for path in sorted(Path(folder).glob("*.csv")):
        lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
        for row in csv.DictReader(lines):
            if row.get("address") and row.get("label"):
                out[norm_addr(row["address"])] = row["label"].strip()
    return out
