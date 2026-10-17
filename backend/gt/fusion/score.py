"""Fusion: turn independent clues into one probability that a wallet cluster belongs to an online identity,
with a plain-English reason for every number.

Each clue is a likelihood ratio (LR): how many times more likely we'd see it if the link were real than
if it weren't. Start from a sceptical prior (1%), multiply the odds by every LR, convert back to a probability."""
import time

from gt import llm
from gt.analytics.behavior import infer_utc_offset
from gt.analytics.bytecode import selectors_from_bytecode, selectors_from_source, similarity
from gt.analytics.latency import latency_lr, latency_test
from gt.chain.normalize import decode_message
from gt.config import HALF_LIFE_S, PRIOR
from gt.schema import Entity, Link, OsintPost, Signal, Transfer

LR_MIN, LR_MAX = 0.1, 50.0   # no single clue may decide a case on its own


def posterior(signals: list[Signal], prior: float = PRIOR) -> float:
    """ponytail: naive Bayes assumes the clues are independent; upgrade = learn weights on simulator runs."""
    odds = prior / (1 - prior)
    for s in signals:
        odds *= min(max(s.lr, LR_MIN), LR_MAX)
    return odds / (1 + odds)


def decay(score: float, age_s: int, half_life_s: int = HALF_LIFE_S) -> float:
    """Confidence halves every half_life_s without fresh evidence."""
    return score * 0.5 ** (max(age_s, 0) / half_life_s)


def _tz_distance(a: int, b: int) -> int:
    d = abs(a - b) % 24
    return min(d, 24 - d)


def build_signals(cluster_wallets: set[str], identity_posts: list[OsintPost], entities: list[Entity],
                  transfers: list[Transfer], bytecodes: dict[str, str]) -> list[Signal]:
    """Statistical tests (timing, time zone, code) are reported whenever there is enough data — even when
    neutral. Mention clues (address in a post, handle in an on-chain message) only when they match:
    not being mentioned proves nothing. Missing inputs produce no signal at all."""
    if not cluster_wallets or not identity_posts:
        return []
    out: list[Signal] = []
    cluster_tx = [t for t in transfers if t.from_addr in cluster_wallets]
    post_ts = [p.ts for p in identity_posts]
    handles = {p.author.lower() for p in identity_posts}

    r = latency_test(post_ts, [t.ts for t in cluster_tx]) if cluster_tx else None
    if r:
        n = r["n_posts"]
        lag = f"{r['median_lag_s']:.0f}s" if r["median_lag_s"] is not None else "n/a"
        out.append(Signal("time_delta", latency_lr(r["p_value"]),
                          f"{round(r['hit_rate'] * n)}/{n} posts were followed by a cluster transaction within "
                          f"15 min (median {lag}; randomly shifted posts: {r['null_hit_rate']:.0%}), p={r['p_value']:.3f}"))

    oc, oi = infer_utc_offset([t.ts for t in cluster_tx]), infer_utc_offset(post_ts)
    if oc and oi:
        same = _tz_distance(oc[0], oi[0]) <= 1
        out.append(Signal("rhythm", 3.0 if same else 0.5,
                          f"wallets are active like a UTC{oc[0]:+d} schedule, posts like UTC{oi[0]:+d}"
                          + (" — same time zone" if same else " — different time zones")))

    post_ids = {p.post_id for p in identity_posts}
    mentioned = sorted({e.value for e in entities if e.post_id in post_ids and e.kind == "address"} & cluster_wallets)
    if mentioned:
        out.append(Signal("address_mention", 30.0,
                          f"posted {len(mentioned)} address(es) belonging to the cluster, e.g. {mentioned[0][:12]}…"))

    src = set().union(*(selectors_from_source(p.text) for p in identity_posts if "function" in p.text))
    codes = [selectors_from_bytecode(c) for a, c in bytecodes.items() if a in cluster_wallets]
    if src and codes:
        sim = max(similarity(src, c) for c in codes)
        out.append(Signal("bytecode", 10.0 if sim >= 0.6 else 1.0,
                          f"posted code shares {sim:.0%} of its function selectors with the cluster's contract"))

    for t in cluster_tx:
        msg = decode_message(t.input_data) if t.input_data not in ("", "0x") else None
        if msg and any(h in msg.lower() for h in handles):
            out.append(Signal("onchain_message", 30.0, f'cluster tx {t.tx_hash[:12]}… carries the message "{msg[:80]}"'))
            break
    return out


def link_for(cluster_id: int, identity: str, signals: list[Signal], age_s: int = 0, now_ts: int | None = None) -> Link:
    return Link(f"{cluster_id}:{identity}", cluster_id, identity, decay(posterior(signals), age_s), signals,
                updated_ts=int(time.time()) if now_ts is None else now_ts)


def label(score: float, status: str) -> str:
    if status in ("confirmed", "rejected"):
        return status
    return "high" if score >= 0.8 else "medium" if score >= 0.5 else "low"


def explain(link: Link, polish: bool = False) -> str:
    reasons = "; ".join(s.detail for s in sorted(link.signals, key=lambda s: -s.lr)) or "no supporting evidence yet"
    text = f"{link.status.capitalize()} ({round(link.score * 100)}%): {link.identity} ↔ cluster {link.cluster_id}. Because: {reasons}."
    if polish:
        summary = llm.complete("In one plain sentence for an investigator, summarise this finding without adding "
                               f"any facts (refer to people as 'they'):\n{text}", max_tokens=80)
        if summary:
            return f"{summary} — {text}"
    return text
