# M2: Chain Ingestion (getting blockchain data in, cleanly)

## In one sentence
M2 **brings real blockchain data into the system**: past hacks from Etherscan and live activity from Alchemy. It **cleans that data** so every later module gets the same tidy `Transfer` objects the simulator produces.

## Why it exists
The analytics (M4) must not care whether a transfer came from the simulator, a past hack or the live chain. Real APIs return messy data: mixed-case addresses, times as strings, amounts in wei, rate-limit errors, timeouts. M2 absorbs all of that at the boundary.

## Where it sits

```
                    ┌── normalize.py  (clean addresses, times, decode hidden messages, tag mixer/bridge/DEX moves)
Etherscan API ──► etherscan.py ──┐
                                  ├──► Transfer objects ──► MongoDB (M0) ──► analytics (M4)
Alchemy API ────► live.py ───────┘
                    └── labels.py  (which addresses are exchanges, mixers, bridges…)
```

## Files

| File | What it does | Features covered |
|---|---|---|
| [normalize.py](../../backend/gt/chain/normalize.py) | Cleans addresses and times, decodes hidden text, classifies transfer type | #4, #10, #11, #12 |
| [labels.py](../../backend/gt/chain/labels.py) | Loads known-address lists from CSV files | #10 |
| [etherscan.py](../../backend/gt/chain/etherscan.py) | Etherscan V2 client (cache, retry, throttle) and the past-hack replay loader | #7, #13 |
| [live.py](../../backend/gt/chain/live.py) | Live polling of watched wallets via Alchemy, plus a mempool count | #7, #8 |
| [data/labels/known.csv](../../data/labels/known.csv) | Seed list of known addresses | — |
| [data/replays/README.md](../../data/replays/README.md) | How to add a real past hack | — |

---

## 1. `normalize.py`: the cleaning gate

| Function | What it does | Example |
|---|---|---|
| `norm_addr(a)` | Trim and lowercase. `None` becomes `""`. | `" 0xAbC "` → `"0xabc"` |
| `to_utc(ts)` | Any time format → `int` UTC seconds. Bad input → `None` (never 0, which would mean 1970). | `"2026-10-17T02:14:00+05:30"`, `"Fri, 17 Oct 2026 02:14:00 GMT"`, `"1760000000"`, `1760000000` all work. A time without a zone is treated as UTC. |
| `decode_message(input_data)` | Turns hex call data into readable text **only if it really is text** (at least 8 characters, at least 70% printable). Hackers and victims negotiate this way. | `0x636f6e74…` → `"contact me for bounty"`; normal contract calls like `0xa9059cbb…` → `None` |
| `classify(t, labels)` | Works out what kind of move a transfer is, from the labels | Sent to a mixer → `mixer_in`; from a mixer → `mixer_out`; to a bridge → `bridge_out`; from a bridge → `bridge_in`; to or from a DEX → `swap`. Types already set (`deploy`, `test_call`, …) are kept. |

## 2. `labels.py`: known addresses
`load_labels(folder)` reads every `*.csv` in `data/labels/` (columns `address,label`; lines starting with `#` are comments) and returns `{address: label}` with lowercase addresses.

Label values: `mixer`, `bridge`, `dex`, `victim`, `exchange:<Name>`.

Labels matter in three ways:
- **Exchanges and mixers are hubs.** Millions of people use them. If the graph treated "both sent money to Binance" as a connection, everyone would end up in one giant cluster. Labeled hubs are never expanded or merged through.
- **Exchanges are exits**, where stolen money becomes cash. That drives exit prediction (M6).
- **Mixers and bridges** turn plain transfers into `mixer_in` / `bridge_out` and so on.

The seed file holds 4 Tornado Cash ETH pools (listed by OFAC in 2022) and one Binance hot wallet. **Check each one on etherscan.io before relying on it**, and add more as you find them (exchange hot wallets, bridges, OFAC-listed addresses).

## 3. `etherscan.py`: past hacks (replay mode)

### `get(params, chainid=1)`: one safe API call
Etherscan's free tier allows 5 calls per second. `get` makes our calls safe:
- **Throttle:** at most 4 calls per second.
- **Retry with backoff:** on HTTP 429, a "rate limit" message, a 5xx error or a timeout, it waits 1 s, 2 s, 4 s, then 8 s and tries again.
- **Never crashes:** after 5 failed attempts it logs a warning and returns `[]`, so the pipeline continues with what it has.
- **Disk cache:** every successful answer is saved in `data/cache/`. The same question never hits the API twice, which saves quota and makes a demo re-run instant. Failures are **not** cached. Your API key is **never** written to the cache.
- "No transactions found" counts as a normal empty answer: no retry, no warning.

### Converters
| Function | Returns | Detail |
|---|---|---|
| `txlist(address, chainid)` | ETH transfers of that wallet (in and out) | Converts wei to ETH and wei gas to gwei. **Contract creation** becomes `kind="deploy"` with the new contract as `to_addr`. **Failed transactions are dropped** (they moved no money). |
| `tokentx(address, chainid)` | Token transfers (USDT, USDC, …) | Amount = value / 10^decimals. The id is `hash:logIndex`, so several tokens in one transaction don't overwrite each other. |
| `get_code(address, chainid)` | Contract bytecode (hex) | Used to compare the exploit contract with code found on GitHub (M4) |

Chain ids: 1 = `eth`, 42161 = `arb`, 10 = `op`, 56 = `bsc`, 137 = `polygon`, 8453 = `base`. One Etherscan V2 key works for all of them.

### `load_replay(path, max_transfers=3000)`: rebuild a past hack
Reads a small JSON file (see [data/replays/README.md](../../data/replays/README.md)) with the attacker's **seed addresses**, then **follows the money forward**:
1. Fetch every transfer of the seed wallets (incoming ones too, which reveals who funded their gas).
2. Take every wallet the seeds **sent** money to, and fetch those.
3. Repeat for `hops` levels.
4. **Never expand labeled hubs** (exchanges, mixers, bridges); they would pull in millions of unrelated transactions.
5. Stop at `max_transfers` so a demo can't run away with the API quota.
6. Fetch the bytecode of any contract the wallets deployed.

Returns `(transfers, {contract_address: bytecode})`, in the same shape as the simulator.

## 4. `live.py`: live mode
| Function | What it does |
|---|---|
| `poll_once(watch, last_block)` | Reads the newest block number, then asks Alchemy (`alchemy_getAssetTransfers`) for all ETH and token transfers **from or to** each watched wallet since `last_block`. A transfer seen from both sides is kept once. Returns `(new_transfers, newest_block)`. On any network or API error it returns `([], last_block)`, so nothing is lost and the next poll picks up the same range. |
| `pending_count(watch)` | Lite mempool view: looks at the pending block and counts transactions touching watched wallets that are **not yet confirmed**. Returns 0 on error. |
| `live_loop(conn, watch, interval_s=12, queue=None)` | Runs forever in the background: poll → save to MongoDB → push each new transfer onto a queue. The API (M7) streams that queue to the browser (SSE), so new transfers appear on screen live. It starts at the current block and **never falls back to block 0** if the first request fails (that would try to scan the entire chain). |

One Ethereum block arrives about every 12 seconds, hence `interval_s=12`.

## Keys needed (in `backend/.env`)
| Key | Used by | Without it |
|---|---|---|
| `ETHERSCAN_API_KEY` | Replay mode | Calls fail safely and return `[]`; replay shows nothing |
| `ALCHEMY_API_KEY` | Live mode | Polls return nothing; the simulator still works fully |

## How to test
From `HackForge`:

```bash
py -3.11 -m pytest backend/tests/test_normalize.py backend/tests/test_etherscan.py backend/tests/test_live.py -q
```

27 tests, all running **without internet** (fake HTTP and RPC clients). They cover: mixed-case addresses, every time format, hidden-message decoding, all classify directions, label merging; retry on 429, rate-limit message and timeout; giving up safely; cache hits; failures not cached; API key kept out of the cache; row conversion, including contract creation and failed transactions; replay hop limit, hub stopping, transfer cap and bytecode fetch; live dedupe, token ids, no-new-block, timeout, mempool count, the loop writing to DB and queue, and the no-genesis-scan guard.

## Not done yet / limitations
- **No real replay file yet.** It needs your Etherscan key, plus attacker addresses copied from a public post-mortem and checked on etherscan.io.
- Live mode and Etherscan have **only been tested with fakes**. Run them once with real keys.
- Live mode watches Ethereum mainnet only (one Alchemy URL). Replay supports many chains.
- `txlist`/`tokentx` read the first 1,000 transfers per wallet. Very busy wallets are cut off on purpose.
- Live token transfers use Alchemy's `uniqueId` as the id, while Etherscan uses `hash:logIndex`. If the same token transfer comes from both sources, it could be stored twice (rare).

## What later modules use from M2
- M4 analytics: cleaned `Transfer`s, `kind` values and labels
- M4 bytecode similarity: `get_code`
- M5 explanations: `decode_message` (on-chain message signal)
- M6 exits and freezability: exchange labels
- M7 API: `load_replay` behind `POST /api/replay/{name}`, `live_loop` behind `GET /api/live`
