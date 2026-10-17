from gt.defense.guards import find_decoys, is_lookalike, prewarn
from gt.schema import Transfer
from gt.simulator import simulate

T0 = 1_760_000_000


def T(h, ts, frm, to, amount, kind="transfer"):
    return Transfer(h, "eth", ts, frm, to, "ETH", amount, kind=kind)


def test_prewarn_fires_before_the_theft_on_the_simulator():
    s = simulate(seed=7)
    main = sorted(s.truth.attacker_wallets)[0]
    alerts = prewarn(s.transfers, s.labels)
    assert [a.target for a in alerts] == [main]
    a = alerts[0]
    assert a.kind == "prewarn" and a.status == "pending" and a.created_ts < T0
    assert "mixer" in a.message and "test" in a.message


def test_prewarn_needs_all_three_parts():
    L = {"0xmix": "mixer"}
    base = [T("1", 0, "0xmix", "0xw", 1.0, "mixer_out"), T("2", 100, "0xw", "0xc", 0, "deploy"),
            T("3", 200, "0xw", "0xc", 0, "test_call")]
    assert prewarn(base, L) == []                                                   # only one test call
    assert len(prewarn(base + [T("4", 300, "0xw", "0xc", 0, "test_call")], L)) == 1
    late = base + [T("4", 30 * 3600, "0xw", "0xc", 0, "test_call")]
    assert prewarn(late, L) == []                                                   # outside the 24h window
    no_mixer = [T("0", 0, "0xbank", "0xw", 1.0)] + base[1:] + [T("4", 300, "0xw", "0xc", 0, "test_call")]
    assert prewarn(no_mixer, L) == []


def test_prewarn_via_one_funder_hop():
    L = {"0xmix": "mixer"}
    txs = [T("1", 0, "0xmix", "0xf", 1.0, "mixer_out"), T("2", 10, "0xf", "0xw", 0.05),
           T("3", 100, "0xw", "0xc", 0, "deploy"), T("4", 200, "0xw", "0xc", 0, "test_call"),
           T("5", 300, "0xw", "0xc", 0, "test_call")]
    assert [a.target for a in prewarn(txs, L)] == ["0xw"]


def test_lookalike():
    real = "0x1f223f" + "0" * 30 + "beef"
    assert is_lookalike("0x1f223f" + "9" * 30 + "beef", real)
    assert not is_lookalike(real, real)
    assert not is_lookalike("0x1f223f" + "9" * 30 + "dead", real)


def test_decoys_on_simulator():
    s = simulate(seed=7)
    found = find_decoys(s.transfers, s.truth.attacker_wallets, set(s.labels))
    assert not found & s.truth.attacker_wallets
    assert len(found & s.truth.decoy_wallets) >= 0.9 * len(s.truth.decoy_wallets)
    assert found <= s.truth.decoy_wallets


def test_zero_value_messages_and_real_payments_are_not_decoys():
    txs = [T("1", 1, "0xatt", "0xvictim", 0.0), T("2", 2, "0xatt", "0xpaid", 1.0),
           T("3", 3, "0xatt", "0xdust", 0.0001), T("4", 4, "0xdust2", "0xx", 1.0),
           T("5", 5, "0xatt", "0xdust2", 0.0001), T("6", 6, "0xdust2", "0xatt", 0.5)]   # sends back → accomplice
    assert find_decoys(txs, {"0xatt"}, set()) == {"0xdust"}
