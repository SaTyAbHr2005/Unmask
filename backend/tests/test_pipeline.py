import dataclasses
import time

import pytest

from gt import db
from gt.pipeline import load_results, load_scenario, run
from gt.schema import Alert, Link, Transfer
from gt.simulator import simulate


@pytest.fixture(scope="module")
def done():
    conn = db.connect("mongomock://")
    s = simulate(seed=11)
    load_scenario(conn, s, name="Simulated attack (seed 11)")
    t = time.time()
    r = run(conn)
    return conn, s, r, time.time() - t


def test_end_to_end_quality(done):
    conn, s, r, secs = done
    assert secs < 30
    assert r.metrics["f1"] >= 0.85 and r.metrics["handle_correct"]
    assert r.links[0].identity == "forum:ghostfox" and r.links[0].score >= 0.8
    assert r.links[0].evidence                          # signals are recorded as hashed evidence


def test_alerts_queued(done):
    conn, *_ = done
    kinds = [a.kind for a in db.select(conn, Alert)]
    assert "exit" in kinds and "prewarn" in kinds and "freeze" in kinds
    assert all(a.status == "pending" for a in db.select(conn, Alert))
    assert len(kinds) < 20                              # grouped, not one per wallet


def test_defense_outputs(done):
    conn, s, r, _ = done
    assert r.exits and r.exits[0].exchange in s.truth.exit_exchanges
    assert sum(h.usd for h in r.holdings if h.freezable) > 0
    assert r.decoys and not r.decoys & {w for w, k in r.clusters.items() if k == 0}
    assert r.bridges and r.utc_offsets["cluster:0"][0] in {8, 9, 10}
    assert r.bot_scores and max(r.bot_scores.values()) > 0.6


def test_results_are_saved(done):
    conn, *_ = done
    saved = load_results(conn)
    assert saved["metrics"]["handle_correct"] and saved["links"][0]["identity"] == "forum:ghostfox"
    assert saved["case"] == "Simulated attack (seed 11)" and saved["stolen_usd"] == pytest.approx(42_000_000)


def test_analyst_decisions_survive_rerun(done):
    conn, *_ = done
    top = db.select(conn, Link)[0]
    db.insert(conn, [dataclasses.replace(top, status="rejected")])
    run(conn)
    assert db.select(conn, Link, {"link_id": top.link_id})[0].status == "rejected"


def test_empty_case_does_not_crash():
    r = run(db.connect("mongomock://"))
    assert r.links == [] and r.exits == [] and r.metrics is None


def test_explicit_seed_without_victim_label():
    conn = db.connect("mongomock://")
    load_scenario(conn, simulate(seed=12), name="x")
    meta = conn.meta.find_one({"_id": "scenario"})["value"]
    victim = next(a for a, l in meta["labels"].items() if l == "victim")
    main = max((t for t in db.select(conn, Transfer) if t.from_addr == victim), key=lambda t: t.amount).to_addr
    assert run(conn, seeds={main}).metrics["recall"] >= 0.9


def test_deposit_composition_in_results(done):
    conn, s, r, _ = done
    assert r.deposits and all(d["exchange"] in s.truth.exit_exchanges for d in r.deposits)
    assert any(d["method"] != "unmatched" and d["n_pieces"] >= 5 for d in r.deposits)


def test_time_to_freeze(done):
    conn, s, r, _ = done
    t = r.timing
    assert t["theft_ts"] == 1_760_000_000
    assert t["first_cashout_ts"] > t["theft_ts"] and t["time_to_first_cashout_s"] == t["first_cashout_ts"] - t["theft_ts"]
    assert t["prewarn_lead_s"] > 0                                  # warning came before the theft
    assert t["next_predicted_exit_s"] is None or t["next_predicted_exit_s"] > 0


def test_wallet_features_in_results(done):
    conn, s, r, _ = done
    main = sorted(s.truth.attacker_wallets)[0]
    f = r.features[main]
    assert f["n_tx"] > 100 and set(f) >= {"mean_gas", "round_frac", "cv_gap", "active_hours"}
    saved = load_results(conn)
    assert saved["features"][main]["n_tx"] == f["n_tx"] and "timing" in saved and "deposits" in saved


def test_newer_osint_does_not_age_the_case():
    """Real posts collected today must not make an older case look a year stale (decay uses chain time)."""
    from gt.osint.extract import make_post
    conn = db.connect("mongomock://")
    load_scenario(conn, simulate(seed=11), name="x")
    db.insert(conn, [make_post("rss", "Blog - Chainalysis", 1_792_000_000, "weekly roundup")])   # ~1 year later
    r = run(conn)
    assert r.links[0].identity == "forum:ghostfox" and r.links[0].score >= 0.8
    assert r.metrics["handle_correct"]
