"""Money-flow graph (wallets = nodes, transfers = edges) and wallet clustering."""
from collections import deque

import networkx as nx

from gt.analytics.amounts import match_bridges
from gt.analytics.funding import funding_clusters
from gt.config import usd
from gt.schema import Transfer

HUB = -1                 # cluster id for labeled hubs (exchanges, mixers, bridges…): never clustered
ATTACKER = 0
MIN_FOLLOW_USD = 100.0   # taint follows real money only — dust and gas payments don't spread it
MAX_HOPS = 4
ALWAYS_FOLLOW = {"deploy", "test_call", "bridge_link"}


def build_graph(transfers: list[Transfer]) -> nx.MultiDiGraph:
    G = nx.MultiDiGraph()
    for t in transfers:
        for a in (t.from_addr, t.to_addr):
            if a not in G:
                G.add_node(a, chain=t.chain)
        G.add_edge(t.from_addr, t.to_addr, key=t.tx_hash, tx_hash=t.tx_hash, ts=t.ts,
                   asset=t.asset, amount=t.amount, kind=t.kind)
    return G


def link_bridges(G: nx.MultiDiGraph, transfers: list[Transfer]) -> list[tuple[str, str, float]]:
    """Match bridge deposits to withdrawals and add a `bridge_link` edge depositor → receiver, so the money
    trail continues across chains. Returns the matches (out_tx, in_tx, confidence)."""
    by_hash = {t.tx_hash: t for t in transfers}
    matches = match_bridges([t for t in transfers if t.kind == "bridge_out"],
                            [t for t in transfers if t.kind == "bridge_in"])
    for oh, ih, conf in matches:
        o, i = by_hash[oh], by_hash[ih]
        G.add_edge(o.from_addr, i.to_addr, key=f"{oh}>{ih}", tx_hash=f"{oh}>{ih}", ts=i.ts,
                   asset=i.asset, amount=i.amount, kind="bridge_link", confidence=conf)
    return matches


def _carries_money(d: dict) -> bool:
    if d["kind"] in ALWAYS_FOLLOW:
        return True
    v = usd(d["asset"], d["amount"])
    return v is None or v >= MIN_FOLLOW_USD


def _reach(G: nx.MultiDiGraph, starts: set[str], hubs: set[str]) -> set[str]:
    """Wallets reachable from `starts` within MAX_HOPS along money-carrying edges, never through hubs."""
    seen, q = set(starts), deque((s, 0) for s in starts)
    while q:
        node, hops = q.popleft()
        if hops == MAX_HOPS:
            continue
        for _, nxt, d in G.out_edges(node, data=True):
            if nxt not in seen and nxt not in hubs and _carries_money(d):
                seen.add(nxt)
                q.append((nxt, hops + 1))
    return seen


def cluster_wallets(G: nx.MultiDiGraph, funders: dict[str, str], seeds: set[str],
                    labels: dict[str, str]) -> dict[str, int]:
    """Cluster 0 = attacker: follow the money from the seeds and pull in every wallet sharing a gas-funding
    group with a member, repeated until nothing new joins. Hubs = -1. Everyone else: Louvain communities 1..n."""
    hubs = set(labels)
    groups = funding_clusters(funders, exclude=hubs)
    by_group: dict[int, set[str]] = {}
    for w, g in groups.items():
        by_group.setdefault(g, set()).add(w)

    attacker = _reach(G, {s for s in seeds if s in G}, hubs)
    while True:
        joined = set().union(*(by_group[groups[w]] for w in attacker if w in groups)) - attacker
        if not joined:
            break
        attacker |= _reach(G, joined, hubs)

    rest = nx.Graph()
    rest.add_nodes_from(n for n in G if n not in attacker and n not in hubs)
    for a, b, d in G.edges(data=True):
        w = usd(d["asset"], d["amount"]) or 0.0
        if a in rest and b in rest and a != b and w > 0:   # all-zero weights made Louvain divide by zero (real data)
            rest.add_edge(a, b, weight=rest.get_edge_data(a, b, {"weight": 0.0})["weight"] + w)
    comms = sorted(nx.community.louvain_communities(rest, weight="weight", seed=0), key=lambda c: (-len(c), min(c)))

    out = {n: HUB for n in G if n in hubs}
    out.update({n: ATTACKER for n in attacker})
    for i, comm in enumerate(comms, start=1):
        out.update({n: i for n in comm})
    return out
