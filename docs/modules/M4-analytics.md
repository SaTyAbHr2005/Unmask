# M4: Analytics (the math layer)

## In one sentence
M4 treats the blockchain as a **matrix and a graph**, and runs **statistical tests** to answer five questions: *Which wallets belong to the hacker? Where did the money cross chains? Is this wallet a bot? Which time zone does the owner live in? Does this person's posting line up with the wallet's activity?*

## Why it exists
The hacker splits the money into hundreds of wallets, hides it in mixers, hops chains, and uses bots that act like normal traders. A human can't connect these by hand fast enough. Each technique below breaks one trick the hacker uses, and each one outputs **numbers** that M5 (Fusion) turns into evidence.

## Where it sits

```
 Transfers (M0/M1/M2) ─► features.py   ─► wallet × time matrix, behaviour vectors
                     ─► graph.py      ─► money-flow graph ─► link_bridges ─► cluster_wallets ─► attacker cluster
                     ─► funding.py    ─► who paid each wallet's gas         ──┘
                     ─► amounts.py    ─► split reconstruction, bridge matching
                     ─► behavior.py   ─► bot score, time zone
 Posts (M3) + txs    ─► latency.py    ─► "posts come minutes before transactions" test
 GitHub code + chain ─► bytecode.py   ─► "posted code = deployed exploit" test
                                          │
                                          ▼
                                    Fusion (M5)
```

## Files

| File | What it answers | Features |
|---|---|---|
| [features.py](../../backend/gt/analytics/features.py) | Activity over time and behaviour per wallet | #14, #15 |
| [graph.py](../../backend/gt/analytics/graph.py) | Money-flow graph, bridge links, wallet clusters | #16, #18 |
| [funding.py](../../backend/gt/analytics/funding.py) | Who paid each new wallet's gas fees | #19 |
| [amounts.py](../../backend/gt/analytics/amounts.py) | Which pieces add up to the stolen sum; which bridge deposit came out where | #9, #20 |
| [behavior.py](../../backend/gt/analytics/behavior.py) | Bot or human? Which time zone? | #21, #22 |
| [latency.py](../../backend/gt/analytics/latency.py) | Do this person's posts precede the hacker's transactions? | #17 |
| [bytecode.py](../../backend/gt/analytics/bytecode.py) | Does posted code match the deployed exploit contract? | #23 |

Also `config.usd(asset, amount)`: fixed demo prices (ETH = $3,000, stablecoins = $1, unknown tokens = `None`).

---

## 1. The ledger as a matrix (`features.py`)

**`activity_matrix(transfers, bucket_s=3600)`**: a table with one row per sending wallet and one column per hour; each cell holds how many transactions that wallet sent in that hour. This is the "blockchain as a mathematical matrix" the problem statement asks for, and the UI heatmaps read from it.

**`wallet_features(transfers)`**: one behaviour vector per wallet:

| Column | Meaning | Why it matters |
|---|---|---|
| `n_tx` | Transactions sent | Activity level |
| `mean_gas`, `std_gas` | Gas price used and how much it varies | Bots often use one fixed gas price |
| `round_frac` | Share of amounts that are "round" (0.1 precision) | Humans type 1.0 or 0.5; bots send 3.71946… |
| `mean_gap_s`, `cv_gap` | Average time between transactions and its variation | Bots act on a steady rhythm |
| `active_hours` | Distinct hours of day the wallet is active | Humans sleep |

Wallets with fewer than 3 transactions get empty (NaN) gap statistics instead of an error.

**Simulator:** 1,987 wallets × 82 hours, built in about 1 second.

## 2. Gas-funder tracing (`funding.py`), the trick most tools miss

Every brand-new wallet needs a little ETH to pay transaction fees before it can do anything. **Someone has to send that ETH.** The hacker's bot can create 300 fresh wallets, but they're all topped up by the same few "gas funder" wallets.

**`gas_funders(transfers)`** → `{wallet: funder}` when:
- the wallet's **first** incoming ETH is small (0.001–0.1 ETH, a gas top-up rather than a payment), **and**
- the wallet sends its first transaction **after** receiving it (it actually used the gas).

**The lower limit matters.** The hacker sprays 0.0001 ETH dust at innocent wallets. In testing, one innocent wallet whose first-ever ETH was that dust got treated as "funded by the hacker", which dragged its whole neighbourhood into the attacker cluster (precision fell to 0.22). Ignoring dust below 0.001 ETH fixed it: precision is back to 1.0 on every seed.

**`funding_clusters(funders, exclude)`** groups wallets that share a funder (union-find). Groups never join through hubs (exchanges, mixers), since thousands of strangers use those.

## 3. The money-flow graph and clustering (`graph.py`)

**`build_graph(transfers)`**: a directed graph where wallets are nodes and every transfer is an edge, carrying its time, asset, amount and kind.

**`link_bridges(G, transfers)`**: runs bridge matching (below) and adds a `bridge_link` edge from the depositor on chain A to the receiver on chain B, so the trail continues across chains.

**`cluster_wallets(G, funders, seeds, labels)`** → `{wallet: cluster id}`:
- **Cluster 0 = the attacker.** Start from the seed wallet (the one that received the stolen funds):
  1. **Follow the money forward** up to 4 hops, **only along edges carrying ≥ $100**, so dust and gas payments don't spread suspicion. Contract deploys, test calls and bridge links are always followed.
  2. **Never pass through a hub** (exchange, mixer, bridge, DEX).
  3. **Pull in every wallet sharing a gas-funding group** with a member. This is how wallets **coming out of the mixer** get caught: the mixer breaks the money trail, but their gas still came from the hacker's funders.
  4. Repeat until nothing new joins.
- **Cluster −1 = hubs** (labeled addresses). They're never clustered.
- **Clusters 1, 2, 3… = everyone else**, grouped into communities by the Louvain algorithm (wallets that trade a lot with each other).

**Accuracy on the simulator (seeds 6–12):**

| | Precision | Recall |
|---|---|---|
| Without bridge links | **1.00** | 0.81–0.83 (misses the ~90 wallets reached via Arbitrum) |
| **With bridge links** | **1.00** | **0.998–1.00** |

The graph has 2,038 wallets and 9,143 edges; clustering takes about 0.2 s.

## 4. Money is conserved (`amounts.py`)

**`match_split(parent_amount, children)`**: which pieces add up to the original amount (±0.5%)? This is the "subset-sum" problem. It searches only the 25 largest pieces, using a meet-in-the-middle method (two halves of about 4–8 thousand sums each), so it finishes well under a second even when given 300 pieces. Returns `None` when no combination fits.

**`match_bridges(outs, ins)`**: a bridge deposit on chain A reappears on chain B:
- with the **same asset**,
- **0–0.3% smaller** (the bridge fee),
- **1–30 minutes later**.

Each withdrawal is matched to at most one deposit, closest in time first. Confidence = 1 − ½·(fee / max fee) − ½·(delay / max delay).

**Simulator:** 652 of 653 bridge transfers matched across seeds 6–12.

## 5. Behaviour fingerprints (`behavior.py`)

**`bot_score(gaps, amounts)`** → 0 (human) to 1 (machine), the average of up to three tests:
1. **Timing:** human activity is roughly random (Poisson, so gaps are exponential). A KS test checks how *un*-random the gaps are.
2. **Roundness:** humans use round numbers; bots don't.
3. **Benford's law** (only with ≥ 20 amounts): in natural money data the first digit is "1" about 30% of the time, "9" under 5%. Machine-generated amounts often break this.

Returns `None` with fewer than 10 gaps (not enough evidence).
**Results:** hacker's main wallet **0.93**; a human-like sample **0.40**.

**`infer_utc_offset(timestamps)`** → `(offset, confidence)`: people are active about 09:00–23:59 local time and asleep otherwise. It builds the hour-of-day histogram and tries every time zone from UTC−11 to UTC+12, keeping the one whose waking window fits best. Confidence is that fit (correlation, 0–1). It needs at least 15 timestamps.
**Result:** the hacker comes out as **UTC+9, confidence 0.75**, which is correct.
(UTC−12 and UTC+12 look identical by hour of day, so only 24 distinct offsets are tested.)

## 6. Time-delta latency test (`latency.py`), the core of the problem statement

*"A forum user posted at 2:09 and the wallet moved at 2:13."* Once is a coincidence; twenty times is evidence. This test turns that into a number.

**`latency_test(post_times, tx_times, max_lag_s=900)`**:
1. **Hit rate:** the share of posts followed by a hacker transaction within 15 minutes.
2. **Null test:** shift all the posts by a random amount in time (keeping the person's posting rhythm) and recompute the hit rate, 500 times.
3. **p-value:** how often a random shift does as well as reality. Small p means not a coincidence.

Returns `hit_rate`, `p_value`, `median_lag_s`, `null_hit_rate`, `n_posts`. It's deterministic (fixed seed), vectorised, and handles 1,000 posts × 5,000 transactions in under a second.

**`latency_lr(p)`** turns the p-value into evidence strength for M5: p < 0.01 gives 20×, p < 0.05 gives 5×, otherwise 1× (no evidence).

**Simulator results:**

| Author | Hit rate | Random-shift hit rate | p-value |
|---|---|---|---|
| `ghostfox` (hacker, forum) | 26/26 = 100% | 43% | **0.002** |
| `fox_ghost` (hacker, Telegram) | 6/6 = 100% | 42% | 0.12 (too few posts alone) |
| normal users | 0–20% | 20–29% | 0.8–1.0 |

That's why M5 runs this test per **identity** (all of one person's accounts together, from M3), not per account.

## 7. Bytecode similarity (`bytecode.py`)

Every contract function has a 4-byte "selector" (the first 4 bytes of the keccak hash of `name(types)`), and compiled contracts contain each selector after a `PUSH4` instruction.
- **`selectors_from_bytecode(code)`** walks the bytecode instruction by instruction, collecting every PUSH4 value. It skips data bytes so they're never misread as instructions.
- **`selectors_from_source(solidity)`** finds `function name(params)`, normalises types (`uint` → `uint256`, drops `payable`, `memory` and parameter names) and hashes them.
- **`similarity(a, b)`** is the overlap between the two sets (Jaccard, 0–1).

**Simulator:** the exploit code `gh0stfox` pushed to GitHub matches the deployed exploit contract **1.0** (3 of 3 functions).

## How to test
From `HackForge`:

```bash
py -3.11 -m pytest backend/tests/test_features.py backend/tests/test_clustering.py backend/tests/test_amounts.py backend/tests/test_behavior.py backend/tests/test_latency.py backend/tests/test_bytecode.py -q
```

37 tests, plus the full suite (101 tests across M0–M4).

## Limitations (honest)
- **The simulator is kinder than reality.** Perfect scores here show the methods work as designed, not that real hacks will score 1.0. Real launderers vary gas sources, use many bridges, and wait days.
- Bridge matching assumes one deposit maps to one withdrawal of the same asset. Swaps during bridging, or batched withdrawals, won't match.
- Subset-sum looks only at the 25 largest pieces.
- Time-zone inference assumes a normal sleep pattern. Night-shift operators or teams across zones will confuse it, which shows up as low confidence.
- Bytecode matching ignores functions with struct or tuple parameters, and can't see through proxy contracts.
- Louvain community numbers for normal wallets are for display only; they aren't used as evidence.

## What later modules use from M4
- **M5 Fusion:** `latency_test` + `latency_lr` (time-delta signal), `infer_utc_offset` (time-zone match signal), `bytecode.similarity` (code signal), the attacker cluster (which wallets to test)
- **M6 Defense:** the graph and attacker cluster (exit prediction, holdings), `usd()`, bot scores
- **M7/M8:** activity matrix (heatmap), graph (flow view), bridge matches (Sankey)
