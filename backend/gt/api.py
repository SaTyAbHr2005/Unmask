"""HTTP API for the dashboard. Run: py -3.11 -m uvicorn gt.api:app --reload --port 8000 (from backend/)."""
import asyncio
import dataclasses
import json
import re
import time
from collections import defaultdict
from datetime import date
from typing import Annotated

import mongomock
import numpy as np
from fastapi import APIRouter, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, StringConstraints

from gt import db
from gt.analytics.behavior import infer_utc_offset
from gt.analytics.features import activity_matrix, wallet_features
from gt.chain.etherscan import CHAINS, get_code, trace
from gt.chain.labels import load_labels
from gt.chain.live import pending_count
from gt.chain.normalize import norm_addr
from gt.chain.prices import eth_usd_on
from gt.config import DATA_DIR, GITHUB_QUERIES, RSS_FEEDS, TELEGRAM_CHANNELS, env, eth_usd, set_eth_usd, usd
from gt.defense import alerts
from gt.fusion.evidence import audit, head, verify_audit
from gt.fusion import score
from gt.osint.collectors import collect_github, collect_rss, collect_telegram
from gt.osint.extract import extract
from gt.osint.style import resolve_identities
from gt.pipeline import load_case, load_results, load_scenario, run, third_party_contracts
from gt.schema import Alert, Link, OsintPost, Transfer
from gt.simulator import simulate, variant
from gt.watch import MAX_WALLETS, chain_source, new_status, simulated_source, watch_loop

app = FastAPI(title="Unmask API", description="Quantitative OSINT + blockchain engine")
app.add_middleware(CORSMiddleware, allow_methods=["*"], allow_headers=["*"],
                   allow_origins=[o.strip() for o in (env("FRONTEND_ORIGINS") or "http://localhost:5173").split(",")])
router = APIRouter(prefix="/api")
STATE: dict = {"conn": None, "live_task": None, "watch": {"on": False}}
LIVE_QUEUE: asyncio.Queue = asyncio.Queue()
CHAIN_IDS = {v: k for k, v in CHAINS.items()}
Analyst = Annotated[str, Header(alias="X-Analyst")]   # ponytail: self-declared name, no auth — add login before real use
Address = Annotated[str, StringConstraints(pattern=r"^0x[0-9a-fA-F]{40}$")]


def conn():
    if STATE["conn"] is None:
        STATE["conn"] = db.connect()
        set_eth_usd((db.get_meta(STATE["conn"], "scenario") or {}).get("eth_usd"))   # after a restart
    return STATE["conn"]


def _results() -> dict:
    return load_results(conn()) or {}


def _labels() -> dict[str, str]:
    return {**load_labels(), **(db.get_meta(conn(), "scenario") or {}).get("labels", {})}


def _members(cluster: int = 0) -> set[str]:
    return {w for w, k in _results().get("clusters", {}).items() if k == cluster}


def _short(a: str) -> str:
    return f"{a[:6]}…{a[-4:]}" if len(a) > 12 else a


def _value(t: Transfer) -> float:
    return usd(t.asset, t.amount) or 0.0


# ── case loading & running ────────────────────────────────────────────────────────────────────────────

@router.get("/health")
def health():
    return {"ok": True, "db": "mongomock" if isinstance(conn().client, mongomock.MongoClient) else "mongo"}


@router.post("/simulate")
def simulate_case(seed: Annotated[int, Query(ge=0, le=1_000_000)] = 7):
    s = simulate(seed=seed, **variant(seed))   # every number but 7 (the story's) is a different attacker
    load_scenario(conn(), s, name=f"Simulated attack (seed {seed})")
    return {"transfers": len(s.transfers), "posts": len(s.posts)}


@router.get("/replays")
def replay_list():
    """Real past hacks available to load (data/replays/*.json)."""
    out = []
    for p in sorted((DATA_DIR / "replays").glob("*.json")):
        cfg = json.loads(p.read_text())
        out.append({"id": p.stem, "name": cfg.get("name", p.stem), "source": cfg.get("source", "")})
    return out


@router.post("/replay/{name}")
def replay_case(name: str):
    if not re.fullmatch(r"[\w-]{1,64}", name):
        raise HTTPException(400, "replay names may only contain letters, digits, - and _")
    path = DATA_DIR / "replays" / f"{name}.json"
    if not path.exists():
        raise HTTPException(404, f"no replay called {name}")
    return _load_trace(json.loads(path.read_text()), name)


def _load_trace(cfg: dict, name: str) -> dict:
    """Trace real money from cfg's seed addresses and make it the loaded case (shared by replays and investigations)."""
    if not env("ETHERSCAN_API_KEY"):
        raise HTTPException(400, "Tracing real transactions needs ETHERSCAN_API_KEY in backend/.env")
    transfers, codes, complete = trace(cfg)
    if not transfers:   # keep whatever case is loaded rather than replacing it with nothing
        raise HTTPException(404, "No transactions with a known price for these addresses in that window. "
                                 "Check the address, the chain and the dates.")
    seeds = {norm_addr(a) for a in cfg.get("seed_addresses", [])}
    chain_of = {a: CHAIN_IDS.get(t.chain, 1) for t in transfers for a in (t.from_addr, t.to_addr)}
    labels = {**load_labels(), **{norm_addr(a): "victim" for a in cfg.get("victims", [])}}   # lets theft be measured
    hubs = third_party_contracts(transfers, seeds, labels, lambda a: len(get_code(a, chain_of.get(a, 1))) > 2)
    price = cfg.get("eth_usd") or (eth_usd_on(date.fromisoformat(cfg["window"][0])) if cfg.get("window") else None)
    load_case(conn(), transfers, [], {**labels, **hubs}, codes, None, cfg.get("name", name), sorted(seeds), price,
              sorted(complete))
    return {"transfers": len(transfers), "posts": 0, "third_party_contracts": len(hubs), "eth_usd": eth_usd()}


class Investigate(BaseModel):
    addresses: Annotated[list[Address], Field(min_length=1, max_length=5)]
    start: date
    end: date
    chain: int = 1
    hops: Annotated[int, Field(ge=0, le=3)] = 2


MAX_WINDOW_DAYS = 120   # each extra day can pull in more wallets: keep a live trace to a few minutes


@router.post("/investigate")
def investigate(body: Investigate):
    """Trace any address the analyst (or a judge) names, the same way as a stored replay."""
    if body.chain not in CHAINS:
        raise HTTPException(422, f"chain must be one of {sorted(CHAINS)}")
    if not 0 < (body.end - body.start).days <= MAX_WINDOW_DAYS:
        raise HTTPException(422, f"the end date must be after the start date, at most {MAX_WINDOW_DAYS} days later")
    first = norm_addr(body.addresses[0])
    more = f" + {len(body.addresses) - 1} more" if len(body.addresses) > 1 else ""
    chain = {1: "Ethereum", 42161: "Arbitrum", 137: "Polygon"}.get(body.chain, CHAINS[body.chain])
    cfg = {"name": f"Investigation: {_short(first)}{more} on {chain}, {body.start} to {body.end}",
           "seed_addresses": body.addresses, "chainids": [body.chain],
           "window": [body.start.isoformat(), body.end.isoformat()], "hops": body.hops}
    return _load_trace(cfg, "investigation")


@router.post("/run")
def run_case():
    r = run(conn())
    return {"metrics": r.metrics, "links": len(r.links),
            "alerts": conn().alert.count_documents({"status": "pending"})}


# ── views for the dashboard ─────────────────────────────────────────────────────────────────────────

def _kind(addr: str, cluster: int | None, labels: dict[str, str], decoys: set[str]) -> str:
    l = labels.get(addr, "")
    if l:
        return "exchange" if l.startswith("exchange:") else l
    if addr in decoys:
        return "decoy"
    return "attacker" if cluster == 0 else "wallet"


@router.get("/graph")
def graph(cluster: int = 0, limit: Annotated[int, Query(ge=1, le=5000)] = 600):
    res = _results()
    if not res:
        return {"nodes": [], "edges": []}
    clusters, labels, decoys = res["clusters"], _labels(), set(res["decoys"])
    members = _members(cluster)
    txs = db.select(conn(), Transfer)
    keep = set(members)
    for t in txs:   # show the hubs and decoys the cluster touches
        for a, b in ((t.from_addr, t.to_addr), (t.to_addr, t.from_addr)):
            if a in members and (b in labels or b in decoys):
                keep.add(b)
    volume: dict[str, float] = defaultdict(float)
    for t in txs:
        if t.from_addr in keep and t.to_addr in keep:
            volume[t.from_addr] += _value(t)
            volume[t.to_addr] += _value(t)
    nodes = sorted(keep, key=lambda a: -volume[a])[:limit]
    shown = set(nodes)
    by_hash = {t.tx_hash: t for t in txs}
    flows = [(t.from_addr, t.to_addr, t.kind, _value(t), t.ts) for t in txs]
    flows += [(by_hash[o].from_addr, by_hash[i].to_addr, "bridge_link", _value(by_hash[i]), by_hash[i].ts)
              for o, i, _ in res["bridges"] if o in by_hash and i in by_hash]
    edges: dict[tuple, dict] = {}
    for a, b, kind, v, ts in flows:
        if a in shown and b in shown and a != b:
            e = edges.setdefault((a, b, kind), {"source": a, "target": b, "kind": kind, "usd": 0.0, "ts": ts})
            e["usd"] += v
            e["ts"] = min(e["ts"], ts)
    return {"nodes": [{"id": a, "label": labels.get(a, "").removeprefix("exchange:") or _short(a),
                       "cluster": clusters.get(a), "kind": _kind(a, clusters.get(a), labels, decoys),
                       "usd": volume[a], "bot_score": res.get("bot_scores", {}).get(a)} for a in nodes],
            "edges": list(edges.values())}


def _identity_posts() -> dict[str, list[OsintPost]]:
    posts = db.select(conn(), OsintPost)
    ids = resolve_identities(posts)
    out: dict[str, list[OsintPost]] = {}
    for p in posts:
        out.setdefault(ids[f"{p.source}:{p.author}"], []).append(p)
    return out


@router.get("/timeline")
def timeline(identity: str | None = None):
    res = _results()
    identity = identity or (res.get("links") or [{}])[0].get("identity")
    members = _members(0)
    events = [{"ts": t.ts, "type": "tx", "who": t.from_addr, "usd": _value(t), "kind": t.kind, "cluster": 0}
              for t in db.select(conn(), Transfer) if t.from_addr in members]
    events += [{"ts": p.ts, "type": "post", "who": f"{p.source}:{p.author}", "text": p.text[:280], "url": p.url}
               for p in _identity_posts().get(identity, [])]
    return sorted(events, key=lambda e: e["ts"])


@router.get("/heatmap/{key:path}")
def heatmap(key: str):
    if key.startswith("cluster:") and key[8:].lstrip("-").isdigit():
        members = _members(int(key[8:]))
        ts = [t.ts for t in db.select(conn(), Transfer) if t.from_addr in members]
    elif key.startswith("identity:"):
        ts = [p.ts for p in _identity_posts().get(key[9:], [])]
    else:
        raise HTTPException(400, "key must be cluster:<n> or identity:<id>")
    if not ts:
        raise HTTPException(404, f"no activity for {key}")
    off = infer_utc_offset(ts)
    return {"hours": np.bincount((np.asarray(ts) // 3600) % 24, minlength=24).tolist(),
            "utc_offset": off[0] if off else None, "confidence": off[1] if off else None}


@router.get("/sankey")
def sankey():
    """Stolen funds → laundering route → where it is now.
    ponytail: the second layer splits each route in proportion to the final buckets (no per-coin tracking)."""
    res = _results()
    if not res:
        return {"nodes": [], "links": []}
    members, labels = _members(0), _labels()
    routes: dict[str, float] = defaultdict(float)
    for t in db.select(conn(), Transfer):
        if t.from_addr in members:
            if t.kind == "mixer_in":
                routes["Mixer"] += _value(t)
            elif t.kind == "bridge_out":
                routes["Bridge"] += _value(t)
            elif t.kind == "swap" and labels.get(t.to_addr) == "dex":
                routes["DEX swap"] += _value(t)
    routes["Direct"] = max(res["stolen_usd"] - sum(routes.values()), 0.0)
    routes = {r: v for r, v in routes.items() if v > 0.001 * res["stolen_usd"]}   # no empty or rounding-crumb routes
    finals: dict[str, float] = defaultdict(float)
    if (back := sum(_value(t) for t in db.select(conn(), Transfer)
                    if t.from_addr in members and labels.get(t.to_addr) == "victim")):
        finals["Returned to the victim"] = back
    for h in res["holdings"]:
        name = h["freezer"].removeprefix("exchange:") if h["freezer"].startswith("exchange:") else \
            "Held · freezable" if h["freezable"] else "Held · not freezable"
        finals[name] += h["usd"]
    names = ["Stolen funds", *routes, *finals]
    idx = {n: i for i, n in enumerate(names)}
    total_final = sum(finals.values()) or 1.0
    links = [{"source": 0, "target": idx[r], "value": round(v)} for r, v in routes.items() if v > 0]
    links += [{"source": idx[r], "target": idx[f], "value": round(v * fv / total_final)}
              for r, v in routes.items() if v > 0 for f, fv in finals.items() if fv > 0]
    return {"nodes": [{"name": n} for n in names], "links": links}


@router.get("/money-now")
def money_now():
    res = _results()
    if not res:
        return {"total_usd": 0, "frozen_possible_usd": 0, "at_exchanges_usd": 0, "in_mixers_usd": 0,
                "unspent_usd": 0, "returned_usd": 0, "exits": [], "timing": {}}
    members, hs, labels = _members(0), res["holdings"], _labels()
    txs = db.select(conn(), Transfer)
    mixed = sum((_value(t) if t.from_addr in members and t.kind == "mixer_in" else 0)
                - (_value(t) if t.to_addr in members and t.kind == "mixer_out" else 0) for t in txs)
    returned = sum(_value(t) for t in txs if t.from_addr in members and labels.get(t.to_addr) == "victim")
    return {"total_usd": res["stolen_usd"],
            "frozen_possible_usd": sum(h["usd"] for h in hs if h["freezable"]),
            "at_exchanges_usd": sum(h["usd"] for h in hs if h["freezer"].startswith("exchange:")),
            "in_mixers_usd": max(mixed, 0.0),
            "unspent_usd": sum(h["usd"] for h in hs if not h["freezer"].startswith("exchange:")),
            "returned_usd": returned,
            "exits": res["exits"], "timing": res.get("timing", {}), "eth_usd": eth_usd()}


# ── analyst decisions ───────────────────────────────────────────────────────────────────────────────

POLISH_TOP = 3   # AI wording costs one call per link: only the top few


def _link_view(l: Link, polish: bool = False) -> dict:
    return {**dataclasses.asdict(l), "label": score.label(l.score, l.status), "explanation": score.explain(l, polish)}


@router.get("/links")
def links(polish: bool = False):
    ls = sorted(db.select(conn(), Link), key=lambda l: -l.score)
    return [_link_view(l, polish and i < POLISH_TOP) for i, l in enumerate(ls)]


@router.post("/links/{link_id}/{action}")
def decide_link(link_id: str, action: str, actor: Analyst = "analyst"):
    if action not in ("confirm", "reject"):
        raise HTTPException(404, "action must be confirm or reject")
    found = db.select(conn(), Link, {"link_id": link_id})
    if not found:
        raise HTTPException(404, f"no link {link_id}")
    l = dataclasses.replace(found[0], status=f"{action}ed")
    db.insert(conn(), [l])
    audit(conn(), actor, f"{action}_link", link_id)
    return _link_view(l)


@router.get("/alerts")
def list_alerts():
    return sorted((dataclasses.asdict(a) for a in db.select(conn(), Alert)), key=lambda a: (a["created_ts"], a["alert_id"]))


def _alert_action(alert_id: str, fn, actor: str) -> dict:
    if not db.select(conn(), Alert, {"alert_id": alert_id}):
        raise HTTPException(404, f"no alert {alert_id}")
    try:
        return dataclasses.asdict(fn(conn(), alert_id, actor))
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@router.post("/alerts/{alert_id}/approve")
def approve_alert(alert_id: str, actor: Analyst = "analyst"):
    return _alert_action(alert_id, alerts.approve, actor)


@router.post("/alerts/{alert_id}/dismiss")
def dismiss_alert(alert_id: str, actor: Analyst = "analyst"):
    return _alert_action(alert_id, alerts.dismiss, actor)


# ── report ──────────────────────────────────────────────────────────────────────────────────────────

def freeze_request(to: str, holdings: list[dict], links: list[Link], case: str = "", stolen_usd: float = 0) -> str:
    """Plain-text freeze request for one recipient (issuer or exchange). Always marked as suspected."""
    lines = [f"To: {to} — compliance / security team",
             f"Subject: Urgent freeze request — funds traced from {case or 'a theft under investigation'}", "",
             f"We are investigating the theft of about ${stolen_usd:,.0f}. These balances under your control "
             f"are traced to the attacker's wallet cluster:"]
    lines += [f"  - {h['address']}: {h['amount']:,.4f} {h['asset']} (~${h['usd']:,.0f})" for h in holdings]
    top = [l for l in links if l.status != "rejected"][:1]
    if top:
        lines += ["", f"Attribution (suspected — pending law-enforcement confirmation): {top[0].identity}, "
                      f"confidence {top[0].score:.0%}.", "Evidence hashes: " + ", ".join(h[:16] for h in top[0].evidence[:5])]
    else:
        lines += ["", "Attribution: none yet (suspected activity — pending law-enforcement confirmation)."]
    lines += ["", "Please freeze these balances/accounts and preserve all records (KYC, IP logs) for law enforcement."]
    return "\n".join(lines)


def _report(polish: bool = False) -> dict:
    res, c = _results(), conn()
    ls = sorted(db.select(c, Link), key=lambda l: -l.score)
    by_freezer: dict[str, list[dict]] = defaultdict(list)
    for h in res.get("holdings", []):
        if h["freezable"]:
            by_freezer[h["freezer"].removeprefix("exchange:")].append(h)
    case, stolen = res.get("case", ""), res.get("stolen_usd", 0)
    return {"case": case, "generated_ts": int(time.time()), "stolen_usd": stolen, "metrics": res.get("metrics"),
            "links": [_link_view(l, polish and i < POLISH_TOP) for i, l in enumerate(ls[:5])],
            "exits": res.get("exits", []), "holdings": res.get("holdings", []), "timing": res.get("timing", {}),
            "deposits": [d for d in res.get("deposits", []) if d["n_pieces"] >= 2],
            "freeze_requests": [{"to": to, "text": freeze_request(to, hs, ls, case, stolen)} for to, hs in by_freezer.items()],
            "audit_ok": verify_audit(c), "audit_head": head(c), "audit_entries": c.auditentry.count_documents({}),
            "evidence_count": c.evidence.count_documents({})}


@router.get("/report")
def report(polish: bool = False):
    return _report(polish)


@router.post("/report/export")
def export_report(actor: Analyst = "analyst"):
    audit(conn(), actor, "export_report", _results().get("case", ""))
    return _report()


# ── OSINT collection, wallet detail, matrix, mempool ────────────────────────────────────────────────

class OsintCollect(BaseModel):
    rss: bool = True
    github_queries: list[str] | None = None
    telegram_channels: list[str] | None = None
    search_case_addresses: bool = True


@router.post("/osint/collect")
async def osint_collect(body: OsintCollect):
    """Pull public text into the current case (then POST /run to rescore). Never fails on a dead source."""
    return await _collect_posts(body)


async def _collect_posts(body: OsintCollect) -> dict:
    queries = list(body.github_queries or GITHUB_QUERIES)
    if body.search_case_addresses:
        queries += _results().get("seeds", [])[:3]   # does anyone mention the attacker's wallet?
    rss = await asyncio.to_thread(collect_rss, RSS_FEEDS) if body.rss else []
    gh = await asyncio.to_thread(collect_github, queries)
    tg = await collect_telegram(body.telegram_channels or TELEGRAM_CHANNELS)
    posts = rss + gh + tg
    ents = [e for p in posts for e in extract(p)]
    db.insert(conn(), posts)
    db.insert(conn(), ents)
    return {"rss": len(rss), "github": len(gh), "telegram": len(tg), "entities": len(ents),
            "total_posts": conn().osintpost.count_documents({}), "next": "POST /api/run to rescore"}


class Reveal(BaseModel):
    reason: Annotated[str, StringConstraints(min_length=3, max_length=200)]


@router.post("/privacy/reveal")
def reveal_personal_details(body: Reveal, actor: Analyst = "analyst"):
    """Emails/IPs found in OSINT are masked in the UI; revealing them is a recorded decision with a reason."""
    audit(conn(), actor, "reveal_pii", body.reason)
    return {"revealed": True}


ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")


@router.get("/wallet/{addr}")
def wallet(addr: str):
    if not ADDRESS.match(addr):
        raise HTTPException(400, "not an address")
    addr = norm_addr(addr)
    txs = [t for t in db.select(conn(), Transfer) if addr in (t.from_addr, t.to_addr)]
    if not txs:
        raise HTTPException(404, f"no transfers for {addr}")
    res, labels = _results(), _labels()
    cluster = res.get("clusters", {}).get(addr)
    feats = res.get("features", {}).get(addr)
    if feats is None:
        df = wallet_features([t for t in txs if t.from_addr == addr])
        feats = {k: (None if v != v else float(v)) for k, v in df.iloc[0].items()} if not df.empty else {}
    off = infer_utc_offset([t.ts for t in txs if t.from_addr == addr])
    recent = sorted(txs, key=lambda t: -t.ts)[:25]
    return {"address": addr, "label": labels.get(addr, ""), "cluster": cluster,
            "kind": _kind(addr, cluster, labels, set(res.get("decoys", []))),
            "features": feats, "bot_score": res.get("bot_scores", {}).get(addr),
            "utc_offset": off[0] if off else None,
            "holdings": [h for h in res.get("holdings", []) if h["address"] == addr],
            "deposits": [d for d in res.get("deposits", []) if d["wallet"] == addr],
            "transfers": [{**dataclasses.asdict(t), "usd": _value(t)} for t in recent]}


@router.get("/matrix")
def matrix(cluster: int = 0, bucket: Annotated[int, Query(ge=60, le=86400)] = 3600,
           top: Annotated[int, Query(ge=1, le=200)] = 40):
    """The ledger as a matrix: the cluster's busiest wallets x time buckets, tx counts."""
    members = _members(cluster)
    m = activity_matrix([t for t in db.select(conn(), Transfer) if t.from_addr in members], bucket)
    if m.empty:
        return {"wallets": [], "buckets": [], "counts": []}
    m = m.loc[m.sum(axis=1).sort_values(ascending=False).index[:top]]
    # keep quiet hours as empty columns, so the time axis stays honest (capped at 200 columns)
    cols = range(int(m.columns.min()), int(m.columns.max()) + bucket, bucket)
    m = m.reindex(columns=list(cols)[:200], fill_value=0)
    return {"wallets": m.index.tolist(), "buckets": [int(b) for b in m.columns],
            "counts": m.astype(int).values.tolist()}


@router.get("/mempool")
async def mempool():
    """Pending (not yet confirmed) transactions touching the attacker cluster right now."""
    watch = _members(0)
    if not env("ALCHEMY_API_KEY"):
        return {"available": False, "pending": 0, "watching": len(watch)}
    return {"available": True, "pending": await asyncio.to_thread(pending_count, watch), "watching": len(watch)}


# ── live mode ───────────────────────────────────────────────────────────────────────────────────────


class LiveStart(BaseModel):
    watch: list[Address] | None = None     # default: the attacker cluster's busiest wallets


@router.post("/live/start")
async def live_start(body: LiveStart | None = None):
    """Watch mode: check for new transfers every block, rerun the engine when something moves (new alerts land in
    the approval queue), and re-collect public posts every 10 minutes. Stops by itself after 30 minutes."""
    meta = db.get_meta(conn(), "scenario") or {}
    if not meta.get("name"):
        raise HTTPException(400, "Load a case first")
    simulated = meta.get("truth") is not None
    if not simulated and not env("ALCHEMY_API_KEY"):
        raise HTTPException(400, "Watching a real case needs ALCHEMY_API_KEY in backend/.env")
    res = _results()
    busiest = [h["address"] for h in res.get("holdings", []) if not h["freezer"].startswith("exchange:")]
    watch = {norm_addr(a) for a in (body.watch if body and body.watch else
                                     list(dict.fromkeys(busiest + sorted(_members(0)))))[:MAX_WALLETS]}
    if not watch:
        raise HTTPException(400, "Run the analysis first: there are no attacker wallets to watch yet")
    live_stop()
    status = STATE["watch"] = new_status("simulated" if simulated else "blockchain", len(watch))

    async def collect() -> int:
        r = await _collect_posts(OsintCollect())
        return r["rss"] + r["github"] + r["telegram"]

    check = simulated_source(conn()) if simulated else chain_source(watch)
    STATE["live_task"] = asyncio.create_task(
        watch_loop(conn(), check, lambda: run(conn()), collect, status, meta["name"], queue=LIVE_QUEUE))
    return status


@router.post("/live/stop")
def live_stop():
    if STATE["live_task"]:
        STATE["live_task"].cancel()
        STATE["live_task"] = None
    STATE["watch"]["on"] = False
    return STATE["watch"]


@router.get("/live/status")
def live_status():
    return STATE["watch"]


@router.get("/live")
async def live(max_events: Annotated[int | None, Query(ge=1)] = None):
    async def stream():
        sent = 0
        while max_events is None or sent < max_events:
            try:
                t = await asyncio.wait_for(LIVE_QUEUE.get(), timeout=15)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue
            yield f"data: {json.dumps(dataclasses.asdict(t))}\n\n"
            sent += 1
    return StreamingResponse(stream(), media_type="text/event-stream")


app.include_router(router)
