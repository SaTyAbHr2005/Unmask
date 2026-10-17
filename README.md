# Unmask

**From `0x7a1b…` to a name.**

Unmask is a quantitative OSINT and blockchain engine for tracking crypto hacks. It fuses **who said what, and when** on the open internet (forums, Telegram, GitHub) with **which wallet moved what, and when** on the blockchain, so that it can:

- **Find the hacker's wallets** hidden among hundreds of split, mixed and bridged laundering wallets
- **Name the likely online identity**, with a confidence score and a plain-English reason for every link
- **Predict where the stolen money will cash out** and how much of it can still be frozen
- **Alert the parties who can freeze it**, after a human approves each alert

Built for the "Ghost Attacks" hackathon problem statement.

## How it works

```
 Simulator ─┐
 Etherscan ─┼─► MongoDB ─► Analytics ─► Fusion ─► Defense ─► API ─► Dashboard
 Alchemy   ─┤                                                  │
 OSINT     ─┘                                    alerts ◄──────┘  (human-approved)
```

Three data modes feed one pipeline:
- **Simulator:** a realistic synthetic hack that also holds the answer key, so accuracy can be measured. Works fully offline.
- **Replay:** a real past hack rebuilt from Etherscan.
- **Live:** watched wallets streamed from Alchemy.

## Status

| Module | Status |
|---|---|
| M0 Foundation · M1 Simulator · M2 Chain ingestion · M3 OSINT · M4 Analytics · M5 Fusion | ✅ done |
| M6 Defense · M7 API · M8 Frontend · M9 Deploy | ⏳ in progress |

The detailed guide for each module is in [docs/modules/](docs/modules/README.md), and the full build plan is in [docs/superpowers/plans/](docs/superpowers/plans/2026-10-17-unmask-engine.md).

## Run the tests

Requires Python 3.11.

```bash
py -3.11 -m pip install -r backend/requirements.txt
```
```bash
py -3.11 -m pytest backend/tests -q
```

## Configuration

Copy `backend/.env.example` to `backend/.env` and fill in only the keys you have. Everything works without keys, using the simulator and an in-memory database. Never commit `.env`.

## Stack

Python 3.11 · FastAPI · pandas · NetworkX · SciPy · scikit-learn · MongoDB (Atlas M0) · React + Vite · Render (backend) · Vercel (frontend). Free tiers only.

## Ethics

Synthetic identities only in demos. Every attribution stays **suspected** until a human analyst confirms it, and nothing leaves the system without human approval.
