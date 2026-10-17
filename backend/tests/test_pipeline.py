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
