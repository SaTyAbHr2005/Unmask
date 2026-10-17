"""Money is conserved: split pieces add back up to the original, and a bridge deposit reappears
on the other chain minus a small fee, a few minutes later."""
import bisect

from gt.schema import Transfer


def _subset_sums(items: list[tuple[str, float]]) -> list[tuple[float, int]]:
    """Every (sum, bitmask) over the items."""
    sums = [(0.0, 0)]
    for i, (_, amt) in enumerate(items):
        sums += [(s + amt, m | 1 << i) for s, m in sums]
    return sums


def match_split(parent_amount: float, children: list[tuple[str, float]], tol: float = 0.005,
                max_n: int = 25) -> list[str] | None:
    """Ids of children whose amounts add up to parent_amount within ±tol (relative), else None.
    ponytail: meet-in-the-middle over the max_n largest children (2^13 × 2^12 sums); upgrade = ILP solver."""
    items = sorted(children, key=lambda c: -c[1])[:max_n]
    if not items or parent_amount <= 0:
        return None
    half = len(items) // 2
    left, right = items[:half], items[half:]
    rsums = sorted(_subset_sums(right))
    rvals = [s for s, _ in rsums]
    lo_t, hi_t = parent_amount * (1 - tol), parent_amount * (1 + tol)
    for ls, lm in _subset_sums(left):
        j = bisect.bisect_left(rvals, lo_t - ls)
        if j < len(rvals) and rvals[j] + ls <= hi_t and (lm or rsums[j][1]):
            rm = rsums[j][1]
            return [left[i][0] for i in range(len(left)) if lm >> i & 1] + \
                   [right[i][0] for i in range(len(right)) if rm >> i & 1]
    return None


def match_bridges(outs: list[Transfer], ins: list[Transfer], fee_max: float = 0.003,
                  window_s: tuple[int, int] = (60, 1800)) -> list[tuple[str, str, float]]:
    """(out_tx, in_tx, confidence) pairs. A pair qualifies when the same asset arrives on the other side
    0–fee_max cheaper within the time window; pairs are assigned one-to-one, closest in time first."""
    ins = sorted(ins, key=lambda t: t.ts)
    in_ts = [t.ts for t in ins]
    cands = []
    for o in outs:
        if o.amount <= 0:
            continue
        lo = bisect.bisect_left(in_ts, o.ts + window_s[0])
        hi = bisect.bisect_right(in_ts, o.ts + window_s[1])
        for i in ins[lo:hi]:
            fee = (o.amount - i.amount) / o.amount
            if i.asset == o.asset and 0 <= fee <= fee_max:
                cands.append((i.ts - o.ts, o.tx_hash, i.tx_hash, fee))
    used_o, used_i, out = set(), set(), []
    for gap, oh, ih, fee in sorted(cands):
        if oh in used_o or ih in used_i:
            continue
        used_o.add(oh)
        used_i.add(ih)
        out.append((oh, ih, 1 - fee / fee_max * 0.5 - gap / window_s[1] * 0.5))
    return out
