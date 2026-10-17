import pytest

from gt.analytics.funding import gas_funders
from gt.analytics.graph import build_graph, cluster_wallets, link_bridges
from gt.defense.freeze import holdings, predict_exits
from gt.schema import Transfer
from gt.simulator import simulate


def T(h, ts, frm, to, amount, asset="ETH", kind="transfer"):
    return Transfer(h, "eth", ts, frm, to, asset, amount, kind=kind)


LABELS = {"0xx": "exchange:X", "0xy": "exchange:Y", "0xz": "exchange:Z"}


def test_flow_shares_split_by_amount():
    G = build_graph([T("1", 1, "0xs", "0xa", 60), T("2", 2, "0xs", "0xb", 40),
                     T("3", 3, "0xa", "0xx", 60), T("4", 4, "0xb", "0xy", 40)])
    ex = predict_exits(G, {"0xs"}, LABELS, total_usd=300_000)
    assert [(e.exchange, round(e.share, 3), e.arrived) for e in ex] == [("X", 0.6, True), ("Y", 0.4, True)]
    assert round(ex[0].usd) == 180_000


def test_money_still_held_is_predicted_to_follow_the_same_pattern():
    G = build_graph([T("1", 1, "0xs", "0xa", 50), T("2", 2, "0xs", "0xb", 50),
                     T("3", 100, "0xa", "0xx", 50)])           # 0xb still holds its half
    ex = {(e.exchange, e.arrived): e for e in predict_exits(G, {"0xs"}, LABELS, total_usd=1000)}
    assert round(ex[("X", True)].share, 3) == 0.5
    assert round(ex[("X", False)].share, 3) == 0.5 and ex[("X", False)].eta_s is not None


def test_no_exit_yet_falls_back_to_busiest_exchange():
    G = build_graph([T("1", 1, "0xs", "0xa", 10), T("2", 2, "0xn1", "0xz", 999), T("3", 3, "0xn2", "0xy", 5)])
    ex = predict_exits(G, {"0xs"}, LABELS, total_usd=100)
    assert ex[0].exchange == "Z" and not ex[0].arrived and round(ex[0].share, 3) == round(999 / 1004, 3)
    assert round(sum(e.share for e in ex), 6) == 1.0


def test_holdings_freezability():
    txs = [T("1", 1, "0xv", "0xw", 10.0), T("2", 2, "0xd", "0xw", 5000.0, "USDT"),
           T("3", 3, "0xw", "0xx", 4.0), T("4", 4, "0xd", "0xw", 2000.0, "USDC"),
           T("5", 5, "0xg", "0xw", 0.01)]                       # a gas top-up just adds to the ETH balance
    h = {(x.address, x.asset): x for x in holdings(txs, {"0xw"}, LABELS)}
    assert h[("0xw", "USDT")].freezable and h[("0xw", "USDT")].freezer == "Tether"
    assert h[("0xw", "USDC")].freezer == "Circle"
    eth = h[("0xw", "ETH")]
    assert not eth.freezable and round(eth.amount, 2) == 6.01 and eth.usd > 0
    assert h[("0xx", "ETH")].freezable and h[("0xx", "ETH")].freezer == "exchange:X"   # already deposited


@pytest.fixture(scope="module")
def sim():
    s = simulate(seed=7)
    G = build_graph(s.transfers)
    link_bridges(G, s.transfers)
    c = cluster_wallets(G, gas_funders(s.transfers), {sorted(s.truth.attacker_wallets)[0]}, s.labels)
    return s, G, {w for w, k in c.items() if k == 0}


def test_simulator_exits_and_freezable(sim):
    s, G, cluster = sim
    main = sorted(s.truth.attacker_wallets)[0]
    ex = predict_exits(G, {main}, s.labels, total_usd=42_000_000)
    assert ex[0].exchange in s.truth.exit_exchanges
    assert 0.99 <= sum(e.share for e in ex) <= 1.01
    h = holdings(s.transfers, cluster, s.labels)
    assert sum(x.usd for x in h if x.freezable) > 0
    assert any(x.asset == "ETH" and not x.freezable for x in h)       # the raw-ETH consolidation wallet
