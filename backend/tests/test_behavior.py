import numpy as np

from gt.analytics.behavior import bot_score, infer_utc_offset
from gt.simulator import simulate


def test_bot_scores_high():
    rng = np.random.default_rng(1)
    gaps = rng.uniform(20, 40, 60).tolist()                 # metronome-like
    amounts = rng.uniform(1.0, 9.99, 60).round(6).tolist()  # never round, flat first digits
    assert bot_score(gaps, amounts) > 0.7


def test_human_scores_low():
    rng = np.random.default_rng(2)
    gaps = rng.exponential(1800, 60).tolist()                # Poisson-like
    amounts = rng.lognormal(0, 2, 60)
    amounts[::2] = np.round(amounts[::2], 1)                 # half rounded
    assert bot_score(gaps, amounts.tolist()) < 0.5


def test_bot_score_needs_enough_data():
    assert bot_score([30.0] * 5, [1.23] * 5) is None
    assert bot_score([30.0] * 12, [1.23] * 5) is not None    # Benford part skipped below 20 amounts


def test_bot_score_same_second_burst_is_finite():
    s = bot_score([0.0] * 12, [1.23] * 12)    # a contract's batch, all in one block
    assert s is not None and 0 <= s <= 1


def test_timezone_from_waking_hours():
    rng = np.random.default_rng(3)
    day0 = 1_760_000_000 - 1_760_000_000 % 86400
    local_hours = rng.integers(10, 23, 200)                  # active 10:00–22:59 local
    ts = [int(day0 + d * 86400 + (h - 9) * 3600 + m) for d, h, m in
          zip(rng.integers(0, 5, 200), local_hours, rng.integers(0, 3600, 200))]
    off, conf = infer_utc_offset(ts)
    assert off in {8, 9, 10} and 0 < conf <= 1


def test_timezone_needs_enough_data():
    assert infer_utc_offset([1, 2, 3]) is None


def test_simulator_attacker_is_bot_and_utc_plus_9():
    s = simulate(seed=4)
    main = sorted(s.truth.attacker_wallets)[0]
    sent = sorted((t for t in s.transfers if t.from_addr == main), key=lambda t: t.ts)
    gaps = np.diff([t.ts for t in sent]).tolist()
    assert bot_score(gaps, [t.amount for t in sent if t.amount > 0.001]) > 0.6
    att_ts = [t.ts for t in s.transfers if t.from_addr in s.truth.attacker_wallets]
    assert infer_utc_offset(att_ts)[0] in {8, 9, 10}
