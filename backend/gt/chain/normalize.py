"""Ingestion boundary: everything downstream sees lowercase addresses and int UTC seconds."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from gt.schema import Transfer


def norm_addr(a: str | None) -> str:
    return (a or "").strip().lower()


def to_utc(ts: int | str | None) -> int | None:
    if isinstance(ts, (int, float)):
        return int(ts)
    s = (ts or "").strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(s)
        except (TypeError, ValueError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def decode_message(input_data: str) -> str | None:
    """Readable text hidden in tx input data (hackers negotiate this way), else None."""
    try:
        text = bytes.fromhex(input_data.removeprefix("0x")).decode("utf-8").strip("\x00 ")
    except (ValueError, UnicodeDecodeError):
        return None
    if len(text) < 8 or sum(c.isprintable() for c in text) / len(text) < 0.7:
        return None
    return text


_ROLES = [("to", "mixer", "mixer_in"), ("from", "mixer", "mixer_out"),
          ("to", "bridge", "bridge_out"), ("from", "bridge", "bridge_in"),
          ("to", "dex", "swap"), ("from", "dex", "swap")]


def classify(t: Transfer, labels: dict[str, str]) -> str:
    if t.kind not in ("transfer", ""):
        return t.kind
    for side, label, kind in _ROLES:
        if labels.get(t.to_addr if side == "to" else t.from_addr) == label:
            return kind
    return t.kind
