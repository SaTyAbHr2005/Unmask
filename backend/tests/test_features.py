import math

from gt.analytics.features import activity_matrix, wallet_features
from gt.analytics.graph import build_graph
from gt.schema import Transfer


def T(h, ts, frm, to, amount=1.0, gas=20.0, kind="transfer", chain="eth"):
    return Transfer(h, chain, ts, frm, to, "ETH", amount, gas, 0, "0x", kind)


def test_activity_matrix_shape_and_counts():
    m = activity_matrix([T("1", 0, "0xa", "0xb"), T("2", 3700, "0xa", "0xc"), T("3", 100, "0xb", "0xa")])
    assert set(m.index) == {"0xa", "0xb"} and list(m.columns) == [0, 3600]
    assert m.loc["0xa"].tolist() == [1, 1] and m.loc["0xb"].tolist() == [1, 0]


def test_activity_matrix_empty():
    assert activity_matrix([]).empty


def test_wallet_features_values():
    txs = [T(str(i), ts, "0xa", "0xb", amt, gas) for i, (ts, amt, gas) in
           enumerate([(0, 1.0, 10.0), (100, 2.5, 20.0), (300, 10.0, 30.0), (3600 * 5, 3.1234, 40.0)])]
    f = wallet_features(txs).loc["0xa"]
    assert f["n_tx"] == 4 and f["mean_gas"] == 25.0
    assert f["round_frac"] == 0.75
    assert f["active_hours"] == 2          # hours 0 and 5 UTC
    assert math.isclose(f["mean_gap_s"], (100 + 200 + 17700) / 3)


def test_wallet_with_one_tx_has_nan_gaps_not_error():
    f = wallet_features([T("1", 0, "0xa", "0xb")]).loc["0xa"]
    assert f["n_tx"] == 1 and math.isnan(f["cv_gap"]) and math.isnan(f["mean_gap_s"])


def test_wallet_features_empty():
    assert wallet_features([]).empty


def test_graph_edges_and_attrs():
    G = build_graph([T("1", 0, "0xa", "0xb", kind="mixer_in"), T("2", 5, "0xa", "0xb"), T("3", 9, "0xb", "0xc", chain="arb")])
    assert G.number_of_edges() == 3 and G.number_of_nodes() == 3
    assert {d["kind"] for _, _, d in G.edges("0xa", data=True)} == {"mixer_in", "transfer"}
    assert G.nodes["0xc"]["chain"] == "arb"
    assert G["0xb"]["0xc"]["3"]["amount"] == 1.0    # edge key = tx_hash
