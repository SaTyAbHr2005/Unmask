"""Time-delta latency analysis: do this person's posts keep landing minutes before the wallets act?

Test: how many posts are followed by a transaction within max_lag_s? Compare against the same posts
shifted in time (circular shift keeps the person's posting rhythm but breaks any real link). If the real
hit rate beats almost every shifted version, the timing is not a coincidence."""
import numpy as np

HOUR = 3600


def _hits_and_lags(posts: np.ndarray, txs: np.ndarray, max_lag_s: int) -> tuple[np.ndarray, np.ndarray]:
    """For every post (any shape): lag to the first tx strictly after it, and whether that lag ≤ max_lag_s."""
    idx = np.searchsorted(txs, posts, side="right")
    nxt = txs[np.minimum(idx, len(txs) - 1)]
    lag = np.where(idx < len(txs), nxt - posts, np.iinfo(np.int64).max)
    return lag <= max_lag_s, lag


def latency_test(post_ts: list[int], tx_ts: list[int], max_lag_s: int = 900,
                 n_perm: int = 500, seed: int = 0) -> dict | None:
    if len(post_ts) < 5 or not tx_ts:
        return None
    posts = np.sort(np.asarray(post_ts, dtype=np.int64))
    txs = np.sort(np.asarray(tx_ts, dtype=np.int64))
    lo = min(posts[0], txs[0])
    span = max(posts[-1], txs[-1]) - lo
    if span <= 2 * HOUR:
        return None

    hits, lags = _hits_and_lags(posts, txs, max_lag_s)
    observed = float(hits.mean())

    offsets = np.random.default_rng(seed).integers(HOUR, span - HOUR, size=n_perm)
    shifted = lo + (posts[None, :] - lo + offsets[:, None]) % span
    null_hits, _ = _hits_and_lags(shifted, txs, max_lag_s)
    null_rates = null_hits.mean(axis=1)

    return {"hit_rate": observed,
            "p_value": float((1 + np.sum(null_rates >= observed)) / (1 + n_perm)),
            "median_lag_s": float(np.median(lags[hits])) if hits.any() else None,
            "null_hit_rate": float(null_rates.mean()),
            "n_posts": int(len(posts))}


def latency_lr(p_value: float) -> float:
    """Likelihood ratio for the fusion layer: strong / moderate / no evidence."""
    return 20.0 if p_value < 0.01 else 5.0 if p_value < 0.05 else 1.0
