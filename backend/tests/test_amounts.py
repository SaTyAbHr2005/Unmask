import time

from gt.analytics.amounts import match_bridges, match_split
from gt.analytics.funding import gas_funders
from gt.analytics.graph import build_graph, cluster_wallets, link_bridges
from gt.schema import Transfer
from gt.simulator import evaluate, simulate


def test_split_found():
    kids = [("a", 3.0), ("b", 4.0), ("c", 5.5), ("d", 100.0)]
    assert sorted(match_split(12.5, kids)) == ["a", "b", "c"]


def test_split_within_tolerance_and_none_when_impossible():
    assert sorted(match_split(10.04, [("a", 4.0), ("b", 6.0)])) == ["a", "b"]   # 0.4% off, tol 0.5%
    assert match_split(50.0, [("a", 4.0), ("b", 6.0)]) is None
    assert match_split(5.0, []) is None


def test_split_blowup_is_bounded():
    kids = [(str(i), 1.0 + i * 0.37) for i in range(300)]
    t = time.time()
    match_split(99999.0, kids)
    assert time.time() - t < 1.0


def B(h, ts, amount, kind, chain="eth"):
    return Transfer(h, chain, ts, "0xu" + h, "0xr" + h, "ETH", amount, kind=kind)


def test_bridge_rules():
    outs = [B("o1", 0, 10.0, "bridge_out"), B("o2", 0, 10.0, "bridge_out"), B("o3", 0, 7.0, "bridge_out")]
    ins = [B("i1", 300, 9.99, "bridge_in", "arb"),     # fee 0.1%, 5 min → match
           B("i2", 900, 9.98, "bridge_in", "arb"),     # also fits; one-to-one gives it to the other 10.0 out
           B("i3", 100, 6.0, "bridge_in", "arb"),      # fee 14% → never
           B("i4", 5000, 7.0, "bridge_in", "arb")]     # too late → never
    m = match_bridges(outs, ins)
    assert {(o, i) for o, i, _ in m} == {("o1", "i1"), ("o2", "i2")}
    assert all(0 < c <= 1 for _, _, c in m)
    assert dict(((o, i), c) for o, i, c in m)[("o1", "i1")] > dict(((o, i), c) for o, i, c in m)[("o2", "i2")]


def test_bridges_on_simulator():
    s = simulate(seed=8)
    outs = [t for t in s.transfers if t.kind == "bridge_out"]
    ins = [t for t in s.transfers if t.kind == "bridge_in"]
    assert len(match_bridges(outs, ins)) >= 0.9 * len(outs)


def test_bridge_links_raise_cluster_recall():
    s = simulate(seed=6)
    G = build_graph(s.transfers)
    links = link_bridges(G, s.transfers)
    assert links and sum(1 for *_, d in G.edges(data=True) if d["kind"] == "bridge_link") == len(links)
    c = cluster_wallets(G, gas_funders(s.transfers), {sorted(s.truth.attacker_wallets)[0]}, s.labels)
    r = evaluate({w for w, k in c.items() if k == 0}, None, s.truth)
    assert r["precision"] >= 0.95 and r["recall"] >= 0.95
