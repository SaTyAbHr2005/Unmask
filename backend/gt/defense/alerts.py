"""Human-in-the-loop alerts: the engine only *proposes*; nothing leaves the system until an analyst approves.
Every approval and every send is written to the tamper-evident audit chain."""
import dataclasses
import logging
import time

import httpx

from gt import db
from gt.config import env
from gt.fusion.evidence import audit
from gt.schema import Alert

log = logging.getLogger(__name__)
DISCORD_LIMIT = 2000


def queue(conn, new_alerts: list[Alert]) -> None:
    """Add proposals as 'pending'. An alert that already exists keeps its status (re-runs never reset a decision)."""
    now = int(time.time())
    fresh = [dataclasses.replace(a, status="pending", created_ts=a.created_ts or now)
             for a in new_alerts if not conn.alert.find_one({"_id": a.alert_id})]
    db.insert(conn, fresh)


def _load_pending(conn, alert_id: str) -> Alert:
    found = db.select(conn, Alert, {"alert_id": alert_id})
    if not found:
        raise ValueError(f"unknown alert {alert_id}")
    if found[0].status != "pending":
        raise ValueError(f"alert {alert_id} is already {found[0].status}")
    return found[0]


def _default_sender():
    """Discord webhook if configured, else Telegram bot, else None (nothing to send to)."""
    if url := env("DISCORD_WEBHOOK_URL"):
        return lambda text: httpx.post(url, json={"content": text[:DISCORD_LIMIT]}, timeout=15).status_code < 300
    token, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if token and chat:
        return lambda text: httpx.post(f"https://api.telegram.org/bot{token}/sendMessage",
                                       json={"chat_id": chat, "text": text}, timeout=15).status_code < 300
    return None


def approve(conn, alert_id: str, actor: str, send=None) -> Alert:
    """pending → approved (audited) → sent (audited) if a channel accepts it; stays 'approved' otherwise."""
    a = dataclasses.replace(_load_pending(conn, alert_id), status="approved")
    db.insert(conn, [a])
    audit(conn, actor, "approve_alert", alert_id)
    sender = send or _default_sender()
    if sender is None:
        return a
    try:
        ok = sender(f"[Unmask] {a.kind.upper()} — {a.target}: {a.message}")
    except httpx.HTTPError as e:
        log.warning("alert %s send failed: %r", alert_id, e)
        ok = False
    if ok:
        a = dataclasses.replace(a, status="sent")
        db.insert(conn, [a])
        audit(conn, "system", "send_alert", alert_id)
    return a


def dismiss(conn, alert_id: str, actor: str) -> Alert:
    a = dataclasses.replace(_load_pending(conn, alert_id), status="dismissed")
    db.insert(conn, [a])
    audit(conn, actor, "dismiss_alert", alert_id)
    return a
