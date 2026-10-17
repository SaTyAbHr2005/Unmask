# Unmask — Quantitative OSINT Blockchain Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A 14-hour hackathon build that fuses OSINT text (forums, Telegram, GitHub) with blockchain transaction data, links anonymous wallets to identities with explainable confidence scores, predicts where stolen funds will cash out, and alerts the parties who can freeze them.

**Architecture:** Python backend (FastAPI + pandas/NetworkX/scipy) writes everything into MongoDB (one database `unmask`, one collection per dataclass). Three data modes feed the same pipeline: **Simulator** (synthetic attack with ground truth — the demo backbone, works offline), **Replay** (a real past hack pulled from Etherscan), **Live** (Alchemy stream). A React + Vite frontend reads JSON endpoints and renders graph / timeline / Sankey / heatmap / report.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, pandas, numpy, scipy, networkx ≥3.0, scikit-learn, rapidfuzz, httpx, feedparser, python-dotenv, eth-hash[pycryptodome], telethon (optional), pytest · Node 22+, React, Vite, TypeScript, cytoscape, echarts, echarts-for-react · MongoDB (pymongo; mongomock for tests/offline) · Deploy: MongoDB Atlas M0 (free) + Render free web service (backend) + Vercel (frontend).

**Spec:** The problem statement "Ghost Attacks" plus the decisions made in planning chat (2026-10-17). Feature numbers `#1–#44` refer to the **Feature Map** at the end of this file.

## Global Constraints

- **Zero cost.** Only free tiers: Alchemy, Etherscan API V2, GitHub REST, Groq or Gemini, Telegram API, Discord webhook / Telegram bot. No paid service, no card-required service.
- **Offline-first demo.** With an empty `.env`, `simulate → run → UI` must work end to end. Every external call (LLM, APIs) has a non-network fallback.
- **Secrets** live only in `backend/.env` (gitignored). `.env.example` lists names with empty values. Never commit or paste keys.
- **All timestamps are `int` unix seconds UTC.** Convert at ingestion; nothing downstream sees strings or local time.
- **All addresses are lowercase `0x…` strings.** Normalize at ingestion.
- **Amounts are `float` in token units** (not wei). USD value for stablecoins = amount; for ETH use one constant `ETH_USD` in `config.py`.
- **Demo identities are synthetic.** Never attach a real person's name to a real wallet in the demo. Replay mode shows wallet clustering and exits only.
- **Every attribution is `suspected` until a human confirms it.** Nothing leaves the system (alert/webhook) without a human approval click (#42).
- **Database: MongoDB.** `MONGODB_URI` from `.env` (Atlas M0 free cluster in deployment). If `MONGODB_URI` is unset or `mongomock://`, use in-memory `mongomock` — tests and the offline demo need no server. DB name `unmask`. Everything persistent goes in Mongo (deployed disk is ephemeral); `data/cache/` is only a best-effort HTTP cache.
- Every function parameter named `conn` below is a `pymongo.database.Database`.
- Backend runs on `http://localhost:8000`, frontend on `http://localhost:5173`, API prefix `/api`.
- **Deployment:** backend → Render free web service (`render.yaml`, start `uvicorn gt.api:app --host 0.0.0.0 --port $PORT`, root `backend`); frontend → Vercel (root `frontend`, Vite preset). CORS origins from env `FRONTEND_ORIGINS` (comma-separated, default `http://localhost:5173`); frontend API base from `VITE_API_URL` (default `http://localhost:8000/api`). Render free sleeps after ~15 min idle (≈1 min cold start) — hit `/api/health` 2 min before demoing. The live poller only runs while the instance is awake.

## Review Focus

1. **Tiny / empty inputs** — a wallet with 1–2 transactions, a post with no entities, an empty DB. Expected: functions return `None`/empty results, never raise. Tests in Task 4a, 4d.
2. **Mixed-case or checksummed addresses** (`0xAbC…` vs `0xabc…`). Expected: treated as the same wallet everywhere. Test in Task 2a.
3. **Subset-sum blow-up** — 300 children for one parent. Expected: returns in < 1 s (candidates capped), may return `None`. Test in Task 4c.
4. **API rate limit / network failure** (HTTP 429, timeout). Expected: retry with backoff, then skip and log; pipeline continues with cached data. Test in Task 2b.
5. **Messy feed timestamps** (ISO strings with offsets, RFC-822 dates, missing dates). Expected: converted to UTC int; posts with no parseable time are dropped, not stored as 0. Test in Task 3a.

---

## Module Overview

| Module | What it delivers | Tasks | Features | Owner (4-person team) | Hours |
|---|---|---|---|---|---|
| **M0 Foundation** | Repo, schema contract, MongoDB store | 0 | — | Everyone | 0:00–0:45 |
| **M1 Attack Simulator** | Synthetic attack + OSINT + ground truth + accuracy metric | 1 | (demo backbone) | P3 Math | 0:45–2:30 |
| **M2 Chain Ingestion** | Normalize/decode/labels, Etherscan replay, live stream | 2a, 2b, 2c | #7–#13 | P1 Chain | 1–6 |
| **M3 OSINT Ingestion** | Extraction, collectors, stylometry | 3a, 3b, 3c | #1–#6 | P2 OSINT | 1–6 |
| **M4 Analytics** | Matrix, graph, clusters, gas funders, subset-sum, bots, rhythm, latency, bytecode | 4a–4f | #14–#23 | P3 Math (4f: P2) | 2:30–9 |
| **M5 Fusion** | Bayesian scores, decay, explanations, evidence, audit | 5a, 5b | #24–#27, #41, #43 | P3 Math | 7–10 |
| **M6 Defense** | Freezability, exit prediction, pre-attack, decoys, alerts + approval | 6a, 6b, 6c | #28–#32, #42 | P1 Chain (6c: P2) | 7–11 |
| **M7 Pipeline + API** | One `run()` + FastAPI endpoints + SSE | 7a, 7b | glue | P3 + P1 | 6–7 (checkpoint), 10–11 |
| **M8 Frontend** | Dashboard, Investigate, Report pages | 8a, 8b, 8c | #33–#40, #44 | P4 UI | 1–13 |
| **M9 Demo hardening** | Replay case, rehearsal, cut list | 9 | — | Everyone | 12–14 |

**Solo / 2-person order:** 0 → 1 → 4a → 4b → 4e → 5a → 6a → 7a → 7b → 8a → 8b → then everything else in task order.

**Hour 6 integration checkpoint (mandatory):** `POST /api/simulate` → `POST /api/run` → Dashboard graph renders. Whatever isn't merged by then waits.

**Cut order if behind:** 2c(mempool) → 2b(second chain) → 3c(usernames) → 8b(feedback buttons) → 4f → 4c(bridge matching). **Never cut:** 1, 4b, 4e, 5a, 6a, 8a.

---

## File Structure

```
HackForge/
  .gitignore                       # .env, data/, node_modules, .venv, __pycache__
  data/                            # cache/, replays/*.json, labels/*.csv  (cache gitignored)
  backend/
    requirements.txt
    .env.example
    gt/
      __init__.py
      config.py                    # env + constants (ETH_USD, thresholds)
      schema.py                    # dataclasses = THE contract between modules
      db.py                        # generic MongoDB upsert/find for dataclasses
      simulator.py                 # M1: synthetic scenario + evaluate()
      llm.py                       # optional LLM call, returns None if no key
      chain/
        normalize.py               # M2a: addr/time normalization, input-data decode, kind classify
        labels.py                  # M2a: exchange/mixer/bridge/OFAC label loading
        etherscan.py               # M2b: cached + backoff client, replay loader
        live.py                    # M2c: Alchemy polling + pending tx
      osint/
        extract.py                 # M3a: regex entity extraction + time parsing
        collectors.py              # M3b: RSS, GitHub, Telegram
        style.py                   # M3c: stylometry + username fuzzy match
      analytics/
        features.py                # M4a: activity matrix + wallet features
        graph.py                   # M4a/4b: graph build + clustering
        funding.py                 # M4b: gas funder tracing
        amounts.py                 # M4c: subset-sum + bridge matching
        behavior.py                # M4d: bot score + timezone inference
        latency.py                 # M4e: time-delta permutation test
        bytecode.py                # M4f: selector extraction + similarity
      fusion/
        score.py                   # M5a: signals → posterior, decay, explanation
        evidence.py                # M5b: evidence hashing + audit log
      defense/
        freeze.py                  # M6a: freezability + exit prediction
        guards.py                  # M6b: pre-attack warning + decoy filter
        alerts.py                  # M6c: alert queue, approval, webhook send
      pipeline.py                  # M7a: run everything, write results
      api.py                       # M7b: FastAPI app
    tests/
      test_<module>.py             # one file per task
  frontend/
    src/
      api.ts                       # typed fetch helpers
      App.tsx                      # router: / , /investigate , /report
      pages/Dashboard.tsx  Investigate.tsx  Report.tsx
      components/FlowGraph.tsx MoneyNow.tsx AlertQueue.tsx Timeline.tsx
                 Heatmap.tsx Sankey.tsx LinkCard.tsx
```

All backend commands below run from `HackForge/backend` with the venv active.

---

## M0 — Foundation

### Task 0: Scaffold, schema contract, MongoDB store

**Files:**
- Create: `.gitignore`, `backend/requirements.txt`, `backend/.env.example`, `backend/gt/__init__.py`, `backend/gt/config.py`, `backend/gt/schema.py`, `backend/gt/db.py`
- Test: `backend/tests/test_db.py`

**Interfaces:**
- Produces (every later task depends on these exact names):

```python
# gt/schema.py
from dataclasses import dataclass, field

@dataclass
class Transfer:
    tx_hash: str
    chain: str            # "eth" | "arb" | "sim"
    ts: int               # unix UTC seconds
    from_addr: str        # lowercase
    to_addr: str          # lowercase
    asset: str            # "ETH" | "USDT" | "USDC" | other symbol
    amount: float
    gas_price_gwei: float = 0.0
    nonce: int = -1
    input_data: str = "0x"
    kind: str = "transfer"  # transfer|swap|mixer_in|mixer_out|bridge_out|bridge_in|deploy|test_call

@dataclass
class OsintPost:
    post_id: str
    source: str           # "github" | "telegram" | "rss" | "forum" | "sim"
    author: str           # handle as seen on that source
    ts: int
    text: str
    url: str = ""

@dataclass
class Entity:
    entity_id: str        # sha1(post_id|kind|value)[:16]  (first field = primary key, so it must be unique)
    post_id: str
    kind: str             # "address" | "tx" | "ip" | "email" | "handle" | "ens"
    value: str

@dataclass
class Signal:
    name: str             # "time_delta" | "rhythm" | "address_mention" | "bytecode" | "onchain_message"
    lr: float             # likelihood ratio
    detail: str           # human-readable reason

@dataclass
class Link:
    link_id: str          # f"{cluster_id}:{identity}"
    cluster_id: int
    identity: str
    score: float          # posterior 0..1 after decay
    signals: list[Signal] = field(default_factory=list)
    status: str = "suspected"   # suspected | confirmed | rejected
    evidence: list[str] = field(default_factory=list)  # evidence hashes
    updated_ts: int = 0

@dataclass
class Alert:
    alert_id: str
    kind: str             # "exit" | "prewarn" | "freeze" | "decoy"
    target: str           # address or exchange name
    message: str
    status: str = "pending"     # pending | approved | sent | dismissed
    created_ts: int = 0

ALL = [Transfer, OsintPost, Entity, Link, Alert]   # Task 5b appends Evidence, AuditEntry
```

Primary key = first field of each dataclass. `Transfer.tx_hash` must be unique per row: token transfers use `f"{hash}:{logIndex}"`, simulator hashes are random 64-hex.

```python
# gt/db.py
def connect(uri: str | None = None, name: str = "unmask") -> Database
    # uri default = env MONGODB_URI; None/"" or "mongomock://" → mongomock.MongoClient(); else pymongo.MongoClient(uri)
def insert(conn, rows: list) -> int        # collection = type(rows[0]).__name__.lower(); _id = first field; bulk upsert (ReplaceOne, upsert=True); returns count; [] → 0
def select(conn, cls: type, query: dict | None = None) -> list   # find(query) → dataclass instances (drop _id; rebuild Signal inside Link.signals)
def clear(conn) -> None                    # drop every collection in schema.ALL (used by simulate/replay)
def put_meta(conn, key: str, value) -> None ; def get_meta(conn, key: str, default=None)   # collection "meta", {_id: key, value: ...}
```

- [ ] **Step 1: Init repo and venv**

```bash
git init
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install fastapi uvicorn pandas numpy scipy networkx scikit-learn rapidfuzz httpx feedparser python-dotenv "eth-hash[pycryptodome]" pymongo mongomock pytest
backend/.venv/Scripts/python -m pip freeze > backend/requirements.txt
```
`.env.example` keys: `FRONTEND_ORIGINS=http://localhost:5173 MONGODB_URI= ETHERSCAN_API_KEY= ALCHEMY_API_KEY= GITHUB_TOKEN= GROQ_API_KEY= GEMINI_API_KEY= TELEGRAM_API_ID= TELEGRAM_API_HASH= TELEGRAM_BOT_TOKEN= TELEGRAM_CHAT_ID= DISCORD_WEBHOOK_URL=`

- [ ] **Step 2: Write the failing test**

```python
# tests/test_db.py
from gt import db
from gt.schema import Transfer, Link, Signal

def test_roundtrip_transfer():
    conn = db.connect("mongomock://")
    t = Transfer("0xh", "sim", 100, "0xa", "0xb", "ETH", 1.5)
    assert db.insert(conn, [t]) == 1
    assert db.select(conn, Transfer) == [t]

def test_roundtrip_nested_lists():
    conn = db.connect("mongomock://")
    l = Link("1:bob", 1, "bob", 0.9, [Signal("time_delta", 20.0, "x")], evidence=["abc"])
    db.insert(conn, [l])
    assert db.select(conn, Link, {"identity": "bob"}) == [l]
```

- [ ] **Step 3: Run test — expect FAIL** (`python -m pytest tests/test_db.py -v` → ModuleNotFoundError)

- [ ] **Step 4: Implement `gt/schema.py` (as above), `gt/config.py`, `gt/db.py`**
  - `config.py`: `load_dotenv()`; expose `env(name) -> str | None`; constants `ETH_USD = 3000.0`, `PRIOR = 0.01`, `HALF_LIFE_S = 6*3600`, `DB_NAME = "unmask"`.
  - `db.py`: one table per dataclass, columns from `dataclasses.fields`; primary key = first field. `list`/nested dataclass fields stored as JSON text; `select` rebuilds `Signal` objects inside `Link.signals`.

- [ ] **Step 5: Run test — expect PASS**

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: scaffold, schema contract, mongodb store"`

---

## M1 — Attack Simulator (demo backbone)

### Task 1: Synthetic attack scenario + accuracy evaluation

**Files:**
- Create: `backend/gt/simulator.py`
- Test: `backend/tests/test_simulator.py`

**Interfaces:**
- Consumes: `Transfer`, `OsintPost` from Task 0.
- Produces:

```python
@dataclass
class Truth:
    attacker_wallets: set[str]     # every wallet the attacker controls
    attacker_handles: set[str]     # handles the attacker uses (forum + github + telegram)
    decoy_wallets: set[str]        # innocent wallets that received dust / look-alikes
    exit_exchanges: set[str]       # exchange names funds were sent to
    utc_offset: int                # attacker's real timezone

@dataclass
class Scenario:
    transfers: list[Transfer]
    posts: list[OsintPost]
    labels: dict[str, str]         # address -> "exchange:<name>" | "mixer" | "bridge" | "victim"
    bytecodes: dict[str, str]      # contract address -> runtime bytecode hex
    truth: Truth

def simulate(seed: int = 7, n_split: int = 300, n_noise_wallets: int = 1500,
             utc_offset: int = 9, t0: int = 1_760_000_000) -> Scenario
def evaluate(predicted_wallets: set[str], predicted_handle: str | None, truth: Truth) -> dict
    # {"precision": float, "recall": float, "f1": float, "handle_correct": bool}
```

- [ ] **Step 1: Write the failing tests**

```python
from gt.simulator import simulate, evaluate

def test_deterministic():
    a, b = simulate(seed=1), simulate(seed=1)
    assert a.transfers == b.transfers and a.posts == b.posts

def test_money_is_conserved_in_split():
    s = simulate(seed=2, n_split=50)
    main = next(iter(sorted(s.truth.attacker_wallets)))  # see step 3: main wallet sorts first ("0x00…")
    out = sum(t.amount for t in s.transfers if t.from_addr == main and t.asset == "ETH" and t.kind == "transfer")
    assert abs(out - 14_000) / 14_000 < 0.001        # 42M USD / ETH_USD 3000

def test_scenario_contains_every_signal_kind():
    s = simulate(seed=3)
    kinds = {t.kind for t in s.transfers}
    assert {"mixer_in", "mixer_out", "bridge_out", "bridge_in", "swap", "deploy", "test_call"} <= kinds
    assert any("exchange:" in v for v in s.labels.values())
    assert s.truth.decoy_wallets and s.bytecodes

def test_evaluate_perfect():
    s = simulate(seed=4)
    r = evaluate(s.truth.attacker_wallets, next(iter(s.truth.attacker_handles)), s.truth)
    assert r["precision"] == 1.0 and r["recall"] == 1.0 and r["handle_correct"]
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement `simulate`** with `random.Random(seed)` / `numpy.random.default_rng(seed)` only (deterministic). Timeline relative to `t0` (theft time):
  1. **Pre-attack (t0−6h … t0−1h):** mixer pays a fresh *gas funder* wallet (`mixer_out`); funder pays attacker main wallet; main deploys exploit contract (`deploy`, store its bytecode containing the selectors of 3 functions also present in the attacker's GitHub post); 3 `test_call`s.
  2. **Theft (t0):** victim protocol → main: 14,000 ETH. Main wallet address = `"0x00" + 38 hex` so it sorts first (used by tests).
  3. **Split:** main → `n_split` child wallets, amounts from Dirichlet(α=0.8) × 14,000. Each child first receives 0.01 ETH gas from one of **2 gas funders** (both funded by the first funder). Bot timing: intervals `uniform(20, 40)` s.
  4. **Routing per child:** 40% → `mixer_in` (mixer address) and later `mixer_out` to fresh wallets; 30% → `bridge_out` on `eth`, matching `bridge_in` on `arb` with fee 0.1% and delay `uniform(120, 900)` s; 30% → `swap` ETH→USDT.
  5. **Consolidation (t0+4h … t0+10h):** fresh wallets merge into 5 consolidation wallets → deposits to 2 exchange addresses (`labels["0x…"] = "exchange:Exch-A"` / `"exchange:Exch-B"`). Keep ~30% sitting in USDT (freezable) and ~20% in raw ETH.
  6. **Attacker activity** happens only in local hours 09–23 at `utc_offset`.
  7. **On-chain message:** one tx from main with `input_data = "0x" + "contact ghostfox on forum for bounty".encode().hex()`.
  8. **Decoys:** 20 dust transfers (0.0001 ETH) to random noise wallets + 2 look-alike addresses (same first 6 and last 4 chars as an exchange deposit address).
  9. **Noise:** `n_noise_wallets` humans: amounts lognormal with 30% rounded to 0.1/1/10, Poisson timing, random utc offsets, uniform gas around market.
  10. **OSINT:** attacker handles `ghostfox` (forum), `gh0stfox` (github), `fox_ghost` (telegram) — same writing quirks (lowercase, "ur", "lol", "fr"). 25 forum posts each 2–6 min **before** an attacker tx; 1 GitHub post with Solidity source of the exploit; 1 forum post mentioning a child wallet address. 60 noise authors posting at random times with random styles.
  - `evaluate`: precision/recall/F1 of `predicted_wallets` vs `truth.attacker_wallets`; `handle_correct = predicted_handle in truth.attacker_handles`.

- [ ] **Step 4: Run — expect PASS**
- [ ] **Step 5: Commit** — `feat: attack simulator with ground truth`

---

## M2 — Chain Ingestion

### Task 2a: Normalization, input-data decoding, labels (#10, #11, #12)

**Files:**
- Create: `backend/gt/chain/__init__.py`, `backend/gt/chain/normalize.py`, `backend/gt/chain/labels.py`, `data/labels/` (CSV `address,label`)
- Test: `backend/tests/test_normalize.py`

**Interfaces:**
```python
# normalize.py
def norm_addr(a: str) -> str                         # strip + lower; "" for None
def to_utc(ts: int | str) -> int | None              # int passthrough; ISO-8601 (any offset) / RFC-822 → UTC int; unparseable → None
def decode_message(input_data: str) -> str | None    # hex → utf-8 if ≥ 70% printable and ≥ 8 chars, else None
def classify(t: Transfer, labels: dict[str, str]) -> str   # kind from labels: to mixer→mixer_in, from mixer→mixer_out, to bridge→bridge_out, from bridge→bridge_in; else t.kind
# labels.py
def load_labels(folder: str = "data/labels") -> dict[str, str]   # merge all CSVs; keys normalized
```

- [ ] **Step 1: Failing tests**

```python
from gt.chain.normalize import norm_addr, to_utc, decode_message, classify
from gt.schema import Transfer

def test_checksum_and_lower_are_same_wallet():
    assert norm_addr(" 0xAbCDef ") == norm_addr("0xabcdef") == "0xabcdef"

def test_to_utc_offsets():
    assert to_utc("2026-10-17T02:14:00+05:30") == to_utc("2026-10-16T20:44:00Z")
    assert to_utc("Fri, 17 Oct 2026 02:14:00 GMT") == to_utc("2026-10-17T02:14:00Z")
    assert to_utc("not a date") is None

def test_decode_message():
    assert decode_message("0x" + b"contact me for bounty".hex()) == "contact me for bounty"
    assert decode_message("0xa9059cbb000000000000") is None   # ERC-20 call data, not text

def test_classify_mixer():
    t = Transfer("h", "eth", 1, "0xa", "0xmix", "ETH", 1.0)
    assert classify(t, {"0xmix": "mixer"}) == "mixer_in"
```

- [ ] **Step 2: Run — FAIL.** **Step 3: Implement.** `to_utc`: try `datetime.fromisoformat` (replace `Z` with `+00:00`), then `email.utils.parsedate_to_datetime`. Label CSVs: hand-collect for real data — Tornado Cash pool addresses (Etherscan "Tornado.Cash" label page), top exchange hot wallets, one bridge, OFAC SDN digital-currency addresses (free XML from treasury.gov). Verify each address on Etherscan before adding.
- [ ] **Step 4: Run — PASS.** **Step 5: Commit** — `feat: chain normalization and labels`

### Task 2b: Etherscan V2 client with cache + backoff, replay loader (#7, #13)

**Files:**
- Create: `backend/gt/chain/etherscan.py`, `data/replays/README.md`
- Test: `backend/tests/test_etherscan.py`

**Interfaces:**
```python
def get(params: dict, chainid: int = 1, *, http=None, sleep=time.sleep) -> list[dict]
    # GET https://api.etherscan.io/v2/api ; cache by sha256(params) in data/cache/*.json ;
    # on 429/timeout/"rate limit" message: retry 4× with sleep 1,2,4,8 s; then return [] and log.
def txlist(address: str, chainid: int = 1) -> list[Transfer]        # module=account action=txlist  (has gasPrice, nonce, input, timeStamp)
def tokentx(address: str, chainid: int = 1) -> list[Transfer]       # action=tokentx (USDT/USDC etc.), amount = value / 10**tokenDecimal
def get_code(address: str, chainid: int = 1) -> str                 # module=proxy action=eth_getCode
def load_replay(path: str, max_transfers: int = 3000) -> tuple[list[Transfer], dict[str, str]]
    # replay JSON: {"name": str, "seed_addresses": [..], "chainids": [1], "hops": 2}
    # BFS outward from seeds over txlist+tokentx, capped at max_transfers; returns transfers + bytecodes of deployed contracts
```

- [ ] **Step 1: Failing tests** (fake HTTP, no network)

```python
from gt.chain import etherscan

class FakeHttp:
    def __init__(self, responses): self.responses, self.calls = list(responses), 0
    def get(self, url, params, timeout):
        self.calls += 1
        return self.responses.pop(0)

class R:
    def __init__(self, code, body): self.status_code, self._b = code, body
    def json(self): return self._b

def test_retries_on_429_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(etherscan, "CACHE_DIR", tmp_path)
    http = FakeHttp([R(429, {}), R(200, {"status": "1", "result": [{"hash": "0x1"}]})])
    assert etherscan.get({"a": 1}, http=http, sleep=lambda s: None) == [{"hash": "0x1"}]
    assert http.calls == 2

def test_gives_up_without_crashing(tmp_path, monkeypatch):
    monkeypatch.setattr(etherscan, "CACHE_DIR", tmp_path)
    http = FakeHttp([R(429, {})] * 5)
    assert etherscan.get({"b": 1}, http=http, sleep=lambda s: None) == []

def test_cache_hit_skips_network(tmp_path, monkeypatch):
    monkeypatch.setattr(etherscan, "CACHE_DIR", tmp_path)
    http = FakeHttp([R(200, {"status": "1", "result": [1]})])
    etherscan.get({"c": 1}, http=http, sleep=lambda s: None)
    assert etherscan.get({"c": 1}, http=http, sleep=lambda s: None) == [1] and http.calls == 1
```

- [ ] **Step 2: Run — FAIL.** **Step 3: Implement.** Use `httpx.Client` as default `http`. Throttle to ≤ 4 req/s (free tier is 5). Convert rows via `norm_addr`/`to_utc`; `gas_price_gwei = int(gasPrice)/1e9`, `amount = int(value)/1e18` for ETH.
- [ ] **Step 4: Run — PASS.**
- [ ] **Step 5: Create one real replay file.** Pick a past hack from a public post-mortem (rekt.news / the protocol's own report). Copy the attacker addresses **from that report** into `data/replays/<name>.json`, verify each on Etherscan. Run `python -c "from gt.chain.etherscan import load_replay; print(len(load_replay('../data/replays/<name>.json')[0]))"` → expect > 100.
- [ ] **Step 6: Commit** — `feat: etherscan client with cache, backoff, replay loader`

### Task 2c: Live stream + mempool (lite) (#7, #8)

**Files:**
- Create: `backend/gt/chain/live.py`
- Test: `backend/tests/test_live.py`

**Interfaces:**
```python
def poll_once(watch: set[str], last_block: int, rpc=None) -> tuple[list[Transfer], int]
    # Alchemy JSON-RPC: eth_blockNumber, then alchemy_getAssetTransfers(fromBlock=last_block+1, fromAddress/toAddress in watch,
    #   category=["external","erc20"], withMetadata=True). Returns (new transfers, new last_block).
async def live_loop(conn, watch: set[str], interval_s: int = 12, queue: asyncio.Queue | None = None) -> None
    # forever: poll_once → db.insert → put each Transfer on queue (consumed by SSE in Task 7b)
def pending_count(watch: set[str], rpc=None) -> int
    # lite mempool: one eth_getBlockByNumber("pending", true) scan, count txs touching watch
```

- [ ] **Step 1: Failing test** — fake `rpc(method, params)` returning canned JSON; assert `poll_once({"0xa"}, 10, rpc)` returns 1 Transfer with normalized fields and `last_block == 12`; and with `rpc` raising `httpx.TimeoutException` returns `([], 10)`.
- [ ] **Step 2: FAIL. Step 3: Implement** (`rpc` default = httpx POST to `https://eth-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}`). **Step 4: PASS. Step 5: Commit** — `feat: live alchemy poller and mempool count`

---

## M3 — OSINT Ingestion

### Task 3a: Entity extraction + time handling (#3, #4)

**Files:**
- Create: `backend/gt/osint/__init__.py`, `backend/gt/osint/extract.py`
- Test: `backend/tests/test_extract.py`

**Interfaces:**
```python
def extract(post: OsintPost) -> list[Entity]
    # regex: address 0x[0-9a-fA-F]{40} (normalized), tx 0x[0-9a-fA-F]{64}, IPv4, email, @handle, *.eth (ENS)
    # tx regex must win over address regex (a 64-hex tx hash must not also yield a 40-hex address)
def make_post(source: str, author: str, ts_raw, text: str, url: str = "") -> OsintPost | None
    # ts via to_utc; returns None if ts unparseable; post_id = sha1(source|author|ts|text)[:16]
```

- [ ] **Step 1: Failing tests**

```python
from gt.osint.extract import extract, make_post

def test_extracts_all_kinds():
    p = make_post("forum", "x", 1, "send to 0x" + "Ab"*20 + " tx 0x" + "c"*64 + " ip 10.0.0.5 mail a@b.io @ghostfox vitalik.eth")
    kinds = {(e.kind, e.value) for e in extract(p)}
    assert ("address", "0x" + "ab"*20) in kinds
    assert ("tx", "0x" + "c"*64) in kinds
    assert {"ip", "email", "handle", "ens"} <= {k for k, _ in kinds}
    assert sum(1 for k, _ in kinds if k == "address") == 1   # tx hash not double-counted

def test_post_without_time_is_dropped():
    assert make_post("rss", "x", "garbage", "hi") is None

def test_no_entities_is_empty_not_error():
    assert extract(make_post("forum", "x", 1, "nothing here")) == []
```

- [ ] **Step 2: FAIL. Step 3: Implement. Step 4: PASS. Step 5: Commit** — `feat: osint entity extraction`

### Task 3b: Collectors — RSS, GitHub, Telegram (#1, #2)

**Files:**
- Create: `backend/gt/osint/collectors.py`, `backend/gt/llm.py`
- Test: `backend/tests/test_collectors.py`

**Interfaces:**
```python
def collect_rss(urls: list[str], parse=feedparser.parse) -> list[OsintPost]          # source="rss", author=feed title
def collect_github(queries: list[str], http=None) -> list[OsintPost]
    # GET https://api.github.com/search/code?q=<q> (needs GITHUB_TOKEN) and /search/commits; text = file snippet / commit message;
    # author = repo owner login; ts = commit date or repo pushed_at; on 403/429 return what was collected so far
async def collect_telegram(channels: list[str], limit: int = 200) -> list[OsintPost]  # telethon; returns [] if TELEGRAM_API_ID unset
# llm.py
def complete(prompt: str, max_tokens: int = 400) -> str | None
    # Groq (OpenAI-compatible POST https://api.groq.com/openai/v1/chat/completions) else Gemini else None. Never raises.
```

- [ ] **Step 1: Failing tests** — `collect_rss` with a fake `parse` returning `{"feed": {"title": "rekt"}, "entries": [{"title": "t", "summary": "s 0x…", "link": "u", "published": "Fri, 17 Oct 2026 02:14:00 GMT"}]}` → 1 post with correct UTC ts; `collect_github` with fake http returning 403 → `[]`; `complete("hi")` with no keys in env → `None`.
- [ ] **Step 2: FAIL. Step 3: Implement.** Feed URLs and GitHub queries live in `config.py` (`RSS_FEEDS`, `GITHUB_QUERIES = ["exploit flashloan", "0x<attacker prefix>"]`). **Verify each feed URL works at hour 1**; drop any that don't. Telegram: public channels only; first run needs the user to log in interactively once (session file in `data/`).
- [ ] **Step 4: PASS. Step 5: Commit** — `feat: rss github telegram collectors`

### Task 3c: Stylometry + cross-platform usernames (#5, #6)

**Files:**
- Create: `backend/gt/osint/style.py`
- Test: `backend/tests/test_style.py`

**Interfaces:**
```python
def username_similarity(a: str, b: str) -> float      # rapidfuzz ratio on de-leeted lowercase (0→o, 1→i/l, 3→e, 4→a, 5→s, _/- removed), 0..1
def style_similarity(texts_a: list[str], texts_b: list[str]) -> float
    # TfidfVectorizer(analyzer="char_wb", ngram_range=(2,4)) fit on both; cosine of mean vectors; 0..1
def resolve_identities(posts: list[OsintPost], name_thr: float = 0.8, style_thr: float = 0.6) -> dict[str, str]
    # maps every "source:author" to a canonical identity; merge two authors when name_sim ≥ name_thr OR style_sim ≥ style_thr
    # (union-find; canonical = alphabetically first member)
```

- [ ] **Step 1: Failing tests**

```python
from gt.osint.style import username_similarity, resolve_identities
from gt.simulator import simulate

def test_leet_usernames_match():
    assert username_similarity("ghostfox", "gh0st_fox") > 0.9
    assert username_similarity("ghostfox", "alice") < 0.5

def test_simulator_handles_resolve_to_one_identity():
    s = simulate(seed=5)
    ids = resolve_identities(s.posts)
    att = {ids[f"{p.source}:{p.author}"] for p in s.posts if p.author in s.truth.attacker_handles}
    assert len(att) == 1
```

- [ ] **Step 2: FAIL. Step 3: Implement. Step 4: PASS. Step 5: Commit** — `feat: stylometry and identity resolution`

---

## M4 — Analytics (the math layer)

### Task 4a: Activity matrix, wallet features, graph (#14, #15, #16)

**Files:**
- Create: `backend/gt/analytics/__init__.py`, `backend/gt/analytics/features.py`, `backend/gt/analytics/graph.py`
- Test: `backend/tests/test_features.py`

**Interfaces:**
```python
# features.py
def activity_matrix(transfers: list[Transfer], bucket_s: int = 3600) -> pd.DataFrame
    # index = wallet (sender), columns = bucket start ts, values = tx count
def wallet_features(transfers: list[Transfer]) -> pd.DataFrame
    # index = wallet; columns: n_tx, mean_gas, std_gas, round_frac, mean_gap_s, cv_gap, active_hours (set size 0..24)
    # wallets with < 3 sent txs → NaN for gap stats (never raise)
# graph.py
def build_graph(transfers: list[Transfer]) -> nx.MultiDiGraph
    # nodes = addresses (attr: chain); edges from→to with attrs tx_hash, ts, asset, amount, kind
    # bridge_out/bridge_in pairs are added as an extra edge by Task 4c, not here
```

- [ ] **Step 1: Failing tests** — matrix shape on 3 handcrafted transfers; `wallet_features` on a wallet with 1 tx returns a row with NaN `cv_gap` (no exception); `round_frac` of amounts `[1.0, 2.5, 10.0, 3.1234]` = 0.75 (round = amount*10 is an integer); graph has the right edge count and `kind` attrs.
- [ ] **Step 2: FAIL. Step 3: Implement. Step 4: PASS. Step 5: Commit** — `feat: activity matrix, wallet features, graph`

### Task 4b: Gas-funder tracing + wallet clustering (#18, #19)

**Files:**
- Create: `backend/gt/analytics/funding.py`; Modify: `backend/gt/analytics/graph.py`
- Test: `backend/tests/test_clustering.py`

**Interfaces:**
```python
# funding.py
def gas_funders(transfers: list[Transfer], max_gas_eth: float = 0.1) -> dict[str, str]
    # for each wallet: sender of its FIRST incoming ETH transfer if amount ≤ max_gas_eth and that wallet's first OUTGOING tx comes after it
def funding_clusters(funders: dict[str, str], exclude: set[str]) -> dict[str, int]
    # union-find over wallet—funder edges; never union through addresses in `exclude` (exchanges, mixers, bridges)
# graph.py (add)
def cluster_wallets(G: nx.MultiDiGraph, funders: dict[str, str], seeds: set[str], labels: dict[str, str]) -> dict[str, int]
    # cluster 0 = attacker cluster: seeds ∪ wallets reachable from seeds within 4 hops through non-labeled nodes
    #   ∪ wallets in the same funding cluster as any member. Other wallets: louvain_communities(undirected, weight=amount, seed=0) ids 1..n.
```

- [ ] **Step 1: Failing tests**

```python
from gt.simulator import simulate, evaluate
from gt.analytics.graph import build_graph, cluster_wallets
from gt.analytics.funding import gas_funders

def test_attacker_cluster_quality_on_simulator():
    s = simulate(seed=6)
    G = build_graph(s.transfers)
    main = sorted(s.truth.attacker_wallets)[0]
    c = cluster_wallets(G, gas_funders(s.transfers), {main}, s.labels)
    pred = {w for w, k in c.items() if k == 0}
    r = evaluate(pred, None, s.truth)
    assert r["precision"] >= 0.85 and r["recall"] >= 0.85

def test_exchange_never_joins_attacker_cluster():
    s = simulate(seed=6)
    G = build_graph(s.transfers)
    c = cluster_wallets(G, gas_funders(s.transfers), {sorted(s.truth.attacker_wallets)[0]}, s.labels)
    assert all(c.get(a) != 0 for a, l in s.labels.items() if l.startswith("exchange:"))
```

- [ ] **Step 2: FAIL. Step 3: Implement. Step 4: PASS** (if recall is low, mixer_out wallets are the usual gap — they are reconnected via gas funders; check funder logic first). **Step 5: Commit** — `feat: gas funder tracing and clustering`

### Task 4c: Amount conservation + bridge matching (#9, #20)

**Files:**
- Create: `backend/gt/analytics/amounts.py`
- Test: `backend/tests/test_amounts.py`

**Interfaces:**
```python
def match_split(parent_amount: float, children: list[tuple[str, float]], tol: float = 0.005, max_n: int = 25) -> list[str] | None
    # ids whose amounts sum to parent within tol (relative). Only the max_n largest children are searched.
    # ponytail: meet-in-the-middle over ≤25 items (2^12.5 each side); upgrade = ILP solver if more needed
def match_bridges(outs: list[Transfer], ins: list[Transfer], fee_max: float = 0.003,
                  window_s: tuple[int, int] = (60, 1800)) -> list[tuple[str, str, float]]
    # (out_tx, in_tx, confidence). Candidate if 0 ≤ (out.amount − in.amount)/out.amount ≤ fee_max and in.ts − out.ts within window.
    # Greedy one-to-one by smallest |time gap|; confidence = 1 − rel_fee/fee_max * 0.5 − gap/window_max * 0.5
```

- [ ] **Step 1: Failing tests**

```python
import time
from gt.analytics.amounts import match_split, match_bridges
from gt.simulator import simulate

def test_split_found():
    kids = [("a", 3.0), ("b", 4.0), ("c", 5.5), ("d", 100.0)]
    assert sorted(match_split(12.5, kids)) == ["a", "b", "c"]

def test_split_blowup_is_bounded():
    kids = [(str(i), 1.0 + i * 0.37) for i in range(300)]
    t = time.time(); match_split(99999.0, kids); assert time.time() - t < 1.0

def test_bridges_on_simulator():
    s = simulate(seed=8)
    outs = [t for t in s.transfers if t.kind == "bridge_out"]
    ins = [t for t in s.transfers if t.kind == "bridge_in"]
    assert len(match_bridges(outs, ins)) >= 0.9 * len(outs)
```

- [ ] **Step 2: FAIL. Step 3: Implement. Step 4: PASS. Step 5: Commit** — `feat: subset-sum and bridge matching`

### Task 4d: Bot detection + timezone inference (#21, #22)

**Files:**
- Create: `backend/gt/analytics/behavior.py`
- Test: `backend/tests/test_behavior.py`

**Interfaces:**
```python
def bot_score(gaps_s: list[float], amounts: list[float]) -> float | None
    # None if len(gaps_s) < 10. Mean of three 0..1 sub-scores:
    #  (1) timing: KS test of gaps vs exponential(mean) — humans ≈ Poisson; score = 1 − p_value
    #  (2) roundness: 1 − round_frac (bots don't round)
    #  (3) benford: only if len(amounts) ≥ 20; chi-square of first digits vs Benford; score = 1 − p_value; else skipped
def infer_utc_offset(ts_list: list[int]) -> tuple[int, float] | None
    # None if < 15 timestamps. Hour histogram (UTC); template = 1 for local hours 9..23 else 0;
    # for offset in -12..14 compute correlation of histogram vs template shifted; return (best_offset, best_corr − second_best_corr)
```

- [ ] **Step 1: Failing tests** — uniform(20,40) gaps + unrounded amounts → score > 0.7; exponential gaps + 50% round amounts → score < 0.5; 5 gaps → `None`; timestamps generated at local 10:00–22:00 for offset +9 → `infer_utc_offset(...)[0] in {8, 9, 10}`; 3 timestamps → `None`.
- [ ] **Step 2: FAIL. Step 3: Implement. Step 4: PASS. Step 5: Commit** — `feat: bot score and timezone inference`

### Task 4e: Time-delta latency analysis (#17) — core of the problem statement

**Files:**
- Create: `backend/gt/analytics/latency.py`
- Test: `backend/tests/test_latency.py`

**Interfaces:**
```python
def latency_test(post_ts: list[int], tx_ts: list[int], max_lag_s: int = 900,
                 n_perm: int = 500, seed: int = 0) -> dict | None
    # None if len(post_ts) < 5 or not tx_ts.
    # observed = fraction of posts followed by ≥1 tx within (0, max_lag_s]
    # null: circularly shift all post_ts by a random offset in [1h, span−1h] (keeps post rhythm), recompute, n_perm times
    # p_value = (1 + #null ≥ observed) / (1 + n_perm)
    # returns {"hit_rate": observed, "p_value": p, "median_lag_s": median of first-tx lags for hits, "n_posts": len(post_ts)}
def latency_lr(p_value: float) -> float      # 20 if p < 0.01, 5 if p < 0.05, 1 otherwise
```

- [ ] **Step 1: Failing tests**

```python
from gt.simulator import simulate
from gt.analytics.latency import latency_test

def test_attacker_handle_is_significant():
    s = simulate(seed=9)
    att_tx = sorted(t.ts for t in s.transfers if t.from_addr in s.truth.attacker_wallets)
    posts = sorted(p.ts for p in s.posts if p.author == "ghostfox")
    assert latency_test(posts, att_tx)["p_value"] < 0.01

def test_random_author_is_not():
    s = simulate(seed=9)
    att_tx = sorted(t.ts for t in s.transfers if t.from_addr in s.truth.attacker_wallets)
    noise = [p for p in s.posts if p.author not in s.truth.attacker_handles]
    author = max({p.author for p in noise}, key=lambda a: sum(p.author == a for p in noise))
    assert latency_test(sorted(p.ts for p in noise if p.author == author), att_tx)["p_value"] > 0.05
```

- [ ] **Step 2: FAIL. Step 3: Implement** with `numpy.searchsorted` (vectorized; must run < 1 s for 1000 posts × 5000 tx). **Step 4: PASS. Step 5: Commit** — `feat: time-delta latency permutation test`

### Task 4f: Bytecode similarity (#13, #23) — owner P2

**Files:**
- Create: `backend/gt/analytics/bytecode.py`
- Test: `backend/tests/test_bytecode.py`

**Interfaces:**
```python
def selectors_from_bytecode(code_hex: str) -> set[str]      # every PUSH4 (opcode 0x63) operand, walking opcodes and skipping PUSH1..PUSH32 data
def selectors_from_source(solidity: str) -> set[str]        # regex `function name(types)` → canonical sig → keccak256[:4] via eth_hash.auto.keccak
def similarity(a: set[str], b: set[str]) -> float           # Jaccard; 0.0 if either empty
```

- [ ] **Step 1: Failing tests** — `selectors_from_source("function transfer(address to, uint256 amount) external")` == `{"a9059cbb"}`; bytecode `"0x63a9059cbb14"` → `{"a9059cbb"}`; simulator: GitHub post source vs deployed exploit bytecode similarity ≥ 0.6.
- [ ] **Step 2: FAIL. Step 3: Implement. Step 4: PASS. Step 5: Commit** — `feat: bytecode selector similarity`

---

## M5 — Fusion & Attribution

### Task 5a: Signal scoring, decay, explanation (#24, #25, #26, #43)

**Files:**
- Create: `backend/gt/fusion/__init__.py`, `backend/gt/fusion/score.py`
- Test: `backend/tests/test_score.py`

**Interfaces:**
```python
def posterior(signals: list[Signal], prior: float = PRIOR) -> float
    # odds = prior/(1−prior) × Π clip(lr, 0.1, 50); return odds/(1+odds)
    # ponytail: naive Bayes assumes independent signals; upgrade = learn weights on simulator runs
def decay(score: float, age_s: int, half_life_s: int = HALF_LIFE_S) -> float   # score × 0.5 ** (age_s / half_life_s)
def build_signals(cluster_wallets: set[str], identity_posts: list[OsintPost], entities: list[Entity],
                  transfers: list[Transfer], bytecodes: dict[str, str]) -> list[Signal]
    # time_delta: latency_test(posts, cluster tx ts) → Signal("time_delta", latency_lr(p), f"{hits}/{n} posts precede a tx by median {lag}s, p={p:.3f}")
    # rhythm:     |offset(cluster) − offset(identity)| ≤ 1 → lr 3 else 0.5
    # address_mention: identity post mentions a cluster wallet → lr 30
    # bytecode:   max similarity(identity source selectors, cluster contract selectors) ≥ 0.6 → lr 10
    # onchain_message: decoded input data of a cluster tx contains the identity handle → lr 30
    # skip any signal whose inputs are missing (never emit lr=1 placeholders)
def explain(link: Link) -> str
    # template: "Suspected (82%): <identity> ↔ cluster <id>. Because: <detail 1>; <detail 2>; …" ; signals sorted by lr desc
    # if llm.complete returns text use it as a 1-line summary prefix, else template only
def label(score: float, status: str) -> str     # "confirmed" if status=="confirmed"; "high" ≥ 0.8; "medium" ≥ 0.5; else "low"
```

- [ ] **Step 1: Failing tests**

```python
from gt.fusion.score import posterior, decay, label
from gt.schema import Signal

def test_posterior_math():
    assert abs(posterior([], 0.01) - 0.01) < 1e-9
    assert posterior([Signal("a", 30, ""), Signal("b", 20, "")], 0.01) > 0.85

def test_single_signal_is_capped():
    assert posterior([Signal("a", 1e9, "")], 0.01) < 0.34   # cap 50 → odds 0.505

def test_decay_half_life():
    assert abs(decay(0.8, 3600, 3600) - 0.4) < 1e-9

def test_labels():
    assert label(0.9, "suspected") == "high" and label(0.2, "confirmed") == "confirmed"
```

Plus a simulator test: `build_signals` for the attacker identity vs cluster 0 yields posterior ≥ 0.8, and for the busiest noise identity ≤ 0.2.

- [ ] **Step 2: FAIL. Step 3: Implement. Step 4: PASS. Step 5: Commit** — `feat: bayesian link scoring with explanations`

### Task 5b: Evidence chain + audit log (#27, #41)

**Files:**
- Create: `backend/gt/fusion/evidence.py`; Modify: `backend/gt/schema.py` (add `Evidence`, `AuditEntry`, append both to `ALL`)
- Test: `backend/tests/test_evidence.py`

**Interfaces:**
```python
@dataclass
class Evidence:
    hash: str          # sha256 hex of canonical JSON of payload
    kind: str          # "transfer" | "post" | "signal"
    source_url: str
    captured_ts: int
    payload: str       # canonical JSON

@dataclass
class AuditEntry:
    entry_id: str      # sha256(prev_hash + actor + action + target + ts)[:16]
    ts: int
    actor: str
    action: str        # "confirm_link" | "reject_link" | "approve_alert" | "send_alert" | "export_report"
    target: str
    prev_hash: str     # entry_id of previous entry ("" for first) — tamper-evident chain

def record(conn, obj, kind: str, source_url: str = "") -> str     # store Evidence, return hash (idempotent)
def audit(conn, actor: str, action: str, target: str) -> AuditEntry
def verify_audit(conn) -> bool                                     # recompute chain; False if any entry was edited
```

- [ ] **Step 1: Failing tests** — `record` of the same object twice returns the same hash and stores 1 row; three `audit` calls then `verify_audit` is True; manually `conn.auditentry.update_one({...}, {"$set": {"actor": "x"}})` → `verify_audit` is False.
- [ ] **Step 2: FAIL. Step 3: Implement. Step 4: PASS. Step 5: Commit** — `feat: evidence hashing and tamper-evident audit log`

---

## M6 — Defense

### Task 6a: Freezability + exit prediction (#28, #29)

**Files:**
- Create: `backend/gt/defense/__init__.py`, `backend/gt/defense/freeze.py`
- Test: `backend/tests/test_freeze.py`

**Interfaces:**
```python
@dataclass
class Holding:
    address: str; asset: str; amount: float; usd: float
    freezable: bool; freezer: str          # "Tether" | "Circle" | "exchange:<name>" | ""

def holdings(transfers: list[Transfer], wallets: set[str], labels: dict[str, str]) -> list[Holding]
    # net balance per (wallet, asset) = in − out; plus amounts already deposited at exchange addresses (wallet = exchange address)
    # freezable rules: USDT→Tether, USDC→Circle, address labeled exchange:X → "exchange:X", else not freezable
@dataclass
class ExitPrediction:
    exchange: str; address: str; share: float; usd: float; eta_s: int | None; arrived: bool

def predict_exits(G: nx.MultiDiGraph, sources: set[str], labels: dict[str, str], total_usd: float,
                  max_hops: int = 6) -> list[ExitPrediction]
    # flow propagation: start mass 1.0 split over sources; each step a node passes mass to successors proportional to outgoing amount;
    # exchange-labeled nodes absorb. share = absorbed mass; arrived = node already received funds; eta = median edge gap × remaining hops.
    # Sorted by share desc.
    # ponytail: proportional flow ignores timing order; upgrade = temporal walk if it misranks on replay
```

- [ ] **Step 1: Failing tests** — tiny graph: source → A(60) → exchange:X ; source → B(40) → exchange:Y ⇒ shares 0.6/0.4 sorted; `holdings` marks USDT freezable by Tether and raw ETH not freezable; simulator: top predicted exchange ∈ `truth.exit_exchanges` and total freezable USD > 0.
- [ ] **Step 2: FAIL. Step 3: Implement. Step 4: PASS. Step 5: Commit** — `feat: freezability scoring and exit prediction`

### Task 6b: Pre-attack warning + decoy/poisoning filter (#30, #31)

**Files:**
- Create: `backend/gt/defense/guards.py`
- Test: `backend/tests/test_guards.py`

**Interfaces:**
```python
def prewarn(transfers: list[Transfer], labels: dict[str, str], window_s: int = 24 * 3600) -> list[Alert]
    # wallet W flagged when within window_s: W funded by a mixer_out (directly or via one funder hop) AND W has a `deploy` AND ≥ 2 `test_call`
def is_lookalike(a: str, b: str) -> bool             # a != b and a[2:8] == b[2:8] and a[-4:] == b[-4:]
def find_decoys(transfers: list[Transfer], attacker: set[str], known: set[str], dust_usd: float = 1.0) -> set[str]
    # receivers of attacker transfers with usd < dust_usd that never send back into attacker set,
    # plus any receiver that is_lookalike() of an address in `known` (labels keys)
```

- [ ] **Step 1: Failing tests** — simulator: `prewarn` fires on the attacker main wallet with `created_ts` < t0 (i.e. **before the theft**); `find_decoys` recall ≥ 0.9 vs `truth.decoy_wallets` and contains no attacker wallet; `is_lookalike` true/false cases.
- [ ] **Step 2: FAIL. Step 3: Implement. Step 4: PASS. Step 5: Commit** — `feat: pre-attack warning and decoy detection`

### Task 6c: Alert queue, human approval, webhook send (#32, #42) — owner P2

**Files:**
- Create: `backend/gt/defense/alerts.py`
- Test: `backend/tests/test_alerts.py`

**Interfaces:**
```python
def queue(conn, alerts: list[Alert]) -> None                           # insert with status "pending"
def approve(conn, alert_id: str, actor: str, send=None) -> Alert
    # status pending→approved, audit(...,"approve_alert"), then send(text) → status "sent" + audit("send_alert").
    # send default: Discord webhook if DISCORD_WEBHOOK_URL else Telegram bot sendMessage if token+chat id else no-op (stays "approved")
    # raises ValueError if alert is not "pending"
def dismiss(conn, alert_id: str, actor: str) -> Alert
```

- [ ] **Step 1: Failing tests** — approve with a fake `send` records text and ends `sent`; approving twice raises `ValueError`; with no env keys the alert ends `approved` and nothing raises; nothing is sent by `queue` alone.
- [ ] **Step 2: FAIL. Step 3: Implement. Step 4: PASS. Step 5: Commit** — `feat: alert approval gate and webhook delivery`

---

## M7 — Pipeline & API

### Task 7a: Pipeline `run()` + metrics

**Files:**
- Create: `backend/gt/pipeline.py`
- Test: `backend/tests/test_pipeline.py`

**Interfaces:**
```python
@dataclass
class Results:
    clusters: dict[str, int]
    links: list[Link]
    exits: list[ExitPrediction]
    holdings: list[Holding]
    decoys: set[str]
    bridges: list[tuple[str, str, float]]
    bot_scores: dict[str, float]
    utc_offsets: dict[str, tuple[int, float]]     # "cluster:0" / "identity:<x>" → offset
    metrics: dict | None                          # evaluate() output when a simulator Truth is loaded

def load_scenario(conn, s: Scenario) -> None      # clear + insert transfers/posts/entities; labels+bytecodes+truth saved via `put_meta(conn, "scenario", ...)`
def run(conn, seeds: set[str] | None = None) -> Results
    # order: transfers/posts from db → classify → find_decoys (removed from graph) → build_graph (+ bridge edges from match_bridges)
    # → gas_funders → cluster_wallets → resolve_identities → build_signals per (cluster 0, identity) → posterior/decay → Links
    # → holdings → predict_exits → prewarn → queue alerts (exit + prewarn + freeze for each freezable holding ≥ $10k)
    # → write Links (keep any prior "confirmed"/"rejected" status) → evaluate if truth exists. Results also saved via `put_meta(conn, "results", ...)`.
    # seeds default: the address that received the largest single inbound transfer from a "victim"-labeled address
```

- [ ] **Step 1: Failing test** — `load_scenario(simulate(seed=11))`, `run()` ⇒ `metrics["f1"] ≥ 0.85`, `metrics["handle_correct"]`, the top link's score ≥ 0.8, ≥ 1 exit alert queued, and the whole run takes < 30 s.
- [ ] **Step 2: FAIL. Step 3: Implement. Step 4: PASS. Step 5: Commit** — `feat: end-to-end pipeline with metrics`

### Task 7b: FastAPI endpoints + live SSE

**Files:**
- Create: `backend/gt/api.py`
- Test: `backend/tests/test_api.py` (FastAPI `TestClient`)

**Interfaces (all JSON, prefix `/api`, CORS allow origins from `FRONTEND_ORIGINS`):**

| Method + path | Returns |
|---|---|
| `POST /simulate?seed=7` | `{"transfers": n, "posts": m}` |
| `POST /replay/{name}` | same; loads `data/replays/{name}.json` |
| `POST /run` | `{"metrics": {...} | null, "links": n, "alerts": n}` |
| `GET /graph?cluster=0&limit=600` | `{"nodes": [{id, label, cluster, kind, usd}], "edges": [{source, target, usd, kind, ts}]}` |
| `GET /timeline` | `[{"ts", "type": "post"|"tx", "who", "text"|"usd", "cluster"}]` sorted by ts |
| `GET /sankey` | `{"nodes": [{name}], "links": [{source, target, value}]}` stages: attacker → split → mixer/bridge/swap → consolidation → exchange/unspent |
| `GET /heatmap/{key}` | `{"hours": [24 ints], "utc_offset": int, "confidence": float}` (key `cluster:0` or `identity:x`) |
| `GET /money-now` | `{"total_usd", "frozen_possible_usd", "at_exchanges_usd", "in_mixers_usd", "unspent_usd", "exits": [ExitPrediction]}` |
| `GET /links` | `[Link + {"label", "explanation"}]` |
| `POST /links/{link_id}/{confirm|reject}` | updated Link; writes audit; confirmed/rejected status survives `/run` |
| `GET /alerts` · `POST /alerts/{id}/approve` · `POST /alerts/{id}/dismiss` | Alert(s) |
| `GET /report` | `{"case", "generated_ts", "links", "exits", "holdings", "freeze_requests": [{"to", "text"}], "audit_ok": bool, "evidence_count"}` |
| `GET /health` | `{"ok": true, "db": "mongo"|"mongomock"}` |
| `GET /live` | `text/event-stream`; one `data: <Transfer JSON>` per new live transfer |
| `POST /live/start` `{"watch": [addresses]}` | starts `live_loop` as a background task |

- `freeze_request(to: str, holdings: list[Holding], links: list[Link]) -> str` lives in `api.py` (template: recipient, addresses, amounts, tx hashes, evidence hashes, "suspected — pending law-enforcement confirmation"; LLM polish optional).
- [ ] **Step 1: Failing tests** — simulate → run → `/graph` has nodes; `/links` first item has `explanation`; approving an alert twice → HTTP 409; `/report` `audit_ok` is true; reject a link, `POST /run` again, status still `rejected`.
- [ ] **Step 2: FAIL. Step 3: Implement. Step 4: PASS.**
- [ ] **Step 5: Run it:** `.venv/Scripts/python -m uvicorn gt.api:app --reload --port 8000` → open `http://localhost:8000/docs`, run simulate + run.
- [ ] **Step 6: Commit** — `feat: fastapi endpoints and live sse`

---

## M8 — Frontend (owner P4; start at hour 1 against `fixtures/*.json` copied from the API response shapes above, swap to real API at the hour-6 checkpoint)

### Task 8a: Scaffold + Dashboard — money flow graph, "money now", alert queue (#33, #37, #42)

**Files:**
- Create: `frontend/` via `npm create vite@latest frontend -- --template react-ts`; `src/api.ts`, `src/App.tsx`, `src/pages/Dashboard.tsx`, `src/components/FlowGraph.tsx`, `src/components/MoneyNow.tsx`, `src/components/AlertQueue.tsx`
- Deps: `npm i cytoscape echarts echarts-for-react react-router-dom` and `npm i -D @types/cytoscape`

**Interfaces:**
- `api.ts`: `const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api"`; one typed function per endpoint in the Task 7b table (`getGraph`, `getMoneyNow`, `getAlerts`, `approveAlert`, `simulate`, `run`, …). TypeScript types mirror the dataclasses field-for-field.
- Dashboard layout: top bar with **Simulate / Replay ▾ / Run / Live** buttons and the F1 metric badge; left 2/3 FlowGraph; right 1/3 MoneyNow cards + AlertQueue.
- FlowGraph: cytoscape `cose` layout; node color by `kind` (attacker cluster red, mixer purple, bridge blue, exchange amber, decoy grey dashed); node size ∝ log(usd); click node → side panel with its transfers.
- MoneyNow: 5 stat cards from `/money-now` + exit list "Exch-A — 46% — ETA 2h — **freeze possible**".
- AlertQueue: pending alerts with **Approve & send** / **Dismiss** (approve shows a confirm dialog — #42).

- [ ] **Step 1:** Scaffold, add deps, `npm run dev` shows the Vite page.
- [ ] **Step 2:** Implement components against fixtures.
- [ ] **Step 3: Verify:** `npm run build` passes with zero TS errors; with the backend running, Simulate → Run updates the graph, cards and alerts without a page reload.
- [ ] **Step 4: Commit** — `feat: dashboard with flow graph, money-now, alert queue`

### Task 8b: Investigate page — timeline, heatmap, Sankey, link cards (#34, #35, #36, #40, #43)

**Files:**
- Create: `src/pages/Investigate.tsx`, `src/components/Timeline.tsx`, `Heatmap.tsx`, `Sankey.tsx`, `LinkCard.tsx`

- Timeline: ECharts scatter, x = time, two rows ("OSINT posts", "Attacker txs"); hovering a post highlights txs within the next 15 min (the time-delta story).
- Heatmap: ECharts 24-column heatmap, cluster vs identity rows side by side, titled "Inferred UTC+9 (confidence 0.42)".
- Sankey: ECharts sankey from `/sankey`.
- LinkCard: identity ↔ cluster, score bar, label chip (low/medium/high/confirmed — #43), explanation text, signal list with LR values, **Confirm / Reject** buttons (#40) → POST then refetch.

- [ ] **Step 1:** Implement. **Step 2: Verify** `npm run build` passes; on simulator data the top LinkCard shows "high" and ≥ 3 signals; Confirm persists after clicking Run again. **Step 3: Commit** — `feat: investigate page`

### Task 8c: Report page + freeze requests + privacy masking (#38, #39, #44)

**Files:**
- Create: `src/pages/Report.tsx`

- Renders `/report` as a print-styled page: case summary, links table with explanations, exits table, freezable holdings, each freeze request in a copyable box, evidence count, "Audit chain verified ✓/✗", generated time (UTC).
- **Download PDF** button → `window.print()` with `@media print` CSS (no PDF library).
- Privacy (#44): identities show as handles only; any extracted email/IP is masked `a***@b.io` / `10.0.*.*` unless an analyst toggles "unmask" (toggle writes an audit entry via a POST).

- [ ] **Step 1:** Implement. **Step 2: Verify** print preview fits on A4 without cut-off tables. **Step 3: Commit** — `feat: printable evidence report with freeze requests`

---

## M9 — Demo Hardening

### Task 9: Replay case, demo script, rehearsal

- [ ] **Step 1:** `POST /replay/<name>` on the real replay file, `POST /run`; confirm graph + exits render. If the replay is slow, cut `max_transfers` to 1500.
- [ ] **Step 2:** Write `DEMO.md` (≤ 1 page): 3-minute script —
  1. Problem in one sentence → **Simulate** → "300 wallets, 3 chains, mixers, bots, decoys".
  2. **Run** → F1 badge ("we recovered 9x% of the attacker's wallets") → graph turns red.
  3. Investigate → timeline (posts precede txs) → heatmap (UTC+9) → LinkCard "high, because …".
  4. Dashboard → exits + "$X freezable" → **Approve & send** → Discord/Telegram message arrives live.
  5. Pre-attack warning fired **before** the theft timestamp.
  6. Report → PDF.
  7. Replay on a real hack → "works on real data too".
- [ ] **Step 3:** Full rehearsal twice from a fresh DB (`POST /simulate` clears it). Time it.
- [ ] **Step 4: Deploy.** Add `render.yaml` (service `unmask-api`, runtime python, `rootDir: backend`, build `pip install -r requirements.txt`, start as in Global Constraints, envVars synced=false for every key in `.env.example` + `FRONTEND_ORIGINS` + `PYTHON_VERSION=3.11.9`). Push to GitHub → Render Blueprint → set env values in the Render dashboard. Vercel: import repo, root `frontend`, set `VITE_API_URL=https://<render-service>.onrender.com/api`; then add the Vercel URL to Render's `FRONTEND_ORIGINS`. Verify: open the Vercel URL → Simulate → Run works against Atlas.
- [ ] **Step 5:** Code freeze at hour 13. Commit — `chore: demo script and deploy config`

---

## Feature Map (#1–#44 → task)

| # | Feature | Task | Depth |
|---|---|---|---|
| 1 | Threat feed scrapers | 3b | lite (RSS, public Telegram; no X/Pastebin/dark web) |
| 2 | GitHub monitoring | 3b | full |
| 3 | Entity extraction | 3a | full |
| 4 | Timestamp normalization | 2a, 3a | full |
| 5 | Cross-platform usernames | 3c | lite |
| 6 | Stylometry | 3c | lite |
| 7 | Live transaction stream | 2b, 2c | full ETH / lite 2nd chain |
| 8 | Mempool monitoring | 2c | lite |
| 9 | Bridge decoding | 4c | lite (amount + time match) |
| 10 | Mixer tracking | 2a | full |
| 11 | DEX swap decoding | 2a | lite (label-based) |
| 12 | On-chain messages | 2a | full |
| 13 | Bytecode collection | 2b, 4f | full |
| 14 | Wallet × time matrix | 4a | full |
| 15 | Wallet feature vectors | 4a | full |
| 16 | Transaction graph | 4a | full |
| 17 | Time-delta latency | 4e | full |
| 18 | Graph clustering | 4b | full |
| 19 | Gas-funder tracing | 4b | full |
| 20 | Amount conservation | 4c | full |
| 21 | Bot detection | 4d | full |
| 22 | Timezone inference | 4d | full |
| 23 | Bytecode similarity | 4f | lite |
| 24 | Bayesian link score | 5a | full |
| 25 | Explanations | 5a | full |
| 26 | Confidence decay | 5a | full |
| 27 | Evidence chain | 5b | full |
| 28 | Exit prediction | 6a | lite |
| 29 | Freezability | 6a | full |
| 30 | Pre-attack warning | 6b | lite |
| 31 | Decoy / poisoning detection | 6b | lite |
| 32 | Live alerts | 6c | full |
| 33 | Money-flow graph | 8a | full |
| 34 | Combined timeline | 8b | full |
| 35 | Cross-chain Sankey | 8b | full |
| 36 | Activity heatmap | 8b | full |
| 37 | Money-now dashboard | 8a | full |
| 38 | PDF report | 8c | full |
| 39 | Freeze-request templates | 7b, 8c | full |
| 40 | Analyst feedback | 7b, 8b | lite (status persists; no prior learning) |
| 41 | Audit log | 5b | full |
| 42 | Human approval gate | 6c, 8a | full |
| 43 | Suspected/confirmed labels | 5a, 8b | full |
| 44 | Privacy controls | 8c | lite |

## Accounts checklist (free; fill `backend/.env` yourself — never paste keys in chat)

| Key | Where | Needed by |
|---|---|---|
| `MONGODB_URI` | mongodb.com/atlas → free M0 cluster → Connect → Drivers (allow Render's IPs or 0.0.0.0/0 for the hackathon) | deployment (unset = in-memory) |
| `ETHERSCAN_API_KEY` | etherscan.io → API keys (V2 key works for many chains) | 2b replay |
| `ALCHEMY_API_KEY` | alchemy.com → create app (Ethereum mainnet) | 2c live |
| `GITHUB_TOKEN` | GitHub → Settings → Developer settings → fine-grained token, public read only | 3b |
| `GROQ_API_KEY` or `GEMINI_API_KEY` | console.groq.com / aistudio.google.com | optional polish (3b, 5a, 7b) |
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | my.telegram.org | optional 3b |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` or `DISCORD_WEBHOOK_URL` | @BotFather / Discord channel → Integrations → Webhooks | 6c |
