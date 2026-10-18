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


def test_third_party_contracts_leave_the_attacker_cluster():
    from gt.pipeline import third_party_contracts
    T = lambda h, a, b, amt, kind="transfer": Transfer(h, "eth", 1_000 + len(h), a, b, "ETH", amt, kind=kind)
    txs = [T("1", "0xatk", "0xmine", 100.0, kind="deploy"),   # contract the attacker deployed: stays theirs
           T("2", "0xatk", "0xhop", 50.0), T("3", "0xhop", "0xsafe", 40.0),  # a multisig someone else runs
           T("4", "0xsafe", "0xstranger", 30.0)]                             # its other users must not join
    contracts = {"0xmine", "0xsafe"}
    hubs = third_party_contracts(txs, {"0xatk"}, {}, lambda a: a in contracts)
    assert hubs == {"0xsafe": "contract"}


@pytest.mark.parametrize("seed", [1, 23, 404, 2026])
def test_every_attack_number_is_a_different_attacker_and_still_found(seed):
    from gt.simulator import variant
    v = variant(seed)
    assert v["handles"]["forum"] != "ghostfox"
    conn = db.connect("mongomock://")
    load_scenario(conn, simulate(seed=seed, **v), name="x")
    r = run(conn)
    assert r.metrics["handle_correct"] and r.links[0].identity == f"forum:{v['handles']['forum']}"
    assert r.metrics["precision"] >= 0.95 and r.metrics["recall"] >= 0.95
    assert r.stolen_usd == pytest.approx(v["total_usd"])
    assert r.utc_offsets["cluster:0"][0] in range(v["utc_offset"] - 1, v["utc_offset"] + 2)


def test_money_only_counts_as_held_where_the_whole_history_was_loaded():
    from gt.pipeline import load_case
    T = lambda h, a, b, amt: Transfer(h, "eth", 1_000 + int(h), a, b, "ETH", amt)
    txs = [T("1", "0xv", "0xs", 100.0), T("2", "0xs", "0xa", 60.0), T("3", "0xs", "0xb", 40.0)]
    conn = db.connect("mongomock://")
    # 0xb's onward transfers were never fetched: its 40 ETH is "last seen", not held
    load_case(conn, txs, [], {"0xv": "victim"}, {}, None, "x", ["0xs"], 1000.0, ["0xs", "0xa"])
    r = run(conn)
    assert {h.address for h in r.holdings} == {"0xa"} and r.stolen_usd == 100_000


def test_real_trace_moves_get_their_role_when_loaded():
    from gt.pipeline import load_case
    conn = db.connect("mongomock://")
    load_case(conn, [Transfer("0x1", "eth", 1, "0xa", "0xtornado", "ETH", 5.0)], [], {"0xtornado": "mixer"}, {})
    assert db.select(conn, Transfer)[0].kind == "mixer_in"     # a trace only knows "transfer"; the API reads this


def test_traced_total_without_a_theft_counts_held_mixed_and_returned():
    from gt.pipeline import load_case
    conn = db.connect("mongomock://")
    T = lambda i, a, b, eth: Transfer(f"0x{i}", "eth", i, a, b, "ETH", eth)
    moves = [T(1, "0xsrc", "0xa", 100.0), T(2, "0xa", "0xmix", 60.0), T(3, "0xa", "0xeuler", 30.0)]
    load_case(conn, moves, [], {"0xmix": "mixer", "0xeuler": "victim"}, {}, seeds=["0xa"], eth_usd=1000.0,
              complete=["0xa"])
    r = run(conn)
    assert r.stolen_usd == pytest.approx(100_000)          # 10 held + 60 into the mixer + 30 given back, at $1,000
