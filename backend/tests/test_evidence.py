from gt import db
from gt.fusion.evidence import audit, record, verify_audit
from gt.schema import AuditEntry, Evidence, Transfer


def test_record_is_idempotent_and_hash_is_content_based():
    conn = db.connect("mongomock://")
    t = Transfer("0xh", "eth", 1, "0xa", "0xb", "ETH", 1.0)
    h1 = record(conn, t, "transfer", "https://etherscan.io/tx/0xh")
    h2 = record(conn, t, "transfer")
    assert h1 == h2 and len(h1) == 64
    assert len(db.select(conn, Evidence)) == 1
    assert record(conn, Transfer("0xh", "eth", 1, "0xa", "0xb", "ETH", 2.0), "transfer") != h1


def test_record_accepts_dicts_with_stable_key_order():
    conn = db.connect("mongomock://")
    assert record(conn, {"b": 1, "a": 2}, "signal") == record(conn, {"a": 2, "b": 1}, "signal")


def test_audit_chain_verifies():
    conn = db.connect("mongomock://")
    a = audit(conn, "analyst1", "confirm_link", "0:forum:ghostfox", ts=100)
    b = audit(conn, "analyst1", "approve_alert", "alert-1", ts=100)
    audit(conn, "analyst2", "export_report", "case", ts=101)
    assert a.prev_hash == "" and b.prev_hash == a.entry_id
    assert verify_audit(conn)


def test_editing_an_entry_breaks_the_chain():
    conn = db.connect("mongomock://")
    e = audit(conn, "analyst1", "confirm_link", "0:x", ts=1)
    audit(conn, "analyst1", "send_alert", "alert-1", ts=2)
    conn.auditentry.update_one({"_id": e.entry_id}, {"$set": {"actor": "someone_else"}})
    assert not verify_audit(conn)


def test_deleting_an_entry_breaks_the_chain():
    conn = db.connect("mongomock://")
    e = audit(conn, "a", "confirm_link", "0:x", ts=1)
    audit(conn, "a", "send_alert", "x", ts=2)
    audit(conn, "a", "export_report", "y", ts=3)
    conn.auditentry.delete_one({"_id": e.entry_id})
    assert not verify_audit(conn)


def test_empty_audit_is_valid():
    assert verify_audit(db.connect("mongomock://"))
    assert {AuditEntry, Evidence} <= set(__import__("gt.schema", fromlist=["ALL"]).ALL)
