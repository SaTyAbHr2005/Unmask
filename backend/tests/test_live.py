import asyncio

import httpx

from gt import db
from gt.chain import live
from gt.schema import Transfer

ALCH = {"blockNum": "0xb", "hash": "0xHASH", "from": "0xAA", "to": "0xBB", "value": 1.5, "asset": "ETH",
        "category": "external", "uniqueId": "0xHASH:external",
        "metadata": {"blockTimestamp": "2026-10-17T02:14:00.000Z"}}


def fake_rpc(transfers=(ALCH,), head="0xc", pending=()):
    calls = []

    def rpc(method, params):
        calls.append((method, params))
        if method == "eth_blockNumber":
            return head
        if method == "alchemy_getAssetTransfers":
            return {"transfers": list(transfers)}
        if method == "eth_getBlockByNumber":
            return {"transactions": list(pending)}
        raise AssertionError(method)
    rpc.calls = calls
    return rpc


def test_poll_once_normalizes_and_dedupes():
    rpc = fake_rpc()
    out, last = live.poll_once({"0xaa"}, 10, rpc)
    assert last == 12
    assert out == [Transfer("0xhash", "eth", 1792203240, "0xaa", "0xbb", "ETH", 1.5)]  # seen as from AND to → once
    q = [p[0] for m, p in rpc.calls if m == "alchemy_getAssetTransfers"]
    assert q[0]["fromBlock"] == "0xb" and q[0]["toBlock"] == "0xc"


def test_poll_once_token_transfer_uses_unique_id():
    tok = {**ALCH, "asset": "USDT", "category": "erc20", "value": None, "uniqueId": "0xHASH:log:0x5"}
    out, _ = live.poll_once({"0xaa"}, 10, fake_rpc([tok]))
    assert (out[0].tx_hash, out[0].asset, out[0].amount) == ("0xhash:log:0x5", "USDT", 0.0)


def test_poll_once_no_new_blocks():
    assert live.poll_once({"0xaa"}, 12, fake_rpc(head="0xc")) == ([], 12)


def test_poll_once_timeout_returns_unchanged():
    def rpc(method, params):
        raise httpx.TimeoutException("slow")
    assert live.poll_once({"0xa"}, 10, rpc) == ([], 10)


def test_pending_count():
    rpc = fake_rpc(pending=[{"from": "0xAA", "to": "0x1"}, {"from": "0x2", "to": "0xaa"}, {"from": "0x3", "to": None}])
    assert live.pending_count({"0xaa"}, rpc) == 2

    def broken(method, params):
        raise httpx.ConnectError("down")
    assert live.pending_count({"0xaa"}, broken) == 0


def test_live_loop_stores_and_queues():
    conn = db.connect("mongomock://")
    q: asyncio.Queue = asyncio.Queue()
    asyncio.run(live.live_loop(conn, {"0xaa"}, interval_s=0, queue=q, rpc=fake_rpc(head="0xc"), max_iters=1,
                               start_block=10))
    assert db.select(conn, Transfer)[0].tx_hash == "0xhash"
    assert q.get_nowait().tx_hash == "0xhash"


def test_default_rpc_without_key_is_safe(monkeypatch):
    monkeypatch.setattr(live, "env", lambda k: None)
    assert live.poll_once({"0xa"}, 10) == ([], 10)


def test_live_loop_never_scans_from_genesis_when_head_read_fails():
    conn = db.connect("mongomock://")
    ok = fake_rpc(head="0x64")
    state = {"n": 0}

    def flaky(method, params):
        state["n"] += 1
        if state["n"] == 1:
            raise httpx.ConnectError("down")
        return ok(method, params)
    asyncio.run(live.live_loop(conn, {"0xaa"}, interval_s=0, rpc=flaky, max_iters=2))
    starts = [int(p[0]["fromBlock"], 16) for m, p in ok.calls if m == "alchemy_getAssetTransfers"]
    assert starts and min(starts) >= 99
