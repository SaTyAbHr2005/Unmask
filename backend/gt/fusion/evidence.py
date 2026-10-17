"""Evidence you can defend: every piece of data is stored under the hash of its content, and every human
decision goes into a hash chain, so any later edit or deletion in the middle is detectable."""
import dataclasses
import hashlib
import json
import time

from gt import db
from gt.schema import AuditEntry, Evidence


def _canonical(obj) -> str:
    data = dataclasses.asdict(obj) if dataclasses.is_dataclass(obj) else obj
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def record(conn, obj, kind: str, source_url: str = "") -> str:
    """Store obj as evidence (once) and return its sha256. Same content → same hash, no duplicate."""
    payload = _canonical(obj)
    h = hashlib.sha256(payload.encode()).hexdigest()
    if not conn.evidence.find_one({"_id": h}):
        db.insert(conn, [Evidence(h, kind, source_url, int(time.time()), payload)])
    return h


def _entry_id(prev_hash: str, actor: str, action: str, target: str, ts: int) -> str:
    return hashlib.sha256(f"{prev_hash}|{actor}|{action}|{target}|{ts}".encode()).hexdigest()[:16]


def _tails(entries: list[AuditEntry]) -> set[str]:
    """Entries nobody points back to — a healthy chain has exactly one (the newest)."""
    return {e.entry_id for e in entries} - {e.prev_hash for e in entries}


def audit(conn, actor: str, action: str, target: str, ts: int | None = None) -> AuditEntry:
    """Append one human action to the chain.
    ponytail: single writer assumed; two simultaneous appends would fork the chain — add a lock if multi-user."""
    tails = _tails(db.select(conn, AuditEntry))
    prev = min(tails) if tails else ""
    ts = int(time.time()) if ts is None else ts
    entry = AuditEntry(_entry_id(prev, actor, action, target, ts), ts, actor, action, target, prev)
    db.insert(conn, [entry])
    return entry


def verify_audit(conn) -> bool:
    """Recompute the whole chain from the newest entry back to the first. False if any entry was edited,
    or one in the middle was removed. (Removing only the newest entry needs an external anchor: the report
    prints the newest entry id.)"""
    entries = db.select(conn, AuditEntry)
    if not entries:
        return True
    tails = _tails(entries)
    if len(tails) != 1:
        return False
    by_id = {e.entry_id: e for e in entries}
    cur, seen = next(iter(tails)), 0
    while cur:
        e = by_id.get(cur)
        if e is None or _entry_id(e.prev_hash, e.actor, e.action, e.target, e.ts) != e.entry_id:
            return False
        seen += 1
        cur = e.prev_hash
    return seen == len(entries)
