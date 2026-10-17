"""Behaviour fingerprints: is this wallet a bot, and which time zone does its owner live in?"""
import numpy as np
from scipy import stats

AWAKE_LOCAL_HOURS = range(9, 24)   # people act roughly 09:00–23:59 local time
OFFSETS = range(-11, 13)           # 24 distinct hour patterns (UTC-12 ≡ UTC+12 by hour-of-day)
BENFORD = np.log10(1 + 1 / np.arange(1, 10))


def _round_frac(amounts: list[float]) -> float:
    a = np.asarray(amounts, dtype=float)
    return float(np.isclose(a * 10, np.round(a * 10)).mean()) if len(a) else 0.0


def _benford_p(amounts: list[float]) -> float:
    first = [int(f"{a:e}"[0]) for a in amounts if a > 0]
    counts = np.bincount(first, minlength=10)[1:]
    return float(stats.chisquare(counts, BENFORD * counts.sum()).pvalue)


def bot_score(gaps_s: list[float], amounts: list[float]) -> float | None:
    """0..1, higher = more machine-like. Mean of: timing not Poisson-like (KS vs exponential),
    amounts never round, and (with ≥ 20 amounts) first digits not following Benford's law."""
    if len(gaps_s) < 10:
        return None
    gaps = np.asarray(gaps_s, dtype=float)
    parts = [1 - stats.kstest(gaps, "expon", args=(0, gaps.mean())).pvalue,
             1 - _round_frac(amounts)]
    if len([a for a in amounts if a > 0]) >= 20:
        parts.append(1 - _benford_p(amounts))
    return float(np.mean(parts))


def infer_utc_offset(ts_list: list[int]) -> tuple[int, float] | None:
    """(utc_offset, confidence 0..1): the offset whose 09–23 waking window best correlates with the
    hour-of-day histogram. Needs ≥ 15 timestamps."""
    if len(ts_list) < 15:
        return None
    hist = np.bincount((np.asarray(ts_list) // 3600) % 24, minlength=24).astype(float)
    if hist.std() == 0:
        return None
    best = (0, -1.0)
    for off in OFFSETS:
        template = np.zeros(24)
        template[[(h - off) % 24 for h in AWAKE_LOCAL_HOURS]] = 1
        corr = float(np.corrcoef(hist, template)[0, 1])
        if corr > best[1]:
            best = (off, corr)
    return best[0], max(0.0, best[1])
