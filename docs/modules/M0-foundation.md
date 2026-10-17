# M0: Foundation (data contract + database)

## In one sentence
M0 decides **what our data looks like** and **where it is stored**, so all the other modules can work on the same objects without arguing about formats.

## Why it exists
Four people build different parts at the same time: chain, OSINT, math, UI. If the chain person writes `"From"` with a capital F, the time as a string and the amount in wei, while the math person expects lowercase, unix seconds and ETH, integration breaks at hour 12. M0 fixes the format once, at hour 0, and every module follows it.

## Where it sits

```
 Simulator (M1) ─┐
 Etherscan (M2) ─┼──► schema objects ──► db.insert ──► MongoDB ──► db.select ──► Analytics (M4) ──► API (M7) ──► UI (M8)
 Alchemy  (M2) ──┤
 OSINT    (M3) ──┘
```

## Files

| File | What it does |
|---|---|
| [backend/gt/schema.py](../../backend/gt/schema.py) | The 6 data shapes (dataclasses) that every module passes around |
| [backend/gt/db.py](../../backend/gt/db.py) | Save and load those shapes in MongoDB |
| [backend/gt/config.py](../../backend/gt/config.py) | Reads `.env` keys and holds shared constants |
| [backend/.env.example](../../backend/.env.example) | List of every secret or key the app can use (values left empty) |
| [backend/requirements.txt](../../backend/requirements.txt) | Python libraries (Render installs these on deploy) |
| [backend/pyproject.toml](../../backend/pyproject.toml) | Tells pytest where the code and tests are |
| [.gitignore](../../.gitignore) | Keeps secrets, caches and build output out of git |

## The data shapes (`schema.py`)

### `Transfer`: one movement of money on a blockchain
| Field | Meaning | Example |
|---|---|---|
| `tx_hash` | Unique id of the row. Token transfers use `hash:logIndex` because one transaction can move several tokens. | `0x9f…` |
| `chain` | Which blockchain | `eth`, `arb` |
| `ts` | Time, **unix seconds in UTC**, always an `int` | `1760000000` |
| `from_addr`, `to_addr` | Sender and receiver, **always lowercase** | `0xab12…` |
| `asset` | What moved | `ETH`, `USDT`, `USDC` |
| `amount` | How much, in normal units (1.5 ETH, not wei) | `1.5` |
| `gas_price_gwei` | Fee price paid. Bots often use one fixed value, which is a fingerprint. | `25.0` |
| `nonce` | The sender's transaction counter | `5` |
| `input_data` | Raw call data. Hackers sometimes hide text messages here. | `0x636f…` |
| `kind` | What type of move it was | `transfer`, `swap`, `mixer_in`, `mixer_out`, `bridge_out`, `bridge_in`, `deploy`, `test_call` |

### `OsintPost`: one piece of public text (forum post, Telegram message, GitHub commit, RSS item)
`post_id`, `source` (`forum`/`telegram`/`github`/`rss`), `author` (the handle), `ts` (UTC int), `text`, `url`.

### `Entity`: something useful found inside a post
An address, tx hash, IP, email, @handle or ENS name. `entity_id` is a hash of post + kind + value, so the same thing found twice is stored once.

### `Signal`: one piece of evidence linking a wallet group to a person
`name` (for example `time_delta`), `lr` (**likelihood ratio**: how many times more likely this evidence is if the link is true than if it's false), `detail` (a human-readable reason).

### `Link`: "wallet cluster X probably belongs to identity Y"
`score` (probability 0–1), the list of `signals` that produced it, `status` (`suspected` / `confirmed` / `rejected`, set by a human analyst) and `evidence` hashes.

### `Alert`: something a human must approve before it is sent
`kind` (`exit`, `prewarn`, `freeze`, `decoy`), `target`, `message`, `status` (`pending` → `approved` → `sent`, or `dismissed`).

`ALL` lists every shape that gets its own database collection.

## The database (`db.py`)

We use **MongoDB**:
- **Deployed:** a free **MongoDB Atlas M0** cluster. Set `MONGODB_URI` in `.env` on Render.
- **Tests and offline demo:** if `MONGODB_URI` is empty, it uses **mongomock**, a fake MongoDB that lives in memory. No server is needed, so the demo works on a laptop with no internet.

| Function | Input → Output | Notes |
|---|---|---|
| `connect(uri=None)` | → database handle | Empty URI or `mongomock://` gives the in-memory DB. Each call to mongomock is a fresh, empty DB. |
| `insert(conn, rows)` | list of dataclasses → count | **Upsert**: the first field is the id (`_id`), so inserting the same transaction twice keeps one copy. An empty list returns 0. |
| `select(conn, cls, query=None)` | class + Mongo query dict → list of dataclasses | Example: `select(conn, Link, {"identity": "bob"})`. It rebuilds nested `Signal` objects inside `Link`. |
| `clear(conn)` | — | Deletes all data collections. Used before loading a new scenario. |
| `put_meta` / `get_meta` | key → any JSON value | A small key-value store for things like "the current scenario's labels" or "last results". It survives `clear()`. |

One collection per class, named by the lowercase class name: `transfer`, `osintpost`, `entity`, `link`, `alert`, plus `meta`.

## Config (`config.py`)
- `env("NAME")` reads a key from `.env`. An empty value counts as "not set" (returns `None`).
- `DATA_DIR` is the absolute path to `HackForge/data`. It works no matter which folder you start the server from, which matters on Render.
- Constants: `ETH_USD = 3000` (fixed price, so all USD numbers are reproducible), `PRIOR = 0.01` (starting belief for a link), `HALF_LIFE_S = 6h` (how fast confidence fades), `DB_NAME = "unmask"`.

## Two rules every module must follow
1. **Addresses are lowercase**, so `0xAbC` and `0xabc` are the same wallet.
2. **Times are `int` unix seconds in UTC**. Never store a string time or a local time.

Both are enforced at the entry points (M2 `normalize.py`, M3 `extract.py`), so nothing downstream has to worry about them.

## How to test
From the `HackForge` folder:

```bash
py -3.11 -m pytest backend/tests/test_db.py -q
```

4 tests: save and load a transfer, nested signals inside a link, upsert and empty insert, clear plus meta.

## Limitations
- The real-MongoDB write path (`bulk_write`) runs only against Atlas and has not been tested yet. Tests use mongomock, which needs a simpler per-row loop because mongomock 4.3 doesn't support the newer bulk API. Run one simulate on Atlas after setting `MONGODB_URI` to confirm it works.
- `ETH_USD` is a fixed number, not a live price. That's on purpose, for reproducible demos.
