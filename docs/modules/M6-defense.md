# M6: Defense (stop the money, not just trace it)

## In one sentence
M6 answers **"what can we still do about it?"**: where the stolen money is right now, **how much can still be frozen and by whom**, **which exchange it will cash out at and when**, an **early warning before an attack happens**, a filter for the **decoys** the attacker plants, and **alerts that only go out after a human approves them**.

## Why it exists
Most tracing tools stop at a pretty graph. But the money is only recoverable **until it becomes cash** at an exchange. M6 turns the analysis into action: it tells you who to call (Tether, Circle, Exchange A) and how urgently, while that's still useful.

## Where it sits

```
 attacker cluster + graph (M4) ─► freeze.py ─► holdings (where + freezable?) ─► "$31.8M can still be frozen"
                               └─────────────► predict_exits ─► "Exch-A ~22% arrived, ~21% expected in ~11h"
 all transfers + labels ───────► guards.py ─► prewarn (before the theft)  ─┐
                               └────────────► find_decoys (ignore these)   │
                                                                           ▼
                                 alerts.py ─► queue (pending) ─► human approves ─► Discord / Telegram ─► audit chain (M5)
```

## Files

| File | What it does | Features |
|---|---|---|
| [freeze.py](../../backend/gt/defense/freeze.py) | Holdings + freezability, exit prediction | #28, #29 |
| [guards.py](../../backend/gt/defense/guards.py) | Pre-attack warning, decoy and address-poisoning filter | #30, #31 |
| [alerts.py](../../backend/gt/defense/alerts.py) | Alert queue, human approval gate, Discord/Telegram delivery | #32, #42 |

---

## 1. Where is the money, and can it be frozen? (`freeze.py`)

### `holdings(transfers, wallets, labels)` → list of `Holding`
For every wallet in the attacker cluster: **money in − money out** per asset. Balances under $100 (leftover gas) are skipped. Money **already deposited at exchanges** is listed too.

Each holding says **who can freeze it**:

| Where the money sits | Freezable? | Who to contact |
|---|---|---|
| USDT in any wallet | ✅ | **Tether** (can freeze USDT balances on request) |
| USDC in any wallet | ✅ | **Circle** |
| Deposited at an exchange | ✅ | **That exchange** (can freeze the account) |
| Raw ETH in a private wallet | ❌ | Nobody: only watch it and wait for it to move |

This is the **freezability** angle most tools miss. It tells the team **where to spend their time**: chasing $10M of raw ETH achieves nothing today, while one email to Tether can lock $10M of USDT.

### `predict_exits(G, sources, labels, total_usd)` → list of `ExitPrediction`
1. **Follow the money:** start with 100% of the stolen funds at the seed wallet. At each step, every wallet passes its share on **in proportion to what it actually sent**. Exchanges **absorb** what reaches them: that money has **arrived**.
2. **Predict the rest:** money still sitting in wallets is expected to leave **the same way the attacker already cashed out** (same exchanges, same proportions). If there are no cash-outs yet, it's spread over the exchanges with the most traffic.
3. **ETA:** the median time the attacker's wallets hold money before passing it on.

Bridge deposits that M4 already linked to the other chain are followed across the bridge rather than lost inside it.

Each row: exchange, address, **share** of the stolen funds, **USD**, **ETA** (predicted rows), **arrived** yes/no.

### Results on the simulator ($42M theft)

| Exchange | Share | USD | Status |
|---|---|---|---|
| Exch-A | 22.1% | $9.3M | arrived |
| Exch-A | 21.5% | $9.0M | predicted, ~11h |
| Exch-B (Ethereum) | 15.9% | $6.7M | arrived |
| Exch-B (Ethereum) | 15.5% | $6.5M | predicted, ~11h |
| Exch-B (Arbitrum) | 12.7% | $5.3M | arrived |
| Exch-B (Arbitrum) | 12.3% | $5.2M | predicted, ~11h |

**Holdings:** $41.9M of $42M located, and **$31.8M can still be frozen**: $21.2M at exchanges and $10.5M in USDT (Tether). The remaining $10.1M is raw ETH that nobody can freeze. Both real exits (Exch-A, Exch-B) are correctly identified.

## 2. Guards (`guards.py`)

### `prewarn(transfers, labels)`: catch it **before** the theft
Attackers prepare: they fund a fresh wallet through a mixer, deploy the exploit contract, and test it. A wallet is flagged when, **within 24 hours of being funded through a mixer** (directly, or via one in-between funder wallet), it:
- deploys a contract, **and**
- makes at least 2 test calls to it.

It produces a `prewarn` alert stamped with the time the pattern completed.
**Simulator:** fires on the attacker's wallet **5.5 hours before the theft**. In a real deployment, that's enough time for the protocol to pause its contracts.

### `find_decoys(transfers, attacker, known)`: ignore the bait
Attackers pollute the trail on purpose:
- **Dust:** tiny payments (between $0 and $1) to innocent wallets so they look connected. A dust receiver that never pays the attacker back is a decoy. One that *does* pay back is treated as a possible accomplice, not a decoy. Zero-value transactions (messages, contract calls) are not dust.
- **Address poisoning:** an address with the **same first 6 and last 4 characters** as a real address (what most wallets display), hoping someone copies the wrong one. `is_lookalike(a, b)` checks this, and any look-alike of a known address that the attacker paid is flagged.

**Simulator:** found **22 of 22** planted decoys, including both look-alike addresses, with **no** attacker wallets wrongly flagged.

## 3. Alerts with a human in the loop (`alerts.py`)

The engine **proposes**; a person **decides**. Nothing leaves the system without an approval click.

| Function | What it does |
|---|---|
| `queue(conn, alerts)` | Saves proposals as **pending**. If an alert already exists it is **left untouched**, so re-running the analysis never resets a decision. |
| `approve(conn, alert_id, actor)` | pending → **approved** (written to the audit chain) → sent to the configured channel → **sent** (audited again). If no channel is configured or sending fails, it stays **approved** and nothing crashes. |
| `dismiss(conn, alert_id, actor)` | pending → **dismissed** (audited) |

Approving something that isn't pending (or doesn't exist) raises an error, which the API turns into a clear message. You can't send the same alert twice.

**Delivery channels** (first one configured wins):
1. **Discord:** `DISCORD_WEBHOOK_URL` (create in a Discord channel → Integrations → Webhooks)
2. **Telegram:** `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` (create a bot with @BotFather)

Message format: `[Unmask] EXIT — Exch-A: ~$9M likely to reach Exch-A in ~11h`

## How to test
From `HackForge`:

```bash
py -3.11 -m pytest backend/tests/test_freeze.py backend/tests/test_guards.py backend/tests/test_alerts.py -q
```

20 tests, all offline: flow shares; prediction for held money; fallback to busy exchanges; holdings and freezers; simulator exits and freezable totals; pre-warning before the theft and its three required parts, the 24-hour window and the funder hop; look-alikes; decoys on the simulator; zero-value and paid-back cases; queueing, approval, double approval, unknown alert, no channel, failed send, re-queue safety, dismiss; Discord and Telegram delivery (faked).

## Limitations (honest)
- **Exit prediction ignores the order of time.** Money is spread over a wallet's outgoing transfers even if some happened before the money arrived. Fine on the simulator; a time-aware walk is the upgrade if replays misrank.
- Predictions assume the attacker **keeps using the same exchanges**. A switch to a new exchange shows up only once it happens.
- The ETA is coarse: one median holding time for all wallets.
- Freezability is a rule of thumb: whether Tether, Circle or an exchange actually freezes depends on law-enforcement requests and their own policies.
- Pre-attack warning needs labels to know which addresses are mixers. Unlabeled mixers aren't recognised.
- Prices are fixed demo values (ETH = $3,000).

## What later modules use from M6
- **M7 Pipeline/API:** `holdings`, `predict_exits`, `prewarn`, `find_decoys` inside `run()`; alerts behind `/alerts`, `/alerts/{id}/approve` and `/dismiss`; holdings and exits behind `/money-now` and `/report` (freeze-request letters)
- **M8 UI:** "Money now" cards, exit list with "freeze possible" badges, alert queue with Approve & send / Dismiss
