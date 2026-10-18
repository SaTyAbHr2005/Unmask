"""One call runs the whole engine on whatever case is loaded (simulator, replay or live):
data → clusters → identities → scored links → money location & exits → proposed alerts."""
import dataclasses
import json
from dataclasses import dataclass, field

import numpy as np

from gt import db
from gt.analytics.amounts import deposit_composition
from gt.analytics.behavior import bot_score, infer_utc_offset
from gt.analytics.features import wallet_features
from gt.analytics.funding import gas_funders
from gt.analytics.graph import ATTACKER, build_graph, cluster_wallets, link_bridges
from gt.chain.labels import load_labels
from gt.chain.normalize import classify
from gt.config import set_eth_usd, usd
from gt.defense.alerts import queue
from gt.defense.freeze import ExitPrediction, Holding, holdings, predict_exits
from gt.defense.guards import find_decoys, prewarn
from gt.fusion.evidence import record
from gt.fusion.score import build_signals, link_for
from gt.osint.extract import extract
from gt.osint.style import resolve_identities
from gt.schema import Alert, Entity, Link, OsintPost, Transfer
from gt.simulator import Scenario, Truth, evaluate

MIN_EXIT_ALERT_SHARE = 0.05
MIN_FREEZE_ALERT_USD = 10_000.0


@dataclass
class Results:
    clusters: dict[str, int] = field(default_factory=dict)
    links: list[Link] = field(default_factory=list)
    exits: list[ExitPrediction] = field(default_factory=list)
    holdings: list[Holding] = field(default_factory=list)
    decoys: set[str] = field(default_factory=set)
    bridges: list[tuple[str, str, float]] = field(default_factory=list)
    bot_scores: dict[str, float] = field(default_factory=dict)
    utc_offsets: dict[str, tuple[int, float]] = field(default_factory=dict)
    metrics: dict | None = None
    stolen_usd: float = 0.0
    case: str = ""
    deposits: list[dict] = field(default_factory=list)      # which laundered pieces make up each exchange deposit
    timing: dict = field(default_factory=dict)              # time-to-freeze window
    features: dict[str, dict] = field(default_factory=dict) # behaviour vector per attacker wallet
    seeds: list[str] = field(default_factory=list)


def load_case(conn, transfers: list[Transfer], posts: list[OsintPost], labels: dict[str, str],
              bytecodes: dict[str, str], truth: Truth | None = None, name: str = "",
              seeds: list[str] | None = None, eth_usd: float | None = None,
              complete: list[str] | None = None) -> None:
    """Replace whatever case is loaded with this one. `eth_usd`: the ETH price on the hack date (None = demo price).
    `complete`: for real traces, the wallets whose whole history was loaded (None = every wallet, as in the simulator)."""
    set_eth_usd(eth_usd)
    db.clear(conn)
    # store each move's role (mixer_in, swap…): the simulator sets it, a real trace only knows "transfer",
    # and the API reads the stored kinds (Beanstalk's Tornado deposits showed as $0 "in mixers")
    every = {**load_labels(), **labels}
    db.insert(conn, [dataclasses.replace(t, kind=classify(t, every)) for t in transfers])
    db.insert(conn, posts)
    db.insert(conn, [e for p in posts for e in extract(p)])
    db.put_meta(conn, "scenario", {
        "name": name, "labels": labels, "bytecodes": bytecodes, "seeds": seeds or [], "eth_usd": eth_usd, "complete": complete,
        "truth": json.loads(json.dumps(dataclasses.asdict(truth), default=sorted)) if truth else None})
    db.put_meta(conn, "results", None)


def load_scenario(conn, s: Scenario, name: str = "Simulated attack") -> None:
    load_case(conn, s.transfers, s.posts, s.labels, s.bytecodes, s.truth, name)


def load_results(conn) -> dict | None:
    return db.get_meta(conn, "results")


def _default_seeds(transfers: list[Transfer], labels: dict[str, str]) -> set[str]:
    """The wallet that received the largest single payment out of the victim."""
    stolen = [t for t in transfers if labels.get(t.from_addr) == "victim" and t.to_addr not in labels]
    return {max(stolen, key=lambda t: usd(t.asset, t.amount) or 0).to_addr} if stolen else set()


def third_party_contracts(transfers: list[Transfer], seeds: set[str], labels: dict[str, str],
                          is_contract) -> dict[str, str]:
    """Real chains only: stolen money also passes through other people's contracts (multisigs, pools, lending
    markets). Any contract that lands in the attacker cluster but wasn't deployed by it becomes a 'contract' hub,
    then we re-cluster until nothing changes. (Euler 2023: the victim's own recovery Safe was being flagged.)"""
    deployed = {t.to_addr for t in transfers if t.kind == "deploy"}
    G, funders = build_graph(transfers), gas_funders(transfers)
    hubs: dict[str, str] = {}
    checked = set(seeds) | deployed
    while True:
        cl = cluster_wallets(G, funders, seeds, {**labels, **hubs})
        new = {w for w, k in cl.items() if k == ATTACKER} - checked
        checked |= new
        found = {w: "contract" for w in sorted(new) if is_contract(w)}
        if not found:
            return hubs
        hubs |= found


def _alerts(exits: list[ExitPrediction], held: list[Holding], transfers, labels) -> list[Alert]:
    out = prewarn(transfers, labels)
    for e in exits:
        if e.share < MIN_EXIT_ALERT_SHARE:
            continue
        if e.arrived:
            msg = (f"{e.share:.0%} of the stolen funds (${e.usd:,.0f}) is already deposited at {e.exchange} "
                   f"({e.address[:12]}…). Ask their compliance team to freeze the account.")
        else:
            eta = "soon" if not e.eta_s else f"~{e.eta_s / 3600:.0f}h" if e.eta_s >= 3600 else f"~{e.eta_s // 60:.0f} min"
            msg = (f"~{e.share:.0%} of the stolen funds (${e.usd:,.0f}) is expected to reach {e.exchange} in {eta}. "
                   f"Warn their compliance team now.")
        out.append(Alert(f"exit:{e.address}:{'arrived' if e.arrived else 'predicted'}", "exit", e.exchange, msg))
    by_issuer: dict[str, list[Holding]] = {}
    for h in held:                       # exchanges are covered by exit alerts; issuers get one alert each
        if h.freezable and not h.freezer.startswith("exchange:"):
            by_issuer.setdefault(h.freezer, []).append(h)
    for issuer, hs in by_issuer.items():
        total = sum(h.usd for h in hs)
        if total >= MIN_FREEZE_ALERT_USD:
            out.append(Alert(f"freeze:{issuer}", "freeze", issuer,
                             f"${total:,.0f} in {', '.join(sorted({h.asset for h in hs}))} across {len(hs)} address(es) "
                             f"can be frozen by {issuer}. The freeze request is ready in the report."))
    return out


def _timing(transfers: list[Transfer], cluster0: set[str], labels: dict[str, str],
            exits: list[ExitPrediction], now_ts: int) -> dict:
    """The freeze window: theft → first cash-out, how early the pre-attack warning came, what's next."""
    theft = min((t.ts for t in transfers if labels.get(t.from_addr) == "victim" and t.to_addr in cluster0), default=None)
    cashout = min((t.ts for t in transfers if t.from_addr in cluster0
                   and labels.get(t.to_addr, "").startswith("exchange:")), default=None)
    warn = min((a.created_ts for a in prewarn(transfers, labels) if a.target in cluster0), default=None)
    etas = [e.eta_s for e in exits if not e.arrived and e.eta_s]
    return {"theft_ts": theft, "first_cashout_ts": cashout,
            "time_to_first_cashout_s": cashout - theft if theft and cashout else None,
            "prewarn_ts": warn, "prewarn_lead_s": theft - warn if theft and warn else None,
            "next_predicted_exit_s": min(etas) if etas else None, "case_now_ts": now_ts}


def _features(transfers: list[Transfer], wallets: set[str]) -> dict[str, dict]:
    df = wallet_features([t for t in transfers if t.from_addr in wallets])
    return {w: {k: (None if v != v else float(v)) for k, v in row.items()} for w, row in df.iterrows()}  # NaN → None


def run(conn, seeds: set[str] | None = None) -> Results:
    meta = db.get_meta(conn, "scenario") or {}
    set_eth_usd(meta.get("eth_usd"))
    labels = {**load_labels(), **meta.get("labels", {})}
    bytecodes = meta.get("bytecodes", {})
    transfers = [dataclasses.replace(t, kind=classify(t, labels)) for t in db.select(conn, Transfer)]
    posts, entities = db.select(conn, OsintPost), db.select(conn, Entity)
    seeds = seeds or set(meta.get("seeds", [])) or _default_seeds(transfers, labels)
    if not transfers or not seeds:
        return Results(case=meta.get("name", ""))

    G = build_graph(transfers)
    bridges = link_bridges(G, transfers)
    clusters = cluster_wallets(G, gas_funders(transfers), seeds, labels)
    cluster0 = {w for w, k in clusters.items() if k == ATTACKER}
    decoys = find_decoys(transfers, cluster0, set(labels))
    cluster0 -= decoys
    now_ts = max(t.ts for t in transfers)   # the case's "now" is chain time — OSINT collected later must not age it
    last_cluster_ts = max((t.ts for t in transfers if t.from_addr in cluster0), default=0)

    # identities → scored, explained links (analyst decisions are kept)
    ids = resolve_identities(posts)
    by_identity: dict[str, list[OsintPost]] = {}
    for p in posts:
        by_identity.setdefault(ids[f"{p.source}:{p.author}"], []).append(p)
    decided = {l.link_id: l.status for l in db.select(conn, Link) if l.status in ("confirmed", "rejected")}
    links = []
    for identity, ps in by_identity.items():
        signals = build_signals(cluster0, ps, entities, transfers, bytecodes)
        if not signals:
            continue
        freshest = max(max(p.ts for p in ps), last_cluster_ts)       # newest activity on either side of the link
        link = link_for(ATTACKER, identity, signals, age_s=now_ts - freshest, now_ts=now_ts)
        link.evidence = [record(conn, s, "signal") for s in signals]
        link.status = decided.get(link.link_id, link.status)
        links.append(link)
    links.sort(key=lambda l: -l.score)
    conn.link.delete_many({})
    db.insert(conn, links)

    # where is the money, where is it going, what should a human approve
    # a balance is only real where the wallet's whole history was loaded; elsewhere the money was merely last seen
    known = cluster0 if meta.get("complete") is None else cluster0 & set(meta["complete"])
    held = holdings(transfers, known, labels)
    # no theft seen: what the attacker's wallets still hold plus what they already sent into mixers and bridges or
    # gave back (Beanstalk read "$0.1M traced" once its $74M profit was in Tornado; Euler returned $189M)
    passed = sum((usd(t.asset, t.amount) or 0) * ((t.from_addr in cluster0 and (t.kind in ("mixer_in", "bridge_out")
                                                                                or labels.get(t.to_addr) == "victim"))
                                                  - (t.to_addr in cluster0 and t.kind in ("mixer_out", "bridge_in")))
                 for t in transfers)
    stolen = sum(usd(t.asset, t.amount) or 0 for t in transfers
                 if labels.get(t.from_addr) == "victim" and t.to_addr in cluster0) or sum(h.usd for h in held) + max(passed, 0)
    exits = predict_exits(G, seeds, labels, stolen)
    queue(conn, _alerts(exits, held, transfers, labels))

    sent: dict[str, list[Transfer]] = {}
    for t in sorted(transfers, key=lambda t: t.ts):
        if t.from_addr in cluster0:
            sent.setdefault(t.from_addr, []).append(t)
    bots = {w: s for w, txs in sent.items()
            if (s := bot_score(np.diff([t.ts for t in txs]).tolist(), [t.amount for t in txs if t.amount > 0])) is not None}
    offsets = {}
    if (o := infer_utc_offset([t.ts for txs in sent.values() for t in txs])):
        offsets["cluster:0"] = o
    for identity, ps in by_identity.items():
        if (o := infer_utc_offset([p.ts for p in ps])):
            offsets[f"identity:{identity}"] = o

    metrics = None
    if meta.get("truth"):
        truth = Truth(**{k: set(v) if isinstance(v, list) else v for k, v in meta["truth"].items()})
        handle = links[0].identity.split(":", 1)[1] if links else None
        metrics = evaluate(cluster0, handle, truth)

    r = Results(clusters, links, exits, held, decoys, bridges, bots, offsets, metrics, stolen, meta.get("name", ""),
                deposit_composition(transfers, cluster0, labels), _timing(transfers, cluster0, labels, exits, now_ts),
                _features(transfers, cluster0), sorted(seeds))
    db.put_meta(conn, "results", json.loads(json.dumps(dataclasses.asdict(r), default=sorted)))
    return r
