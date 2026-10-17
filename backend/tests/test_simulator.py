from gt.simulator import simulate, evaluate


def test_deterministic():
    a, b = simulate(seed=1), simulate(seed=1)
    assert a.transfers == b.transfers and a.posts == b.posts


def test_money_is_conserved_in_split():
    s = simulate(seed=2, n_split=50)
    main = sorted(s.truth.attacker_wallets)[0]  # main wallet is "0x00…" so it sorts first
    out = sum(t.amount for t in s.transfers
              if t.from_addr == main and t.asset == "ETH" and t.kind == "transfer")
    assert abs(out - 14_000) / 14_000 < 0.001  # 42M USD / ETH_USD 3000


def test_scenario_contains_every_signal_kind():
    s = simulate(seed=3)
    kinds = {t.kind for t in s.transfers}
    assert {"mixer_in", "mixer_out", "bridge_out", "bridge_in", "swap", "deploy", "test_call"} <= kinds
    assert any("exchange:" in v for v in s.labels.values())
    assert s.truth.decoy_wallets and s.bytecodes


def test_evaluate_perfect():
    s = simulate(seed=4)
    r = evaluate(s.truth.attacker_wallets, next(iter(s.truth.attacker_handles)), s.truth)
    assert r["precision"] == 1.0 and r["recall"] == 1.0 and r["handle_correct"]


def test_evaluate_partial_and_empty():
    s = simulate(seed=4)
    half = set(sorted(s.truth.attacker_wallets)[: len(s.truth.attacker_wallets) // 2])
    r = evaluate(half | {"0xnotattacker"}, "nobody", s.truth)
    assert 0 < r["recall"] < 1 and r["precision"] < 1 and not r["handle_correct"]
    assert evaluate(set(), None, s.truth)["f1"] == 0.0


def test_hashes_unique_and_addresses_lowercase():
    s = simulate(seed=5)
    assert len({t.tx_hash for t in s.transfers}) == len(s.transfers)
    assert all(t.from_addr == t.from_addr.lower() and t.to_addr == t.to_addr.lower() for t in s.transfers)


def test_attacker_acts_only_in_local_waking_hours():
    s = simulate(seed=6, utc_offset=9)
    hours = {((t.ts // 3600) + 9) % 24 for t in s.transfers if t.from_addr in s.truth.attacker_wallets}
    assert hours <= set(range(9, 24))


def test_attacker_posts_precede_attacker_txs():
    s = simulate(seed=7)
    tx = sorted(t.ts for t in s.transfers if t.from_addr in s.truth.attacker_wallets)
    posts = [p.ts for p in s.posts if p.author == "ghostfox"]
    assert len(posts) >= 20
    hits = sum(any(0 < x - p <= 900 for x in tx) for p in posts)
    assert hits / len(posts) >= 0.9
