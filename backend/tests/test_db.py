from gt import db
from gt.schema import Transfer, Link, Signal


def test_roundtrip_transfer():
    conn = db.connect("mongomock://")
    t = Transfer("0xh", "sim", 100, "0xa", "0xb", "ETH", 1.5)
    assert db.insert(conn, [t]) == 1
    assert db.select(conn, Transfer) == [t]


def test_roundtrip_nested_lists():
    conn = db.connect("mongomock://")
    l = Link("1:bob", 1, "bob", 0.9, [Signal("time_delta", 20.0, "x")], evidence=["abc"])
    db.insert(conn, [l])
    assert db.select(conn, Link, {"identity": "bob"}) == [l]


def test_insert_is_upsert_and_empty_is_noop():
    conn = db.connect("mongomock://")
    t = Transfer("0xh", "sim", 100, "0xa", "0xb", "ETH", 1.5)
    db.insert(conn, [t])
    db.insert(conn, [Transfer("0xh", "sim", 100, "0xa", "0xb", "ETH", 2.0)])
    assert [x.amount for x in db.select(conn, Transfer)] == [2.0]
    assert db.insert(conn, []) == 0


def test_clear_and_meta():
    conn = db.connect("mongomock://")
    db.insert(conn, [Transfer("0xh", "sim", 100, "0xa", "0xb", "ETH", 1.5)])
    db.put_meta(conn, "scenario", {"labels": {"0xa": "mixer"}})
    db.clear(conn)
    assert db.select(conn, Transfer) == []
    assert db.get_meta(conn, "scenario") == {"labels": {"0xa": "mixer"}}  # meta survives clear()
    assert db.get_meta(conn, "missing", 7) == 7
