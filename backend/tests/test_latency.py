import time

import numpy as np

from gt.analytics.latency import latency_lr, latency_test
from gt.simulator import simulate


def _att_tx(s):
    return sorted(t.ts for t in s.transfers if t.from_addr in s.truth.attacker_wallets)


def test_attacker_handle_is_significant():
    s = simulate(seed=9)
    posts = sorted(p.ts for p in s.posts if p.author == "ghostfox")
    r = latency_test(posts, _att_tx(s))
    assert r["p_value"] < 0.01 and r["hit_rate"] >= 0.9 and 0 < r["median_lag_s"] <= 360


def test_random_author_is_not():
    s = simulate(seed=9)
    noise = [p for p in s.posts if p.author not in s.truth.attacker_handles]
    author = max({p.author for p in noise}, key=lambda a: sum(p.author == a for p in noise))
    assert latency_test(sorted(p.ts for p in noise if p.author == author), _att_tx(s))["p_value"] > 0.05


def test_too_little_data_is_none():
    assert latency_test([1, 2, 3], [5, 6]) is None
    assert latency_test(list(range(0, 50000, 5000)), []) is None


def test_deterministic_and_fast():
    rng = np.random.default_rng(0)
    posts = np.sort(rng.integers(0, 10 * 86400, 1000)).tolist()
    txs = np.sort(rng.integers(0, 10 * 86400, 5000)).tolist()
    t = time.time()
    a = latency_test(posts, txs)
    assert time.time() - t < 1.0
    assert a == latency_test(posts, txs)


def test_lr_buckets():
    assert (latency_lr(0.002), latency_lr(0.03), latency_lr(0.4)) == (20.0, 5.0, 1.0)
