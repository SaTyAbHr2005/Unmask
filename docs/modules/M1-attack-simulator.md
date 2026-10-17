# M1: Attack Simulator (synthetic hack with an answer key)

## In one sentence
M1 **creates a fake but realistic crypto hack**: stolen money, laundering wallets, mixers, bridges, bots, decoys, and the hacker's forum chatter. It also **keeps the answer key**, so we can measure how well our engine catches the thief.

## Why it exists
1. **A real hack won't happen during the demo.** The simulator gives a full attack on demand, with no API keys and no internet needed.
2. **Real hacks have no answer key.** With real data we can never say "we found 94% of the attacker's wallets", because nobody knows the true list. The simulator knows it, so we can show **precision, recall and F1** to the judges. Most teams can only show a pretty graph.
3. **Every analytics module can be tested.** Each trick the simulator plants is something a later module must detect. The tests check that they do.

## File
[backend/gt/simulator.py](../../backend/gt/simulator.py)

## Main functions

| Function | Input → Output |
|---|---|
| `simulate(seed=7, n_split=300, n_noise_wallets=1500, utc_offset=9, t0=1_760_000_000)` | → `Scenario` |
| `evaluate(predicted_wallets, predicted_handle, truth)` | → `{"precision", "recall", "f1", "handle_correct"}` |

- **`seed`**: the same seed always gives exactly the same attack, which makes the demo repeatable.
- **`n_split`**: how many pieces the stolen money is split into.
- **`utc_offset`**: the hacker's real time zone (default UTC+9). The engine should be able to guess this from the activity times.
- **`t0`**: the moment of the theft (unix seconds).

### What a `Scenario` contains
| Field | What's in it |
|---|---|
| `transfers` | Every blockchain transfer: attacker and normal users mixed together, sorted by time |
| `posts` | Every forum, Telegram and GitHub post: attacker and normal users mixed together |
| `labels` | Known addresses: `victim`, `mixer`, `dex`, `bridge`, `exchange:Exch-A`, `exchange:Exch-B` |
| `bytecodes` | Code of the exploit contract the hacker deployed |
| `truth` | **The answer key** (below). The engine must never read this; only `evaluate()` uses it. |

### The answer key (`Truth`)
`attacker_wallets` (every wallet the hacker controls), `attacker_handles` (`ghostfox`, `gh0stfox`, `fox_ghost`), `decoy_wallets` (innocent wallets the hacker sprayed dust at), `exit_exchanges` (`Exch-A`, `Exch-B`), `utc_offset`.

## The story the simulator writes (step by step)

| Step | What happens | Which module should catch it |
|---|---|---|
| **1. Preparation** (6 hours before) | A mixer pays a fresh "gas funder" wallet. The funder pays the hacker's main wallet and two more funders. The main wallet **deploys an exploit contract** and makes 3 **test calls**. | M6 pre-attack warning: mixer-funded wallet + deploy + test calls, **before** the theft |
| **2. Theft** | The victim protocol sends **14,000 ETH ($42M at $3,000)** to the main wallet. The main wallet then sends a transaction carrying the hidden text *"contact ghostfox on forum for bounty"*. | M2 `decode_message` finds the text; M5 links it to the `ghostfox` handle |
| **3. Split** | A bot splits the money into 300 **uneven** pieces (Dirichlet random shares). Before each new wallet gets its piece, a funder sends it **0.01 ETH for gas**. Gaps between actions are uniform 20–40 s, a robotic rhythm. | M4 gas-funder tracing (who paid the gas?) and M4 bot detection (timing too regular) |
| **4. Laundering routes** | Each piece takes one route: **40% mixer** (in, then out to a new wallet after 10–60 min, 0.3% fee); **30% bridge** (out on Ethereum, in on Arbitrum 2–15 min later, 0.1% fee); **30% DEX swap** to USDT. | M4 bridge matching (amount minus fee plus time window); M6 freezability (USDT can be frozen by Tether) |
| **5. Cash-out** | Mixer outputs gather in 5 **consolidation wallets**. Two send to **Exch-A**, one to **Exch-B**, one **keeps raw ETH** (can't be frozen), one **keeps USDT** (can be frozen). About 60% of the Arbitrum wallets deposit to Exch-B on Arbitrum. | M6 exit prediction and freezability scoring |
| **6. Noise** | 1,500 normal users make about 7,500 normal transfers: human-like amounts (often round numbers), random timing, their own time zones, some deposits to the same exchanges. | Everything: the engine must find the hacker **inside** this noise |
| **7. Decoys** | The hacker sends 0.0001 ETH "dust" to 20 innocent wallets and to 2 **look-alike addresses** (same first 6 and last 4 characters as the Exch-A address) to pollute the graph. | M6 decoy and poisoning filter |
| **8. OSINT chatter** | `ghostfox` posts on a forum **2–6 minutes before** 25 of the hacker's transactions, plus one post that mentions a laundering wallet's address. `fox_ghost` posts 6 times on Telegram the same way. `gh0stfox` pushed the exploit source code to GitHub 3 days earlier. All three write the same way (lowercase, "ur", "lol", "fr", "ngl"). 60 normal authors post at random times in normal English. | M4 time-delta test (posts come just before transactions), M3 stylometry (three handles are one person), M4 bytecode similarity (GitHub code matches the deployed contract), M3 address mention |

The hacker's own transactions all happen during **09:00–23:59 at UTC+9**, because people sleep. M4 time-zone inference should recover +9.

## What one default run produces (seed 7)
- 9,055 transfers: 8,450 transfer, 164 swap, 130 mixer_out, 129 mixer_in, 89 bridge_out, 89 bridge_in, 3 test_call, 1 deploy
- 571 posts: 338 forum, 232 Telegram, 1 GitHub. Of these, 26 are by `ghostfox` and 6 by `fox_ghost`.
- 528 attacker wallets, 22 decoys
- Runs in about 0.2 seconds

## How `evaluate` scores us
- **Precision** = of the wallets we flagged, how many really are the hacker's (do we accuse innocent people?)
- **Recall** = of the hacker's real wallets, how many we found (did we miss any?)
- **F1** = one number that balances both
- **handle_correct** = did we name the right online identity?

An empty prediction scores 0, not an error.

## How to try it
From `HackForge/backend`:

```bash
py -3.11 -c "from gt.simulator import simulate; s = simulate(); print(len(s.transfers), len(s.posts), len(s.truth.attacker_wallets))"
```

Tests, from `HackForge`:

```bash
py -3.11 -m pytest backend/tests/test_simulator.py -q
```

8 tests: same seed gives the same attack; the split adds up to exactly 14,000 ETH; every laundering trick appears; evaluate scores perfect, partial and empty predictions correctly; tx hashes are unique and addresses lowercase; the hacker acts only during waking hours; at least 90% of ghostfox's posts come 0–15 min before one of the hacker's transactions.

## Limitations (on purpose)
- Gas fees aren't deducted from balances. The 0.01 ETH gas payments are just markers for gas-funder tracing.
- Arbitrum wallets have no gas-funder trail. They're linked back only through bridge matching, which is a deliberate test for M4.
- If you pick an unusual `utc_offset`, the time-zone pushing can move preparation steps close to `t0`. The default (+9) has been checked.
- All addresses, names and the GitHub URL (`github.example`) are fake. Never put real people's names into a scenario.
