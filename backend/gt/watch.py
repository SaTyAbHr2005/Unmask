"""Watch mode: keep a loaded case live. New transfers → stored → the engine reruns → new alerts wait for approval;
public posts are re-collected on a timer. The source is the real chain (Alchemy) or, for a simulated case,
the simulated attacker carrying on with the cash-out."""
import asyncio
import dataclasses
import random
import time
from typing import Awaitable, Callable

from gt import db
from gt.chain.labels import load_labels
from gt.chain.live import poll_once
from gt.chain.normalize import classify
from gt.config import usd
from gt.defense.alerts import queue as queue_alerts
from gt.schema import Alert, Transfer

INTERVAL_S = 12            # one Ethereum block
POSTS_EVERY_S = 600
MAX_WATCH_S = 30 * 60      # ponytail: stops by itself so a forgotten tab can't burn the free Alchemy quota; a scheduler if it must run for days
MAX_WALLETS = 10           # each watched wallet costs 2 Alchemy calls per check


def chain_source(watch: set[str], rpc=None) -> Callable[[], list[Transfer]]:
    """Real transfers from the watched wallets since the previous check (starts at the current block)."""
    last: list[int | None] = [None]

    def check() -> list[Transfer]:
        if last[0] is None:
            _, head = poll_once(set(), 0, rpc)          # empty watch = just read the head
            last[0] = head - 1 if head else None
            if last[0] is None:
                return []
        new, last[0] = poll_once(watch, last[0], rpc)
        return new
    return check


def simulated_source(conn, seed: int = 0) -> Callable[[], list[Transfer]]:
    """A simulated case keeps going: now and then, one attacker wallet that still holds money sends 10–25% of it
    to the exchange Unmask predicted (or the one already used). Chain time moves on a minute per check."""
    rng, n = random.Random(seed), [0]

    def check() -> list[Transfer]:
        res = db.get_meta(conn, "results") or {}
        exits = sorted(res.get("exits", []), key=lambda e: (e["arrived"], -e["share"]))   # predicted first
        held = [h for h in res.get("holdings", []) if not h["freezer"].startswith("exchange:") and h["amount"] > 0]
        if not exits or not held or rng.random() > 0.35:      # about one move every 30–40 s at one check per block
            return []
        h = rng.choice(held[:5])
        n[0] += 1
        now = max((t["ts"] for t in conn.transfer.find({}, {"ts": 1}).sort("ts", -1).limit(1)), default=0)
        return [Transfer(f"0xlive{n[0]:04d}{rng.getrandbits(32):08x}", "eth", now + 60, h["address"], exits[0]["address"],
                         h["asset"], round(h["amount"] * rng.uniform(0.10, 0.25), 4))]
    return check


def new_status(source: str, watching: int) -> dict:
    now = int(time.time())
    return {"on": True, "source": source, "watching": watching, "started_ts": now, "stops_ts": now + MAX_WATCH_S,
            "checks": 0, "new_transfers": 0, "reruns": 0, "last_check_ts": None, "last_posts_ts": None,
            "posts_found": 0, "recent": [], "error": None}


def _arrivals(new: list[Transfer], labels: dict[str, str]) -> list[Alert]:
    """One alert per new move into an exchange (freeze it now) or a mixer (the trail is about to go cold)."""
    out = []
    for t in new:
        hub = labels.get(t.to_addr, "")
        if not (hub.startswith("exchange:") or hub == "mixer"):
            continue
        money = f"{t.amount:,.4g} {t.asset}" + (f" (${v:,.0f})" if (v := usd(t.asset, t.amount)) else "")
        if hub == "mixer":
            msg = f"Just now: {money} moved from attacker wallet {t.from_addr[:10]}… into a mixer. Record the deposit before the trail goes cold."
        else:
            msg = (f"Just now: {money} moved from attacker wallet {t.from_addr[:10]}… to {hub[9:]} ({t.to_addr[:10]}…). "
                   f"Ask their compliance team to freeze it.")
        out.append(Alert(f"live:{t.tx_hash}", "exit", hub.removeprefix("exchange:"), msg))
    return out


async def watch_loop(conn, check: Callable[[], list[Transfer]], rerun: Callable[[], object],
                     collect: Callable[[], Awaitable[int]] | None, status: dict, case: str,
                     interval_s: float = INTERVAL_S, posts_every_s: float = POSTS_EVERY_S,
                     max_s: float = MAX_WATCH_S, queue: asyncio.Queue | None = None, clock=time.time) -> None:
    start, next_posts, posts = clock(), clock(), None
    try:
        while clock() - start < max_s:
            began = clock()
            if (db.get_meta(conn, "scenario") or {}).get("name") != case:   # another case was loaded: stop
                break
            changed = False
            new = await asyncio.to_thread(check)
            if new:
                labels = {**load_labels(), **(db.get_meta(conn, "scenario") or {}).get("labels", {})}
                new = [dataclasses.replace(t, kind=classify(t, labels)) for t in new]
                db.insert(conn, new)
                queue_alerts(conn, _arrivals(new, labels))
                status["new_transfers"] += len(new)
                status["recent"] = ([{"ts": t.ts, "from": t.from_addr, "to": t.to_addr, "asset": t.asset,
                                      "amount": t.amount, "to_label": labels.get(t.to_addr, "")} for t in new]
                                    + status["recent"])[:8]
                for t in new:
                    if queue is not None:
                        queue.put_nowait(t)
                changed = True
            # posts are collected in the background (news feeds and GitHub take ~25 s) so chain checks never wait
            if posts is not None and posts.done():
                status["posts_found"] += posts.result()
                status["last_posts_ts"] = int(clock())
                posts, next_posts, changed = None, clock() + posts_every_s, True
            if collect and posts is None and clock() >= next_posts:
                posts = asyncio.create_task(collect())
            if changed:
                await asyncio.to_thread(rerun)
                status["reruns"] += 1
            status["checks"] += 1
            status["last_check_ts"] = int(clock())
            await asyncio.sleep(max(0.0, interval_s - (clock() - began)))   # one check per block, however long it took
    except Exception as e:   # the loop runs unattended: record why it stopped instead of dying silently
        status["error"] = repr(e)
        raise
    finally:
        if posts is not None:
            posts.cancel()
        status["on"] = False
