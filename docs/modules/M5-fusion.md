# M5: Fusion (from clues to a confident, explained answer)

## In one sentence
M5 **combines all the separate clues** (timing, time zone, posted addresses, posted code, on-chain messages) into **one probability** that a group of wallets belongs to a specific online identity. It gives **a plain-English reason for every number** and keeps **tamper-evident records** of the evidence and of every human decision.

## Why it exists
M4 produces many separate numbers: a p-value, a time zone, a similarity score. An investigator, an exchange compliance officer or a judge needs one answer: *"How sure are you that `ghostfox` controls these wallets, and why?"* M5 gives that answer in a form they can check, challenge and trust.

## Where it sits

```
 attacker cluster (M4) ─┐
 identities (M3)        ├─► build_signals ─► posterior ─► decay ─► Link (score + reasons) ─► explain() ─► UI / report
 entities (M3)          │                                              │
 transfers, bytecode ───┘                                              └─► analyst confirms / rejects ─► audit() chain
                                                     every piece of data ─► record() ─► evidence store (hashed)
```

## Files

| File | What it does | Features |
|---|---|---|
| [score.py](../../backend/gt/fusion/score.py) | Clues → probability → label → explanation | #24, #25, #26, #43 |
| [evidence.py](../../backend/gt/fusion/evidence.py) | Content-hashed evidence store + tamper-evident audit log | #27, #41 |
| [schema.py](../../backend/gt/schema.py) | Adds the `Evidence` and `AuditEntry` shapes | — |

---

## 1. How the score works (`score.py`)

### The idea: likelihood ratios
Each clue gets a **likelihood ratio (LR)**: how many times more likely we'd see this clue **if the link is real** than if it isn't.
- LR 30: very strong (you rarely see this by accident)
- LR 1: neutral (tells us nothing)
- LR 0.5: evidence **against** the link

### The math (Bayes' rule, in plain words)
1. **Start sceptical.** Before any evidence, assume a 1% chance that a given identity owns the cluster (`PRIOR = 0.01`).
2. Turn that into **odds**: 1% = 1 : 99.
3. **Multiply the odds** by every clue's LR.
4. Turn the odds back into a probability.

Example: 1:99 × 30 × 20 = 600:99 ≈ **86%**.

**Safety cap:** each LR is clipped to 0.1–50, so **no single clue can decide a case on its own**. One clue maxes out at 1:99 × 50 ≈ **34%**. Getting to "high" always needs several independent clues.

### The five clues (`build_signals`)

| Clue | When it fires | LR | Comes from |
|---|---|---|---|
| `time_delta` | Whenever the person has ≥ 5 posts and the cluster has transactions | 20 if p < 0.01 · 5 if p < 0.05 · 1 otherwise | M4 latency test |
| `rhythm` | Whenever both sides have ≥ 15 timestamps | 3 if the time zones are within 1 hour · 0.5 if not | M4 time-zone inference |
| `address_mention` | **Only on a match:** the person posted a wallet address that's in the cluster | 30 | M3 extraction |
| `bytecode` | Whenever the person posted code and the cluster deployed a contract | 10 if ≥ 60% of functions match · 1 otherwise | M4 bytecode similarity |
| `onchain_message` | **Only on a match:** a cluster transaction carries a hidden message naming the person's handle | 30 | M2 message decoding |

**Why two kinds?** Statistical tests (timing, time zone, code) are reported **even when neutral**, so the explanation can honestly say "timing shows no pattern". Mention clues fire **only on a match**, because *not* being mentioned proves nothing. If the inputs for a clue are missing, **no signal is produced at all**: there are no fake placeholders.

The time-delta test runs on the person's **whole identity** (all their linked accounts from M3), not one account. The hacker's Telegram account alone had only 6 posts, too few to be significant.

### Confidence fades (`decay`)
`score × 0.5^(age / 7 days)`: without fresh evidence, confidence halves every week. Wallets get abandoned and accounts get sold, so old links shouldn't look as solid as new ones. The age is measured from the **newest activity on either side of the link** (the person's last post or the cluster's last transaction) to the case's latest data. The first design used 6 hours, which decayed the real hacker to 1.5% within a day; see M7.

### Labels (`label`)
`confirmed` / `rejected` when a human analyst has decided; otherwise **high** (≥ 80%), **medium** (≥ 50%) or **low**. Everything starts as **suspected**; only a human can confirm.

### Explanations (`explain`)
Builds one sentence an investigator can read and verify, strongest clue first. Real output on the simulator:

> **Suspected (100%): forum:ghostfox ↔ cluster 0.** Because: posted 1 address(es) belonging to the cluster, e.g. 0xa049453127…; cluster tx 0x6aca56d86e… carries the message "contact ghostfox on forum for bounty"; 32/33 posts were followed by a cluster transaction within 15 min (median 18s; randomly shifted posts: 12%), p=0.002; posted code shares 100% of its function selectors with the cluster's contract; wallets are active like a UTC+9 schedule, posts like UTC+9 — same time zone.

`explain(link, polish=True)` adds a one-line AI summary in front (Groq/Gemini, M3's `llm.py`), instructed **not to add facts**. AI is off by default, and the template alone is complete.

`link_for(cluster_id, identity, signals, age_s)` packages everything into a `Link` (id `"<cluster>:<identity>"`, score after decay, status `suspected`).

### Results on the simulator
- **forum:ghostfox** (the hacker's merged identity): **100%, high**, with all five clues
- **All 60 normal identities: low**
- Highest normal identity: **17%**. `vitorgal` had 4 of 5 posts land shortly before hacker transactions purely by chance. Testing 60 people makes one such coincidence likely, and the cap stops it from going anywhere. This is the system working as intended: a single coincidence never becomes an accusation.

## 2. Evidence you can defend (`evidence.py`)

### `record(conn, obj, kind, source_url="")` → hash
Stores any transfer, post, signal or dict as **canonical JSON** (keys sorted) under its **SHA-256 hash**:
- **Same content, same hash, stored once** (idempotent).
- If anyone later changes one byte of the stored payload, its hash no longer matches.
- `source_url` records where it came from (Etherscan link, forum URL, …).

`Link.evidence` holds these hashes, so every claim points to exact, verifiable data.

### `audit(conn, actor, action, target)` → `AuditEntry`
Records every human decision: `confirm_link`, `reject_link`, `approve_alert`, `send_alert`, `dismiss_alert`, `export_report`. Each entry contains the **ID of the previous entry**, and its own ID is a hash of (previous ID + actor + action + target + time). That forms a **hash chain**, the same idea a blockchain uses.

### `verify_audit(conn)` → True/False
Recomputes the chain from the newest entry back to the first. It returns **False** if:
- any entry was **edited** (its hash no longer matches), or
- any entry in the **middle was deleted** (the chain breaks), or
- the chain has been forked.

**Known gap:** quietly deleting only the *newest* entry can't be detected from inside the database. The fix is an outside anchor: the M7 report prints the newest entry ID, so a printed or shared report pins the chain.

Loading a new scenario clears the database, which starts a fresh, valid chain for the new case.

## How to test
From `HackForge`:

```bash
py -3.11 -m pytest backend/tests/test_score.py backend/tests/test_evidence.py -q
```

17 tests: posterior math; the single-clue cap; evidence against; never exactly zero; decay; all labels; explanation ordering; AI polish only when asked (with fallback); `link_for`; the hacker scoring ≥ 80% with all five clues; the busiest normal user scoring ≤ 20% with no placeholder signals; empty inputs; evidence idempotency and content hashing; stable key order; the audit chain verifying; edits detected; deletions detected; empty audit valid.

## Limitations (honest)
- **Naive Bayes treats clues as independent.** Some aren't fully (posting time and time zone are related). The cap limits the damage; learning weights from many simulator runs would improve it.
- The LR values (30, 20, 10, 5, 3) are **expert estimates**, not fitted from real cases.
- **Multiple testing:** checking many identities makes some chance coincidences likely (see the 17% example). The cap plus "needs several clues for high" is the safeguard.
- Single-writer audit log: two people approving at the exact same moment could fork the chain (which `verify_audit` would then flag).

## What later modules use from M5
- **M6 Defense:** high-confidence links decide which alerts to raise; `audit` records approvals and sends
- **M7 API:** `build_signals` + `link_for` inside `run()`; `explain` and `label` for `/links`; `verify_audit` for `/report`
- **M8 UI:** link cards show the score bar, label chip, explanation and each clue's LR
