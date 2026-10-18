# Results: Unmask against naive baselines

These are the numbers on the Results and Trade-offs slides. Re-run them with `py -3.11 -m gt.benchmark` from `backend/` (about 3 minutes).

Accuracy is measured on simulated attacks, because each one comes with an **answer key** (the attacker's real wallets and username). Real hacks don't publish one. Each attack number is a different attacker: name, amount, time zone, wallet count.

## 1. Finding the attacker's wallets (20 simulated attacks)

| Method | Precision (flagged wallets that really are the attacker's) | Recall (attacker's wallets found) |
|---|---|---|
| **Unmask** (money graph + shared gas funders + bridge matching) | **100%** | **99.98%** |
| Follow the money 1 hop from the first stolen-money wallet | 90.7% | 57.5% |
| Follow the money 2 hops | 68.3% | 57.8% |

## 2. Naming the right person (same 20 attacks)

| Method | Plain attacks | With a decoy posting 5× more than the attacker |
|---|---|---|
| **Unmask** (latency permutation test + Bayesian clues) | **20 / 20** | **20 / 20** (the decoy scored 0.5–2.9%) |
| Count raw "post, then a move within 15 min" coincidences | 20 / 20 | 16 / 20 |
| Name the busiest poster | 20 / 20 | **0 / 20** |

An honest note: on plain simulated attacks the simple rules also win, because our simulated attacker happens to be the busiest poster. That test was too easy. The decoy test (a chatty account posting at random times) is the fair one: only a test that accounts for how often someone posts holds up.

## 3. Load (attack 7, laptop)

| Size | Transfers | Analysis | Accuracy |
|---|---|---|---|
| 1× | 9,055 | 1.1 s | precision 100%, right person |
| 10× | 90,073 | 36.6 s | precision 100%, right person |

On the live free server (about a tenth of a CPU core) attack 7 takes about 40 s to load and analyse.

## 4. Real hacks against the public record

| Hack | Unmask | Public record |
|---|---|---|
| Euler, Mar 2023 | $191.6M traced, $189.4M given back to Euler | ~$197M, nearly all returned |
| Harmony, Jun 2022 | $98.1M into Tornado Cash, 857 deposits of 100 ETH | 85,700 ETH (~$98M) by 2 July |
| Beanstalk, Apr 2022 | $74.4M traced, $74.3M into Tornado | ~$76M kept |
| KyberSwap, Nov 2023 | $33.5M traced on 3 chains | ~$48M |

Details: [data/replays/README.md](../data/replays/README.md).
