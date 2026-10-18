import asyncio
import itertools

import httpx

from gt import db, watch
from gt.pipeline import load_scenario, run
from gt.schema import Alert, Transfer
from gt.simulator import simulate
from test_live import fake_rpc


def _case():
    conn = db.connect("mongomock://")
    load_scenario(conn, simulate(seed=7), name="sim")
    run(conn)
    return conn


def _go(conn, check, collect=None, case="sim", ticks=40, **kw):
    status = watch.new_status("simulated", 3)
    clock = itertools.count(0, 1).__next__            # every clock() call is one second later
    asyncio.run(watch.watch_loop(conn, check, lambda: run(conn), collect, status, case, interval_s=0,
                                 max_s=ticks, clock=clock, **kw))
    return status


def test_new_transfers_rerun_the_engine_and_raise_alerts():
    conn = _case()
    before = {a.alert_id for a in db.select(conn, Alert)}
    status = _go(conn, watch.simulated_source(conn, seed=1))
    assert status["checks"] >= 3 and status["new_transfers"] >= 3 and status["reruns"] == status["new_transfers"]
    assert not status["on"] and status["recent"][0]["to_label"].startswith("exchange:")
    new = {a.alert_id for a in db.select(conn, Alert)} - before
    assert len([a for a in new if a.startswith("live:")]) == status["new_transfers"]   # every new deposit: its own alert


def test_posts_are_collected_on_a_timer():
    conn = _case()
    calls = []

    async def collect():
        calls.append(1)
        return 2
    status = _go(conn, lambda: [], collect, ticks=40, posts_every_s=15)
    assert len(calls) >= 2 and status["posts_found"] >= 4 and status["reruns"] == status["posts_found"] // 2
    assert status["checks"] >= len(calls)                  # collecting never held up the chain checks


def test_stops_when_another_case_is_loaded():
    conn = _case()
    status = _go(conn, lambda: [], case="a different case")
    assert status["checks"] == 0 and not status["on"]


def test_chain_source_starts_at_the_head_and_never_scans_from_genesis():
    ok = fake_rpc(head="0x64")
    n = [0]

    def flaky(method, params):
        n[0] += 1
        if n[0] == 1:
            raise httpx.ConnectError("down")
        return ok(method, params)
    check = watch.chain_source({"0xaa"}, flaky)
    assert check() == []                                   # head unknown: nothing, and no scan from block 0
    check()
    starts = [int(p[0]["fromBlock"], 16) for m, p in ok.calls if m == "alchemy_getAssetTransfers"]
    assert starts and min(starts) >= 99


def test_chain_source_returns_new_real_transfers():
    check = watch.chain_source({"0xaa"}, fake_rpc(head="0xc"))
    out = check()
    assert [t.tx_hash for t in out] == ["0xhash"] and isinstance(out[0], Transfer)
    assert check() == []                                   # no new block, nothing new
