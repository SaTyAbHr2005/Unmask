# M7: Pipeline + API (one button runs everything)

## In one sentence
M7 wires every module into **one `run()`**: load a case, cluster the wallets, score the identities, locate the money, predict the exits, propose alerts. It exposes all of it through a **web API** that the dashboard (M8) calls.

## Why it exists
M0–M6 are separate tools. An investigator under time pressure needs **one click**: "load this case → analyse → show me". The API also lets the frontend, deployed separately on Vercel, talk to the backend on Render.

## Where it sits

```
 Browser (M8) ──HTTP/JSON──► api.py ──► pipeline.run() ──► M4 analytics → M5 fusion → M6 defense
                               │                │
                               │                └─► MongoDB: links, alerts, evidence, audit, results
                               └─► SSE stream ◄── live poller (M2)
```

## Files

| File | What it does |
|---|---|
| [pipeline.py](../../backend/gt/pipeline.py) | `load_case`, `load_scenario`, `run`, `load_results` |
| [api.py](../../backend/gt/api.py) | FastAPI app: every endpoint, CORS, live stream, freeze-request letters |
| [evidence.py](../../backend/gt/fusion/evidence.py) | New `head()`: newest audit entry, printed in the report |

---

## 1. The pipeline (`pipeline.py`)

### Loading a case
- **`load_case(conn, transfers, posts, labels, bytecodes, truth=None, name="", seeds=None)`** replaces whatever case is loaded: it clears the database, stores transfers, posts and every entity found in the posts, and saves the case details (labels, contract code, seed wallets, answer key if any) in `meta`.
- **`load_scenario(conn, scenario, name)`** does the same for a simulator scenario (including its answer key).

### `run(conn, seeds=None)`, in order
1. Read the case. Labels = known-address files (`data/labels`) + the case's own labels. Classify every transfer (mixer in/out, bridge, swap).
2. **Seed wallet:** the one passed in, else the case's seeds (replays), else **the wallet that received the biggest payment out of the victim**.
3. Build the money graph and **link bridge transfers** across chains (M4).
4. **Gas funders + clustering** → cluster 0 = the attacker (M4). Decoys are found (M6) and removed from it.
5. **Identities:** merge accounts that are the same person (M3).
6. For every identity: **clues → probability → decay** (M5). Each clue is stored as hashed evidence. Analyst decisions (confirmed/rejected) are **kept** across re-runs.
7. **Holdings + exits** (M6). Stolen amount = what left the victim into the cluster.
8. **Propose alerts**, all pending until a human approves:
   - pre-attack warnings,
   - one **exit** alert per exchange row holding ≥ 5% of the funds (arrived or predicted),
   - one **freeze** alert per stablecoin issuer (Tether, Circle) holding ≥ $10k.

   Re-running never resets an alert that's already decided.
9. Bot scores for cluster wallets and time zones for the cluster and each identity (M4).
10. **Accuracy** against the answer key when the case is a simulation.
11. Save everything to `meta.results` so the API can answer without re-running.

Returns `Results` (clusters, links, exits, holdings, decoys, bridges, bot_scores, utc_offsets, metrics, stolen_usd, case). An empty case returns an empty `Results` instead of crashing.

### Two problems found while building M7 (and fixed)

| Problem | Cause | Fix |
|---|---|---|
| The real hacker scored only **1.5%** | Confidence decay used a 6-hour half-life, measured from the hacker's last post. Normal users kept posting for 2 more days, so the evidence "aged" 5 half-lives. | Half-life is now **7 days**, measured from the newest activity on **either side** of the link. Attribution evidence doesn't go stale in hours. Score is now **86%** (100% before decay). |
| Loading a scenario took **52 seconds** | The in-memory database (used offline and in demos without Atlas) scanned the whole collection on every single-row save: quadratic work for 9,000 transfers. | Save in bulk (one delete + one insert). Now **0.3 seconds**. |

**End-to-end result (seed 7, over real HTTP):** whole analysis **0.85 s**; attacker wallets **precision 1.00, recall 0.998, F1 0.999**; correct handle `ghostfox` named at **86% (high)**; $42M stolen, **$31.8M still freezable**; 6 exit rows; 8 alerts proposed.

## 2. The API (`api.py`)

All endpoints are under `/api`. Interactive docs are at **`/docs`**: you can try every endpoint in the browser.

### Load and run

| Endpoint | Does | Returns |
|---|---|---|
| `GET /api/health` | Is the server up, which DB? | `{"ok": true, "db": "mongomock"}` (or `"mongo"` with Atlas) |
| `POST /api/simulate?seed=7` | Load a simulated attack | `{"transfers": 9055, "posts": 572}` |
| `POST /api/replay/{name}` | Load `data/replays/{name}.json` from Etherscan | same shape |
| `POST /api/run` | Run the whole engine | `{"metrics": {...}, "links": 53, "alerts": 8}` |

### Views for the dashboard

| Endpoint | Returns |
|---|---|
| `GET /api/graph?cluster=0&limit=600` | Nodes (the cluster's wallets plus the exchanges, mixers, bridges and decoys they touch; biggest `limit` by money volume) and edges (summed per sender, receiver and kind, including cross-chain bridge links). Node `kind`: attacker, exchange, mixer, bridge, dex, victim, decoy, wallet. |
| `GET /api/timeline?identity=…` | The cluster's transactions **and** the identity's posts on one time axis (default: the top-scored identity). This is how you *see* the "posts come minutes before transactions" pattern. |
| `GET /api/heatmap/cluster:0` or `/api/heatmap/identity:forum:ghostfox` | 24 hourly counts (UTC) + inferred time zone + confidence |
| `GET /api/sankey` | Stolen funds → route (Mixer / Bridge / DEX swap / Direct) → where it is now (each exchange / held-freezable / held-not-freezable) |
| `GET /api/money-now` | `total_usd`, `frozen_possible_usd`, `at_exchanges_usd`, `in_mixers_usd`, `unspent_usd`, `exits` |
| `GET /api/links` | Every identity link, highest first, with `label` (high/medium/low/confirmed/rejected) and plain-English `explanation` |

### Human decisions (each one is written to the audit chain)

| Endpoint | Does |
|---|---|
| `POST /api/links/{link_id}/confirm` · `/reject` | Analyst verdict on a link; survives re-runs |
| `GET /api/alerts` | All alerts with status |
| `POST /api/alerts/{id}/approve` | Approve → send to Discord/Telegram if configured. **409** if already decided, **404** if unknown. |
| `POST /api/alerts/{id}/dismiss` | Dismiss |

The analyst's name is taken from the `X-Analyst` header (default `analyst`).

### Report

| Endpoint | Returns |
|---|---|
| `GET /api/report` | Case name, metrics, top 5 links with explanations, exits, holdings, **one ready-to-send freeze-request letter per freezer** (Tether, Circle, each exchange), `audit_ok`, `audit_head` (newest audit-entry id, the outside anchor for the chain), number of audit entries and evidence items |
| `POST /api/report/export` | Same, and records `export_report` in the audit chain (the "Download PDF" button calls this) |

Freeze-request letters always say **"suspected — pending law-enforcement confirmation"** and list addresses, amounts and evidence hashes.

### Live mode

| Endpoint | Does |
|---|---|
| `POST /api/live/start` with `{"watch": ["0x…"]}` | Starts the Alchemy poller for those wallets. **400** without `ALCHEMY_API_KEY`, **422** for malformed addresses. |
| `GET /api/live` | Server-Sent Events: one `data: {transfer JSON}` line per new transfer, plus a keep-alive every 15 s |

### Safety details
- **Replay names** may only contain letters, digits, `-` and `_` (max 64), so no file outside `data/replays/` can be read.
- **CORS:** only origins listed in `FRONTEND_ORIGINS` (default `http://localhost:5173`; add your Vercel URL when deploying).
- **No login yet:** the analyst name is self-declared. Fine for a hackathon demo; add authentication before real use.

## How to run it locally
From the `HackForge` folder:

```bash
py -3.11 -m uvicorn gt.api:app --app-dir backend --port 8000
```

Then open **http://localhost:8000/docs** → `POST /api/simulate` → `POST /api/run` → try any `GET`.

Or from the command line (second terminal):

```bash
curl -X POST "http://localhost:8000/api/simulate?seed=7"
```
```bash
curl -X POST http://localhost:8000/api/run
```
```bash
curl http://localhost:8000/api/money-now
```

## How to test

```bash
py -3.11 -m pytest backend/tests/test_pipeline.py backend/tests/test_api.py -q
```

20 tests. **Pipeline:** quality end to end (F1, handle, score, evidence), alert kinds and grouping, defense outputs, saved results, analyst decisions surviving re-runs, empty case, explicit seed. **API:** health, run summary, graph integrity, explanations, reject surviving re-run plus 404s, approve twice → 409, money-now, timeline, heatmap and sankey, report, replay-name validation, live key and address checks, the SSE stream, every view safe before any run.

Full suite: **159 tests**.

## Limitations
- The Sankey's second layer is proportional: it shows how much ends up where overall, not which coin took which route.
- One case at a time (loading a new case replaces the old one, including its alerts and audit log).
- The live poller runs only while the server is awake (Render's free tier sleeps after 15 minutes idle).
- The dashboard has no login (see Safety details above).

## What M8 uses from M7
Every endpoint above. The dashboard's base URL comes from `VITE_API_URL` (default `http://localhost:8000/api`).
