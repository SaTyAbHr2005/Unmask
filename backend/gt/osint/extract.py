"""Turn raw public text into OsintPosts and pull out identity markers (addresses, handles, emails…)."""
import hashlib
import ipaddress
import re

from gt.chain.normalize import to_utc
from gt.schema import Entity, OsintPost

# Order matters only for readability: the hex patterns refuse to match inside a longer hex run,
# so a 64-hex tx hash never also yields a 40-hex address.
PATTERNS = [
    ("tx", re.compile(r"0x[0-9a-fA-F]{64}(?![0-9a-fA-F])")),
    ("address", re.compile(r"0x[0-9a-fA-F]{40}(?![0-9a-fA-F])")),
    ("email", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("handle", re.compile(r"(?<![\w.@])@([A-Za-z0-9_]{2,32})")),
    ("ens", re.compile(r"(?<![\w.@-])([a-z0-9-]+\.eth)\b", re.IGNORECASE)),
    ("ip", re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d.]\d)")),
]


def make_post(source: str, author: str, ts_raw, text: str, url: str = "") -> OsintPost | None:
    ts = to_utc(ts_raw)
    if ts is None:
        return None
    pid = hashlib.sha1(f"{source}|{author}|{ts}|{text}".encode()).hexdigest()[:16]
    return OsintPost(pid, source, author, ts, text, url)


def _valid_ip(s: str) -> bool:
    try:
        ipaddress.IPv4Address(s)
        return True
    except ValueError:
        return False


def extract(post: OsintPost) -> list[Entity]:
    found: dict[tuple[str, str], None] = {}   # dict keeps first-seen order and dedupes
    for kind, rx in PATTERNS:
        for m in rx.finditer(post.text):
            value = (m.group(1) if rx.groups else m.group(0)).lower()
            if kind == "ip" and not _valid_ip(value):
                continue
            found[(kind, value)] = None
    return [Entity(hashlib.sha1(f"{post.post_id}|{k}|{v}".encode()).hexdigest()[:16], post.post_id, k, v)
            for k, v in found]
