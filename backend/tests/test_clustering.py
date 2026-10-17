from gt.analytics.funding import funding_clusters, gas_funders
from gt.analytics.graph import HUB, build_graph, cluster_wallets
from gt.schema import Transfer
from gt.simulator import evaluate, simulate


def T(h, ts, frm, to, amount):
    return Transfer(h, "eth", ts, frm, to, "ETH", amount)


def test_gas_funder_rules():
    txs = [T("1", 10, "0xf", "0xw", 0.01), T("2", 20, "0xw", "0xx", 5.0),     # funded, then acts → 0xf
           T("3", 10, "0xbig", "0xv", 5.0), T("4", 20, "0xv", "0xx", 1.0),    # first incoming too big → none
           T("5", 10, "0xf", "0xidle", 0.01),                                 # funded but never sends → none
           T("6", 5, "0xu", "0xx", 1.0), T("7", 10, "0xf", "0xu", 0.01)]      # sent before funding → none
    assert gas_funders(txs) == {"0xw": "0xf"}


def test_funding_clusters_never_join_through_hubs():
    c = funding_clusters({"0xa": "0xf", "0xb": "0xf", "0xc": "0xhub", "0xd": "0xhub"}, exclude={"0xhub"})
    assert c["0xa"] == c["0xb"] == c["0xf"]
    assert c["0xc"] != c["0xd"] and "0xhub" not in c


def _attacker_cluster(seed):
    s = simulate(seed=seed)
    G = build_graph(s.transfers)
    c = cluster_wallets(G, gas_funders(s.transfers), {sorted(s.truth.attacker_wallets)[0]}, s.labels)
    return s, c, {w for w, k in c.items() if k == 0}


def test_attacker_cluster_quality_on_simulator():
    s, _, pred = _attacker_cluster(6)
    r = evaluate(pred, None, s.truth)
    # bridged wallets are only reachable once Task 4c adds bridge edges, hence 0.80 here
    assert r["precision"] >= 0.85 and r["recall"] >= 0.80


def test_dust_does_not_spread_the_cluster():
    s, _, pred = _attacker_cluster(6)
    assert not pred & (s.truth.decoy_wallets - s.truth.attacker_wallets)
    assert evaluate(pred, None, s.truth)["precision"] >= 0.98


def test_exchange_never_joins_attacker_cluster():
    s, c, _ = _attacker_cluster(6)
    assert all(c.get(a) == HUB for a, l in s.labels.items() if l.startswith("exchange:") and a in c)


def test_every_node_gets_a_cluster():
    s, c, _ = _attacker_cluster(6)
    G = build_graph(s.transfers)
    assert set(c) == set(G.nodes)
    assert len({k for k in c.values() if k > 0}) > 5      # noise splits into several communities


def test_dust_is_not_gas_funding():
    txs = [T("1", 10, "0xatt", "0xvictim", 0.0001), T("2", 20, "0xvictim", "0xx", 1.0)]
    assert gas_funders(txs) == {}


def test_precision_holds_across_seeds():
    for seed in (6, 7, 8, 9, 10):
        s, _, pred = _attacker_cluster(seed)
        assert evaluate(pred, None, s.truth)["precision"] >= 0.95, seed
