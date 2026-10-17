"""Where is the stolen money now, how much can still be frozen, and where will the rest cash out?"""
import statistics
from collections import defaultdict
from dataclasses import dataclass

import networkx as nx

from gt.config import usd
from gt.schema import Transfer

ISSUER_FREEZE = {"USDT": "Tether", "USDC": "Circle"}   # stablecoin issuers can freeze balances on request


@dataclass
class Holding:
    address: str
    asset: str
    amount: float
    usd: float
    freezable: bool
    freezer: str          # "Tether" | "Circle" | "exchange:<name>" | ""


@dataclass
class ExitPrediction:
    exchange: str
    address: str
    share: float          # fraction of the stolen funds
    usd: float
    eta_s: int | None     # expected seconds until it lands (predicted rows only)
    arrived: bool         # True = already deposited there; False = predicted


def _is_exchange(label: str) -> bool:
    return label.startswith("exchange:")


def holdings(transfers: list[Transfer], wallets: set[str], labels: dict[str, str],
             min_usd: float = 100.0) -> list[Holding]:
    """Net balance of every cluster wallet per asset, plus what was already deposited at exchanges.
    Balances under min_usd (leftover gas) are left out."""
    bal: dict[tuple[str, str], float] = defaultdict(float)
    deposited: dict[tuple[str, str], float] = defaultdict(float)
    for t in transfers:
        if t.to_addr in wallets:
            bal[(t.to_addr, t.asset)] += t.amount
        if t.from_addr in wallets:
            bal[(t.from_addr, t.asset)] -= t.amount
            if _is_exchange(labels.get(t.to_addr, "")):
                deposited[(t.to_addr, t.asset)] += t.amount
    out = []
    for (addr, asset), amt in bal.items():
        value = usd(asset, amt) or 0.0
        if value >= min_usd:
            freezer = ISSUER_FREEZE.get(asset, "")
            out.append(Holding(addr, asset, amt, value, bool(freezer), freezer))
    for (addr, asset), amt in deposited.items():
        out.append(Holding(addr, asset, amt, usd(asset, amt) or 0.0, True, labels[addr]))
    return sorted(out, key=lambda h: -h.usd)


def _edge_value(d: dict) -> float:
    return usd(d["asset"], d["amount"]) or 0.0


def _dwell_s(G: nx.MultiDiGraph, nodes: set[str]) -> int | None:
    """Median time a wallet holds funds before passing them on (first send after first receive)."""
    waits = []
    for n in nodes:
        ins = [d["ts"] for *_, d in G.in_edges(n, data=True)]
        if not ins:
            continue
        outs = [d["ts"] for *_, d in G.out_edges(n, data=True) if d["ts"] >= min(ins)]
        if outs:
            waits.append(min(outs) - min(ins))
    return int(statistics.median(waits)) if waits else None


MIN_PATTERN_SHARE = 0.05   # cash-outs seen so far must cover ≥5% of the money before we extrapolate from them


def predict_exits(G: nx.MultiDiGraph, sources: set[str], labels: dict[str, str], total_usd: float,
                  max_hops: int = 6) -> list[ExitPrediction]:
    """Push the stolen money forward through the graph (each wallet passes it on in proportion to what it sent);
    exchanges absorb it (= arrived). Money still sitting in wallets is predicted to exit the way the attacker
    already cashed out — or, with no exits yet, through the busiest exchanges.
    ponytail: proportional flow ignores timing order; upgrade = temporal walk if it misranks on replay."""
    exch = {a: l.split(":", 1)[1] for a, l in labels.items() if _is_exchange(l)}
    srcs = [s for s in sources if s in G]
    if not srcs:
        return []
    mass = {s: 1 / len(srcs) for s in srcs}
    absorbed: dict[str, float] = defaultdict(float)
    stuck = 0.0
    visited: set[str] = set()
    for _ in range(max_hops):
        nxt: dict[str, float] = defaultdict(float)
        for node, m in mass.items():
            if node in exch:
                absorbed[node] += m
                continue
            visited.add(node)
            outs = [(v, d) for _, v, d in G.out_edges(node, data=True) if v != node]
            if any(d["kind"] == "bridge_link" for _, d in outs):     # same money as the bridge deposit
                outs = [(v, d) for v, d in outs if d["kind"] != "bridge_out"]
            total = sum(_edge_value(d) for _, d in outs)
            if total <= 0:
                stuck += m
                continue
            for v, d in outs:
                nxt[v] += m * _edge_value(d) / total
        mass = nxt
    for node, m in mass.items():
        if node in exch:
            absorbed[node] += m
        else:
            stuck += m

    rows = [ExitPrediction(exch[a], a, s, s * total_usd, None, True) for a, s in absorbed.items() if s > 1e-9]
    pattern = dict(absorbed) or {a: sum(_edge_value(d) for *_, d in G.in_edges(a, data=True)) for a in exch if a in G}
    norm = sum(pattern.values())
    # a pattern needs evidence: on Euler 2023 one $60K deposit (0.04%) was extrapolated to all $170M
    if stuck > 1e-9 and norm > 0 and (not absorbed or norm >= MIN_PATTERN_SHARE):
        eta = _dwell_s(G, visited)
        rows += [ExitPrediction(exch[a], a, stuck * w / norm, stuck * w / norm * total_usd, eta, False)
                 for a, w in pattern.items() if w > 0]
    return sorted(rows, key=lambda r: -r.share)
