"""Live mode: poll Alchemy for new transfers touching watched wallets, plus a lite mempool count."""
import asyncio
import logging

import httpx

from gt import db
from gt.chain.normalize import norm_addr, to_utc
from gt.config import env
from gt.schema import Transfer

log = logging.getLogger(__name__)


def _rpc(method: str, params: list):
    key = env("ALCHEMY_API_KEY")
    if not key:
        raise httpx.HTTPError("ALCHEMY_API_KEY not set")
    r = httpx.post(f"https://eth-mainnet.g.alchemy.com/v2/{key}",
                   json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=20)
    body = r.json()
    if "error" in body:
        raise httpx.HTTPError(str(body["error"]))
    return body["result"]


def _to_transfer(a: dict) -> Transfer:
    tx_hash = norm_addr(a["hash"]) if a.get("category") in ("external", "internal") else norm_addr(a["uniqueId"])
    return Transfer(tx_hash, "eth", to_utc(a["metadata"]["blockTimestamp"]), norm_addr(a["from"]), norm_addr(a["to"]),
                    a.get("asset") or "TOKEN", float(a.get("value") or 0.0))


def poll_once(watch: set[str], last_block: int, rpc=None) -> tuple[list[Transfer], int]:
    rpc = rpc or _rpc
    try:
        head = int(rpc("eth_blockNumber", []), 16)
        if head <= last_block:
            return [], last_block
        seen: dict[str, Transfer] = {}
        for addr in sorted(watch):
            for side in ("fromAddress", "toAddress"):
                res = rpc("alchemy_getAssetTransfers", [{
                    "fromBlock": hex(last_block + 1), "toBlock": hex(head), side: addr,
                    "category": ["external", "erc20"], "withMetadata": True, "maxCount": "0x3e8"}])
                for a in res.get("transfers", []):
                    t = _to_transfer(a)
                    seen.setdefault(t.tx_hash, t)
        return list(seen.values()), head
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as e:
        log.warning("live poll failed: %r", e)
        return [], last_block


def pending_count(watch: set[str], rpc=None) -> int:
    try:
        block = (rpc or _rpc)("eth_getBlockByNumber", ["pending", True])
        return sum(1 for tx in block.get("transactions", [])
                   if norm_addr(tx.get("from")) in watch or norm_addr(tx.get("to")) in watch)
    except (httpx.HTTPError, KeyError, ValueError, TypeError, AttributeError) as e:
        log.warning("pending scan failed: %r", e)
        return 0


async def live_loop(conn, watch: set[str], interval_s: int = 12, queue: asyncio.Queue | None = None,
                    rpc=None, max_iters: int | None = None, start_block: int | None = None) -> None:
    """Forever (or max_iters times): poll → store → push to the SSE queue."""
    last = start_block
    i = 0
    while max_iters is None or i < max_iters:
        if last is None:  # start at the current head; never fall back to block 0 (would scan the whole chain)
            _, head = await asyncio.to_thread(poll_once, set(), 0, rpc)  # empty watch = just read the head
            last = head - 1 if head else None
        new, last = ([], last) if last is None else await asyncio.to_thread(poll_once, watch, last, rpc)
        if new:
            db.insert(conn, new)
            for t in new:
                if queue is not None:
                    queue.put_nowait(t)
        i += 1
        await asyncio.sleep(interval_s)
