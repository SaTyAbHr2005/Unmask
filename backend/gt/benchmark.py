"""Unmask against naive baselines, on simulated attacks that come with an answer key (the numbers in the slides).

    py -3.11 -m gt.benchmark          (from backend/; about 3 minutes)

1. Wallets: Unmask's cluster vs "follow the money 1 / 2 hops from the first stolen-money wallet".
2. Identity: Unmask's top suspect vs "busiest poster" and "most raw post-then-move coincidences",
   then again with a decoy account posting 5x more than the attacker at random times.
3. Load: attack 7 at 1x and 10x the wallets."""
import collections
import statistics
import time

import numpy as np

from gt import db
from gt.osint.extract import make_post
from gt.pipeline import _default_seeds, load_scenario, run
from gt.simulator import evaluate, simulate, variant

SEEDS = range(1, 21)


def _unmask(s, name):
    conn = db.connect("mongomock://")
    load_scenario(conn, s, name=name)
    r = run(conn)
    cluster = {w for w, k in r.clusters.items() if k == 0}
    return cluster, (r.links[0].identity.split(":", 1)[1] if r.links else None)


def _hops(s, n):
    out = collections.defaultdict(set)
    for t in s.transfers:
        if t.amount > 0 and t.to_addr not in s.labels:
            out[t.from_addr].add(t.to_addr)
    found = set(_default_seeds(s.transfers, s.labels))
    for _ in range(n):
        found |= {b for a in found for b in out[a]}
    return found


def _naive_people(s):
    authors = collections.Counter(p.author for p in s.posts)
    moves = np.array(sorted(t.ts for t in s.transfers if t.from_addr in s.truth.attacker_wallets))

    def coincidences(a):          # posts followed by an attacker move within 15 min, no significance test
        ts = np.array([p.ts for p in s.posts if p.author == a])
        i = np.searchsorted(moves, ts, side="right")
        ok = i < len(moves)
        return int(((moves[np.minimum(i, len(moves) - 1)] - ts) <= 900)[ok].sum())
    return authors.most_common(1)[0][0], max(authors, key=coincidences)


def main():
    wallets = collections.defaultdict(list)
    people = collections.Counter()
    for seed in SEEDS:
        s = simulate(seed=seed, **variant(seed))
        cluster, handle = _unmask(s, f"sim {seed}")
        for name, found in (("unmask", cluster), ("1 hop", _hops(s, 1)), ("2 hops", _hops(s, 2))):
            e = evaluate(found, None, s.truth)
            wallets[name].append((e["precision"], e["recall"]))
        busiest, raw = _naive_people(s)
        people["unmask"] += handle in s.truth.attacker_handles
        people["busiest poster"] += busiest in s.truth.attacker_handles
        people["raw coincidences"] += raw in s.truth.attacker_handles

        # same attack plus a chatty decoy
        att = sum(p.author in s.truth.attacker_handles for p in s.posts)
        lo, hi = min(t.ts for t in s.transfers), max(t.ts for t in s.transfers)
        rng = np.random.default_rng(seed)
        s.posts = s.posts + [make_post("forum", "loudtrader", int(ts), "gm gm, market looking spicy today")
                             for ts in rng.uniform(lo, hi, 5 * att)]
        _, handle = _unmask(s, f"decoy {seed}")
        busiest, raw = _naive_people(s)
        people["decoy: unmask"] += handle in s.truth.attacker_handles
        people["decoy: busiest poster"] += busiest in s.truth.attacker_handles
        people["decoy: raw coincidences"] += raw in s.truth.attacker_handles
        print(f"attack {seed} done", flush=True)

    print("\nWallets (mean over 20 attacks)")
    for name, rows in wallets.items():
        print(f"  {name:8} precision {statistics.mean(p for p, _ in rows):.4f}  recall {statistics.mean(r for _, r in rows):.4f}")
    print("Right person named (out of 20)")
    for name, n in people.items():
        print(f"  {name:24} {n}")
    print("Load (attack 7)")
    for mult in (1, 10):
        s = simulate(seed=7, n_split=300 * mult, n_noise_wallets=1500 * mult)
        t = time.time()
        cluster, handle = _unmask(s, f"x{mult}")
        e = evaluate(cluster, handle, s.truth)
        print(f"  x{mult}: {len(s.transfers)} transfers, store + analyse {time.time() - t:.1f} s, "
              f"precision {e['precision']:.3f}, right person {e['handle_correct']}")


if __name__ == "__main__":
    main()
