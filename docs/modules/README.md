# Unmask: module guide

Unmask connects **who said what, and when** on the open internet (OSINT) with **which wallet moved what, and when** on the blockchain. It finds the hacker's wallets, names the likely online identity with an explained confidence score, predicts where the stolen money will be cashed out, and alerts the people who can freeze it.

Each module has its own detailed guide. Read them in order: each builds on the previous ones.

| Module | Status | What it does | Guide |
|---|---|---|---|
| M0 Foundation | ✅ done | Data shapes every module shares, plus MongoDB storage | [M0-foundation.md](M0-foundation.md) |
| M1 Attack Simulator | ✅ done | A fake but realistic hack, with an answer key for measuring accuracy | [M1-attack-simulator.md](M1-attack-simulator.md) |
| M2 Chain Ingestion | ✅ done | Brings in Etherscan replays and the Alchemy live stream, and cleans the data | [M2-chain-ingestion.md](M2-chain-ingestion.md) |
| M3 OSINT Ingestion | ✅ done (Telegram optional) | Collects RSS, GitHub and Telegram text; extracts addresses and handles; links aliases into one identity | [M3-osint-ingestion.md](M3-osint-ingestion.md) |
| M4 Analytics | ✅ done | The math: graph, clustering, gas funders, bridge matching, bot and time-zone detection, time-delta test, bytecode match | [M4-analytics.md](M4-analytics.md) |
| M5 Fusion | ✅ done | Combines clues into a probability per wallet-to-identity link, with plain-English reasons, a hashed evidence store and a tamper-evident audit log | [M5-fusion.md](M5-fusion.md) |
| M6 Defense | ✅ done | Where the money is and who can freeze it, exit prediction, pre-attack warning, decoy filter, human-approved alerts | [M6-defense.md](M6-defense.md) |
| M7 Pipeline + API | ✅ done | One `run()` over every module (0.85 s) plus the FastAPI endpoints the dashboard uses | [M7-pipeline-api.md](M7-pipeline-api.md) |
| M7.1 Integration pass | ✅ done | Connects 7 built-but-unused features (OSINT collection, mempool, wallet features, bot scores, matrix, subset-sum deposits) plus time-to-freeze and optional AI wording | [M7.1-integration.md](M7.1-integration.md) |
| M8 Frontend | ✅ done | Scroll-driven 3D story, live case file (3D money graph, suspects, alerts, timeline, clock, routes, matrix), printable dossier with privacy masking | [M8-frontend.md](M8-frontend.md) |
| M8.1 Real data | ✅ done | All 9 services tested with real keys; four real hacks (Euler, KyberSwap, Harmony, Beanstalk) load from the website and match the public record; fixes for what real data exposed | [M8.1-real-data.md](M8.1-real-data.md) |
| M8.2 Landing page | ✅ done | New home page: a 3D night sky drawn from the real Euler trace, scroll-pinned Trace → Locate → Freeze, the four real hacks against the public record; the story moved to /how-it-works | [M8.2-landing.md](M8.2-landing.md) |
| M9 Demo + Deploy | ⏳ next | Demo script, Render + Vercel deploy | — |

## Big picture

```
 DATA IN                         CORE                                 OUT
 ───────                         ────                                 ───
 Simulator (M1) ─┐
 Etherscan (M2) ─┼─► MongoDB (M0) ─► Analytics (M4) ─► Fusion (M5) ─► Defense (M6) ─► API (M7) ─► UI (M8)
 Alchemy   (M2) ─┤                                                                      │
 OSINT     (M3) ─┘                                                         alerts ◄─────┘ (after human approval)
```

## Running the tests
From the `HackForge` folder (system Python 3.11, no venv):

```bash
py -3.11 -m pip install -r backend/requirements.txt
```
```bash
py -3.11 -m pytest backend/tests -q
```

Run the website: see [M8-frontend.md](M8-frontend.md#how-to-run).

Full plan: [docs/superpowers/plans/2026-10-17-unmask-engine.md](../superpowers/plans/2026-10-17-unmask-engine.md)
