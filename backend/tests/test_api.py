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
    cases = client.get("/api/replays").json()
    assert any(c["id"] == "euler-2023" and c["source"].startswith("https://") for c in cases)


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
    shared = api.STATE["conn"]
    api.STATE["conn"] = db.connect("mongomock://")
    try:
        c = TestClient(api.app)
        assert c.get("/api/links").json() == []
        assert c.get("/api/money-now").json()["total_usd"] == 0
        assert c.get("/api/graph").json() == {"nodes": [], "edges": []}
        assert c.get("/api/matrix").json() == {"wallets": [], "buckets": [], "counts": []}
    finally:
        api.STATE["conn"] = shared


def test_osint_collect_adds_posts_and_searches_case_addresses(client, monkeypatch):
    from gt.osint.extract import make_post
    seen = {}
    monkeypatch.setattr(api, "collect_rss", lambda urls: [make_post("rss", "rekt", 1_760_000_100, "pool drained by 0x" + "ab" * 20)])
    monkeypatch.setattr(api, "collect_github", lambda qs: seen.setdefault("q", qs) and [make_post("github", "dev1", 1_760_000_200, "fix")])

    async def tg(channels):
        seen["tg"] = channels
        return []
    monkeypatch.setattr(api, "collect_telegram", tg)
    before_posts = api.conn().osintpost.count_documents({})
    r = client.post("/api/osint/collect", json={"telegram_channels": ["hacks_watch"]}).json()
    assert (r["rss"], r["github"], r["telegram"]) == (1, 1, 0) and r["entities"] >= 1
    assert any(q.startswith("0x") and len(q) == 42 for q in seen["q"])   # the case's seed wallet is searched
    assert seen["tg"] == ["hacks_watch"]
    assert r["total_posts"] >= before_posts + 2


def test_mempool(client, monkeypatch):
    monkeypatch.setattr(api, "env", lambda k: None)
    m = client.get("/api/mempool").json()
    assert m["available"] is False and m["watching"] > 0
    monkeypatch.setattr(api, "env", lambda k: "key")
    monkeypatch.setattr(api, "pending_count", lambda watch: 3)
    assert client.get("/api/mempool").json() == {"available": True, "pending": 3, "watching": m["watching"]}


def test_wallet_detail(client):
    g = client.get("/api/graph", params={"limit": 50}).json()
    top = next(n for n in g["nodes"] if n["kind"] == "attacker")
    w = client.get(f"/api/wallet/{top['id']}").json()
    assert w["kind"] == "attacker" and w["cluster"] == 0 and w["features"]["n_tx"] >= 1
    assert "bot_score" in w and w["transfers"] and len(w["transfers"]) <= 25
    assert client.get("/api/wallet/0x" + "9" * 40).status_code == 404
    assert client.get("/api/wallet/not-an-address").status_code == 400


def test_matrix_and_bot_scores_on_graph(client):
    m = client.get("/api/matrix", params={"top": 10}).json()
    assert 0 < len(m["wallets"]) <= 10 and len(m["counts"]) == len(m["wallets"])
    assert all(len(row) == len(m["buckets"]) for row in m["counts"])
    g = client.get("/api/graph", params={"limit": 100}).json()
    assert any(n["bot_score"] is not None and n["bot_score"] > 0.6 for n in g["nodes"])


def test_timing_and_deposits_exposed(client):
    t = client.get("/api/money-now").json()["timing"]
    assert t["time_to_first_cashout_s"] > 0 and t["prewarn_lead_s"] > 0
    rep = client.get("/api/report").json()
    assert rep["timing"]["theft_ts"] and rep["deposits"]
    assert all(d["n_pieces"] >= 2 for d in rep["deposits"])          # report shows only real reconstructions


def test_polish_is_opt_in(client, monkeypatch):
    calls = []
    monkeypatch.setattr(api.score.llm, "complete", lambda p, **k: calls.append(1) or "AI summary.")
    plain = client.get("/api/links").json()
    assert not calls and not plain[0]["explanation"].startswith("AI summary.")
    polished = client.get("/api/links", params={"polish": True}).json()
    assert polished[0]["explanation"].startswith("AI summary.") and len(calls) == 3   # top 3 only


def test_reveal_personal_details_is_audited(client):
    before = client.get("/api/report").json()["audit_entries"]
    r = client.post("/api/privacy/reveal", json={"reason": "exchange freeze request"}, headers={"X-Analyst": "satya"})
    assert r.status_code == 200 and r.json()["revealed"] is True
    rep = client.get("/api/report").json()
    assert rep["audit_entries"] == before + 1 and rep["audit_ok"]
    assert client.post("/api/privacy/reveal", json={"reason": ""}).status_code == 422   # a reason is required


def test_matrix_keeps_quiet_hours_and_sankey_has_no_empty_routes(client):
    m = client.get("/api/matrix", params={"top": 5}).json()
    steps = {b - a for a, b in zip(m["buckets"], m["buckets"][1:])}
    assert steps == {3600}                                  # contiguous hours, quiet ones included
    sk = client.get("/api/sankey").json()
    assert all(l["value"] > 0 for l in sk["links"]) and all(
        any(l["source"] == i or l["target"] == i for l in sk["links"]) for i in range(len(sk["nodes"])))
