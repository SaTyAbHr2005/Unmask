import json

import pytest
from fastapi.testclient import TestClient

from gt import api, db
from gt.defense import alerts as alerts_mod


@pytest.fixture(scope="module")
def client():
    mp = pytest.MonkeyPatch()
    mp.setattr(alerts_mod, "env", lambda k: None)          # never post to real webhooks from tests
    api.STATE["conn"] = db.connect("mongomock://")
    c = TestClient(api.app)
    assert c.post("/api/simulate", params={"seed": 7}).status_code == 200
    assert c.post("/api/run").status_code == 200
    yield c
    mp.undo()


def test_health():
    c = TestClient(api.app)
    api.STATE["conn"] = api.STATE.get("conn") or db.connect("mongomock://")
    assert c.get("/api/health").json() == {"ok": True, "db": "mongomock"}


def test_simulate_and_run_summary(client):
    r = client.post("/api/run").json()
    assert r["metrics"]["handle_correct"] and r["links"] > 0 and r["alerts"] > 0


def test_graph(client):
    g = client.get("/api/graph", params={"cluster": 0, "limit": 200}).json()
    assert 0 < len(g["nodes"]) <= 200 and g["edges"]
    kinds = {n["kind"] for n in g["nodes"]}
    assert "attacker" in kinds and "exchange" in kinds
    ids = {n["id"] for n in g["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in g["edges"])


def test_links_have_explanations(client):
    links = client.get("/api/links").json()
    assert links[0]["identity"] == "forum:ghostfox" and links[0]["label"] == "high"
    assert links[0]["explanation"].startswith("Suspected")


def test_reject_survives_rerun(client):
    lid = client.get("/api/links").json()[1]["link_id"]
    r = client.post(f"/api/links/{lid}/reject", headers={"X-Analyst": "satya"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    client.post("/api/run")
    again = {l["link_id"]: l for l in client.get("/api/links").json()}
    assert again[lid]["status"] == "rejected" and again[lid]["label"] == "rejected"
    assert client.post("/api/links/nope/reject").status_code == 404
    assert client.post(f"/api/links/{lid}/delete").status_code == 404


def test_alert_approve_twice_is_409(client):
    pending = [a for a in client.get("/api/alerts").json() if a["status"] == "pending"]
    aid = pending[0]["alert_id"]
    assert client.post(f"/api/alerts/{aid}/approve").json()["status"] == "approved"   # no channel set → approved
    assert client.post(f"/api/alerts/{aid}/approve").status_code == 409
    assert client.post("/api/alerts/does-not-exist/approve").status_code == 404
    other = pending[1]["alert_id"]
    assert client.post(f"/api/alerts/{other}/dismiss").json()["status"] == "dismissed"


def test_money_now(client):
    m = client.get("/api/money-now").json()
    assert m["total_usd"] == pytest.approx(42_000_000)
    assert 0 < m["frozen_possible_usd"] <= m["total_usd"] and m["exits"]
    assert m["at_exchanges_usd"] > 0 and m["unspent_usd"] > 0


def test_timeline_heatmap_sankey(client):
    tl = client.get("/api/timeline").json()
    assert {e["type"] for e in tl} == {"post", "tx"} and tl == sorted(tl, key=lambda e: e["ts"])
    h = client.get("/api/heatmap/cluster:0").json()
    assert len(h["hours"]) == 24 and h["utc_offset"] in (8, 9, 10)
    hi = client.get("/api/heatmap/identity:forum:ghostfox").json()
    assert hi["utc_offset"] in (8, 9, 10)
    assert client.get("/api/heatmap/identity:nobody").status_code == 404
    sk = client.get("/api/sankey").json()
    names = [n["name"] for n in sk["nodes"]]
    assert "Stolen funds" in names and any(l["value"] > 0 for l in sk["links"])
    assert all(0 <= l["source"] < len(names) and 0 <= l["target"] < len(names) for l in sk["links"])


def test_report(client):
    r = client.get("/api/report").json()
    assert r["audit_ok"] and r["evidence_count"] > 0 and r["audit_head"]
    assert r["case"].startswith("Simulated attack") and r["links"]
    assert any(f["to"] == "Tether" for f in r["freeze_requests"])
    assert all("suspected" in f["text"].lower() for f in r["freeze_requests"])
    assert client.post("/api/report/export", headers={"X-Analyst": "satya"}).json()["audit_ok"]


def test_replay_name_is_validated(client):
    assert client.post("/api/replay/..%2F..%2Fsecrets").status_code in (400, 404)
    assert client.post("/api/replay/does_not_exist").status_code == 404


def test_live_requires_key_and_valid_addresses(client, monkeypatch):
    monkeypatch.setattr(api, "env", lambda k: None)
    assert client.post("/api/live/start", json={"watch": ["0x" + "a" * 40]}).status_code == 400
    monkeypatch.setattr(api, "env", lambda k: "key")
    assert client.post("/api/live/start", json={"watch": ["not-an-address"]}).status_code == 422


def test_live_stream_emits_queued_transfer(client):
    from gt.schema import Transfer
    api.LIVE_QUEUE.put_nowait(Transfer("0xlive", "eth", 1, "0xa", "0xb", "ETH", 1.0))
    with client.stream("GET", "/api/live", params={"max_events": 1}) as r:
        line = next(l for l in r.iter_lines() if l.startswith("data:"))
    assert json.loads(line[5:])["tx_hash"] == "0xlive"


def test_endpoints_before_any_run_are_safe():
    api.STATE["conn"] = db.connect("mongomock://")
    c = TestClient(api.app)
    assert c.get("/api/links").json() == []
    assert c.get("/api/money-now").json()["total_usd"] == 0
    assert c.get("/api/graph").json() == {"nodes": [], "edges": []}
