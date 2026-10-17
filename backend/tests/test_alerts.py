import httpx
import pytest

from gt import db
from gt.defense import alerts
from gt.fusion.evidence import verify_audit
from gt.schema import Alert, AuditEntry


def A(i="a1", kind="exit"):
    return Alert(i, kind, "Exch-A", "~$9M likely to reach Exch-A in ~11h")


@pytest.fixture
def conn(monkeypatch):
    monkeypatch.setattr(alerts, "env", lambda k: None)   # no real webhooks in tests
    return db.connect("mongomock://")


def get(conn, i):
    return db.select(conn, Alert, {"alert_id": i})[0]


def test_queue_is_pending_and_sends_nothing(conn):
    sent = []
    alerts.queue(conn, [A()])
    assert get(conn, "a1").status == "pending" and get(conn, "a1").created_ts > 0 and not sent


def test_approve_sends_and_audits(conn):
    sent = []
    alerts.queue(conn, [A()])
    a = alerts.approve(conn, "a1", "analyst1", send=lambda text: sent.append(text) or True)
    assert a.status == "sent" and get(conn, "a1").status == "sent"
    assert "EXIT" in sent[0] and "Exch-A" in sent[0]
    assert [e.action for e in db.select(conn, AuditEntry)] == ["approve_alert", "send_alert"]
    assert verify_audit(conn)


def test_cannot_approve_twice_or_unknown(conn):
    alerts.queue(conn, [A()])
    alerts.approve(conn, "a1", "x", send=lambda t: True)
    with pytest.raises(ValueError):
        alerts.approve(conn, "a1", "x", send=lambda t: True)
    with pytest.raises(ValueError):
        alerts.approve(conn, "nope", "x")


def test_no_channel_configured_stays_approved(conn):
    alerts.queue(conn, [A()])
    assert alerts.approve(conn, "a1", "analyst1").status == "approved"


def test_failed_send_stays_approved(conn):
    alerts.queue(conn, [A("a1"), A("a2")])
    assert alerts.approve(conn, "a1", "x", send=lambda t: False).status == "approved"

    def boom(text):
        raise httpx.ConnectError("down")
    assert alerts.approve(conn, "a2", "x", send=boom).status == "approved"


def test_requeue_keeps_existing_status(conn):
    alerts.queue(conn, [A()])
    alerts.approve(conn, "a1", "x", send=lambda t: True)
    alerts.queue(conn, [A()])                       # pipeline runs again
    assert get(conn, "a1").status == "sent"


def test_dismiss(conn):
    alerts.queue(conn, [A()])
    assert alerts.dismiss(conn, "a1", "analyst1").status == "dismissed"
    with pytest.raises(ValueError):
        alerts.approve(conn, "a1", "analyst1")


def test_default_sender_discord(monkeypatch, conn):
    posted = []

    class R:
        status_code = 204
    monkeypatch.setattr(alerts, "env", lambda k: "https://discord.example/hook" if k == "DISCORD_WEBHOOK_URL" else None)
    monkeypatch.setattr(alerts.httpx, "post", lambda url, json, timeout: posted.append((url, json)) or R())
    alerts.queue(conn, [A()])
    assert alerts.approve(conn, "a1", "x").status == "sent"
    assert posted[0][0] == "https://discord.example/hook" and "Exch-A" in posted[0][1]["content"]


def test_default_sender_telegram(monkeypatch, conn):
    posted = []

    class R:
        status_code = 200
    keys = {"TELEGRAM_BOT_TOKEN": "123:abc", "TELEGRAM_CHAT_ID": "-100"}
    monkeypatch.setattr(alerts, "env", lambda k: keys.get(k))
    monkeypatch.setattr(alerts.httpx, "post", lambda url, json, timeout: posted.append((url, json)) or R())
    alerts.queue(conn, [A()])
    assert alerts.approve(conn, "a1", "x").status == "sent"
    assert posted[0][0].endswith("/bot123:abc/sendMessage") and posted[0][1]["chat_id"] == "-100"
