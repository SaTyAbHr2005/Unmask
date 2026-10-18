# Unmask: the complete guide (problem, solution, demo, judges' questions)

Read this top to bottom once. After that, use section 8 (the demo) and section 9 (questions) on the day.

---

## 1. The problem, in plain words

The problem statement is called **Ghost Attacks**.

1. A hacker steals **$42M** from a crypto (DeFi) protocol at 2:14 AM.
2. Within minutes a **bot** splits the money into hundreds of small, uneven transfers. It sends them through **bridges** (to other blockchains) and **mixers** (Tornado Cash, which blends coins so the trail breaks).
3. Two teams try to catch the hacker, but they can't combine their work:
   - **OSINT investigators** read forums, Telegram and GitHub. They find clues like a username, a leaked IP or a code snippet, but can't connect a forum post to a wallet.
   - **Blockchain analysts** see every transaction, but only as anonymous addresses (`0x7a1b…`). The bot also changes timing and amounts to look like normal market noise.
4. They match timestamps by hand in spreadsheets. The hacker creates wallets faster than they can check them.
5. After a few hours the hacker **cashes out at an exchange**. Once the money is in a bank under a fake identity, it's gone for good.

**What the problem statement asks us to build:** a "Quantitative OSINT Blockchain Engine" that:
- **(A)** automatically scrapes public threat feeds and developer repositories for identity markers;
- **(B)** treats the live blockchain ledger as a mathematical matrix;
- **(C)** uses statistics (it names **time-delta latency analysis** and **graph clustering**) to link anonymous wallets to real-world identities.

The story adds two implied needs: cope with **bridges, mixers and bots**, and act **before the cash-out**.

---

## 2. What Unmask is

**Unmask** connects *who said what, and when* on the internet with *which wallet moved what, and when* on the blockchain. It then:

1. finds **all the hacker's wallets**, starting from one address;
2. names the **most likely online identity**, with a confidence score and the evidence behind it;
3. shows **where the stolen money is right now** (held, in a mixer, at an exchange, given back);
4. **predicts the next cash-out** and drafts **freeze requests** to the exchange or stablecoin company that can freeze the money. A person approves each request before anything is sent.

Website pages:

| Page | Address | What it's for |
|---|---|---|
| Home | `/` | What Unmask is, the real-hack results, buttons to try it |
| How it works | `/how-it-works` | A 3-minute scroll story of the $42M attack from the problem statement |
| Case file | `/case` | The working tool: load a case, see the graph, suspects, money and alerts |
| Dossier | `/report` | A printable report with the evidence and the freeze letters |

---

## 3. Does it satisfy the problem statement? Point by point

| The problem statement asks | What Unmask does | Where you see it |
|---|---|---|
| **(A) Scrape threat feeds and code repositories** | Collects posts from 5 security news feeds (rekt.news, SlowMist, Chainalysis, Cointelegraph, Web3 Is Going Great), **GitHub** code search, and public **Telegram** channels (optional). Pulls out the identity markers: wallet addresses, transaction hashes, usernames, emails, IPs and ENS names. | Case file → **Collect public posts** |
| **Link one person's many accounts** | Spots one person using several names (e.g. `ghostfox` and `fox_ghost`) from name similarity and writing style. | Suspects panel |
| **(B) The ledger as a matrix** | Builds a **wallet × time matrix** (activity of each wallet per time slot), a **feature vector per wallet** (volume, timing, gas habits), and the **transaction graph**. | Case file → activity matrix, 3D money graph, click any wallet |
| **(C) Time-delta latency analysis** | Checks whether a person's posts land *just before* the wallets move, more often than chance. A **permutation test** shuffles the post times 500 times to get a p-value. In the simulated attack: 32 of 33 posts land minutes before a move, which happens by chance about 2 times in 1,000. | Suspects panel → evidence list |
| **(C) Graph clustering** | Groups wallets that belong to one owner: money flows (Louvain community detection), **shared gas funders** (who paid the fees for a fresh wallet), and bridge matching (same amount out on one chain, in on another, minutes apart). | 3D graph: purple = attacker wallets |
| **(C) Link wallets to identities** | Every clue is a **likelihood ratio** (how much more likely if this person is the attacker). They're combined with Bayes' rule into one probability, with a plain-English reason for each clue. Confidence fades if nothing new happens for a week. | Suspects panel: % score and the reasons |
| **Bots that mimic market noise** | **Bot score**: real people act at random-ish times and round numbers; bots don't (KS test against random timing, round-amount check, Benford's law on the first digits). | Click a wallet → bot score |
| **Bridges and mixers** | Labeled mixers (Tornado Cash) and bridges are tracked as exits. Money into a mixer is counted ("Still inside the mixer"). | Money panel; route chart |
| **Act before the cash-out** | **Exit prediction** (which exchange next, roughly when), **freezability** (USDT and USDC can be frozen by Tether and Circle; exchange deposits by the exchange), a **ready-to-send freeze letter**, and alerts to Discord or Telegram **only after a person clicks Approve**. | Alerts queue; Dossier |
| *Extra:* where the attacker lives | **Time-zone inference** from the hours the wallets and the posts are active. | The clock |
| *Extra:* trust | Every attribution stays "suspected" until a person confirms it. Evidence is hashed and kept in a **tamper-evident audit log**. Personal details (emails, IPs) are masked until someone records a reason to reveal them. | Dossier |

**So:** all three named requirements are built and run on real data. Part of the "live" side isn't automatic yet (section 6).

---

## 4. How it works (one case, start to finish)

```
 Data in                      Engine (one run, under a second)                     Out
 ───────                      ────────────────────────────────                     ───
 Blockchain (Etherscan,  ─┐   1 build the transaction graph and the matrix
   Alchemy live)          ├─► 2 cluster the attacker's wallets                ─► website
 Posts (RSS, GitHub,      │   3 extract identity markers from posts           ─► dossier and freeze letters
   Telegram)             ─┘   4 score each person-to-wallet link (Bayes)      ─► alerts (after a person approves)
                              5 where is the money, what's freezable, next exit
```

1. **Collect.** Transactions come from Etherscan (history) or Alchemy (live). Posts come from RSS, GitHub and Telegram. Everything goes into MongoDB in one format (lowercase addresses, UTC timestamps).
2. **Cluster.** Starting from one known attacker address, Unmask follows the money and groups the wallets one person controls.
3. **Extract.** Addresses, hashes and usernames are pulled out of every post, and aliases are merged.
4. **Fuse.** For each person, five tests produce clues:
   - they posted a wallet address from the cluster;
   - an on-chain message names them;
   - their posts come just before the money moves (latency test);
   - code they pushed matches the deployed attack contract;
   - their posting hours match the wallets' hours.

   The clues are combined into one probability with reasons.
5. **Defend.** Unmask works out where the money is, what can be frozen and who to ask, and predicts the next exchange. It drafts the letters, and a person approves before anything is sent.

---

## 5. Why we use three kinds of data

| Mode | What it is | Why it matters |
|---|---|---|
| **Simulated attack** | A realistic fake hack: wallets, bot splitting, mixer, bridge, exchange, plus fake forum, GitHub and Telegram posts, with an **answer key** | It's the only way to **measure accuracy**. Real hacks don't publish who did it. On 20 random attacks Unmask named the right attacker every time: 100% precision and ≥99.7% recall on wallets, with the time zone exact in 17 of 20. Every attack number (e.g. 7, 42, 1234) is a different attacker. |
| **Real hacks** (Euler, Harmony, Beanstalk, KyberSwap) | Real transactions pulled from Etherscan | Proves the blockchain side works on **real messy data**, and the numbers match what investigators reported (table below). |
| **Trace any address** | Paste any address, pick dates and a chain | **The judge picks the data.** It's traced live from the blockchain. |

| Real hack | Unmask finds | Public record |
|---|---|---|
| Euler, Mar 2023 | $191.6M traced, $189.4M given back to Euler | ~$197M, nearly all returned |
| Harmony, Jun 2022 | $98.1M into Tornado Cash in 857 deposits of 100 ETH | 85,700 ETH (~$98M) into Tornado by 2 July |
| Beanstalk, Apr 2022 | $74.4M traced, $74.3M into Tornado | ~$76M kept |
| KyberSwap, Nov 2023 | $33.5M traced on 3 chains, freeze letters to Circle and Tether | ~$48M |

**Why no suspect on real hacks?** These hackers left no public posts we can match, so Unmask names **nobody**. That's on purpose: it never attaches a real person's name to a wallet without evidence. The identity side is shown on the simulated attack, where we can prove it's right.

---

## 6. "Is it continuous monitoring?" Yes: Watch live

The problem statement says "automatically scrape" and "the **live** blockchain ledger". In the case file, **Watch live** does this:

- **Every block (12 s):** it checks the attacker's wallets for new transfers (the real blockchain through Alchemy, or the simulated attacker carrying on). New transfers are stored and the analysis **reruns by itself** in under a second. Every new deposit at an exchange or mixer raises its own alert ("Just now: 28.16 ETH moved … to Exch-A. Ask their compliance team to freeze it.").
- **Every 10 minutes:** it re-collects news feeds, GitHub and Telegram in the background, then reruns.
- The money panel, exits, suspects and alerts update on screen without anyone clicking.
- **A person still approves** every alert before it's sent.
- **Mempool check:** the case file also shows how many of the attacker's transactions are waiting to be confirmed right now, before they're even in a block.

**What to say:** "Watch live turns a case into continuous monitoring: every block it checks the attacker's wallets, reruns the engine and puts new alerts in the queue. Every 10 minutes it re-scrapes the public sources. The analyst only approves."

**Be honest about its limits:**
- It stops after 30 minutes, to protect the free API quota.
- It runs inside the server, so it stops if the free Render server sleeps.
- On a real old hack the wallets are quiet, so nothing new appears. Use the simulated attack to show alerts arriving live.

## 7. Is it production-ready?

**Already in place:**
- 199 automated tests.
- Built only on free services: MongoDB Atlas, Etherscan, Alchemy, GitHub, Groq/Gemini, Discord/Telegram.
- Holds up against real-world failures:
  - retries with backoff on rate limits;
  - errors are never cached as "no data";
  - every Etherscan answer is cached;
  - fake tokens and spam airdrops are ignored;
  - money is priced at the ETH price on the hack date.
- Safety:
  - nothing is sent without a person's approval;
  - tamper-evident audit log;
  - personal data masked;
  - "suspected" until confirmed.
- **Deployment target:** backend on Render (free), frontend on Vercel (free), database on MongoDB Atlas (free). The frontend already reads the API address from `VITE_API_URL`, and the backend reads allowed sites from `FRONTEND_ORIGINS`.

**Not done yet (say so if asked):**

| Gap | Why it matters | Fix |
|---|---|---|
| No login | Anyone with the link can load cases or approve alerts | Add sign-in; only analysts can approve |
| One case at a time, shared by everyone | Two judges loading different cases would replace each other's case | Store a case ID per user or session |
| Watch mode lives in the server process and stops after 30 minutes; Render's free tier sleeps after 15 idle minutes | Monitoring stops when the server sleeps or restarts | A paid always-on worker, or a scheduled job |
| The Etherscan cache isn't in the repository | A fresh server takes 1–5 minutes to load each real hack the first time | Open each case once right after deploying |
| Deploy not done yet | — | M9 |

**What to say:** "It's a working prototype built like a product: tested, deployable for free, with safety gates. For a real agency we'd add sign-in, a case per user and an always-on worker so watch mode runs for days, not 30 minutes."

---

## 8. Run it and test it yourself

**Live site:** https://unmask-five.vercel.app. Open https://unmask-api.onrender.com/api/health 2–3 minutes before presenting to wake the free server, then load attack 7 (about 40 seconds on the free plan) so it's ready.

### First time only (from the `HackForge` folder)

```bash
py -3.11 -m pip install -r backend/requirements.txt
```

```bash
npm install --prefix frontend
```

### Every time: two terminals, both in `HackForge`

Terminal 1, the engine (API):

```bash
py -3.11 -m uvicorn gt.api:app --app-dir backend --port 8000
```

Terminal 2, the website:

```bash
npm --prefix frontend run dev
```

Open **http://localhost:5173**. With `MONGODB_URI` set in `backend/.env`, cases are saved in your Atlas database.

### The demo (about 5 minutes), with what to say

| # | Click | You should see | Say |
|---|---|---|---|
| 1 | Open **Home** | The night sky: 1,681 real addresses from four traced hacks, Euler in the middle | "These are four real hacks. Every dot is a wallet the stolen money touched; purple ones are the attackers'." |
| 2 | Scroll down | Trace → Locate → Freeze, then four real hacks | "It traces, locates the money and drafts the freeze. Here it is on four real hacks, next to what investigators reported." |
| 3 | **Case file** → Attack `7` → **Load simulated attack** | The graph, a suspect (`ghostfox`), a confidence score, alerts | "This is the $42M attack from the problem statement, with posts. Unmask names the attacker and shows why." |
| 4 | Open the suspect's evidence | 5 clues with reasons | "Each clue is a likelihood ratio. The latency test: their posts land minutes before the money moves, which happens by chance about 2 in 1,000." |
| 5 | Look at the money panel and alerts | Can be frozen, at exchanges, next exit | "It predicts the next cash-out and drafts the letter. Nothing is sent until I approve." |
| 6 | **Approve** one alert | It's marked approved (and sent to Discord/Telegram if configured) | "A person stays in charge. Every approval goes into the audit log." |
| 6b | Click **Watch live**, wait about a minute | New moves appear in the feed; "Just now…" alerts arrive in the queue; the money panel updates by itself | "This is continuous monitoring. Every block it checks the attacker's wallets, reruns and raises alerts. Every 10 minutes it re-scrapes the sources. I only approve." |
| 7 | Click **Stop watching**, change Attack to `42`, load again | A different attacker, amount and time zone | "Every number is a new attack with an answer key. It's right on all 20 we tested." |
| 8 | **Real hack** → Harmony → **Load real hack** | $98.1M into Tornado Cash | "Real data: 857 deposits of 100 ETH into Tornado in six days. That's what Elliptic reported." |
| 9 | **Dossier** → on the Tether letter click **Mark as sent**, then **Funds frozen** | The letter turns green ("Frozen · your name, time"); in the case file, "can still be frozen" drops and a "Frozen" row appears | "Unmask can't freeze crypto, only the exchange or the stablecoin company can. It writes the request with the evidence, says how to send it, and tracks the answer in the audit log." |
| 10 | (If asked) **Trace any address** | A live trace of their address | "Pick any hack. It's traced live from the blockchain." |

**Before the demo:** load each real hack once so it's cached (seconds instead of minutes). Have the simulated attack loaded before you start.

---

## 9. Questions judges will likely ask

**How do you know it's right?**
The simulator has an answer key: 100% precision on 20 random attacks. On real hacks, the totals match published investigations (section 5).

**Why doesn't it name the real Euler hacker?**
There are no public posts to match. Unmask names nobody without evidence, which is a deliberate safety rule.

**What's new compared with Chainalysis or Etherscan?**
Those trace money. Unmask also fuses *posts* with *transactions* statistically:
- the latency test;
- matching the time zone of posts and wallets;
- bytecode matching between a GitHub push and the deployed contract;
- explained Bayesian scores.

It also measures its own accuracy, and it is free.

**What if the hacker uses a bot to look like normal noise?**
The bot score catches machine timing and amounts. Clustering by shared gas funders still links fresh wallets, because someone has to pay their fees.

**What about mixers?**
Money into Tornado is tracked and counted. A mixer breaks the money trail, but not the *timing* trail: posts and wallet activity still line up in time.

**Is it continuous?**
Yes: **Watch live** (section 6). Show it on the simulated attack.

**Could a researcher who posts the hacker's address be accused?**
No. A mention only counts when the address isn't public: not a seed from the post-mortem, and posted by only one person. On Euler, researchers who quoted the hacker's address in their code score at the baseline (about 1–3%), not as suspects.

**Could it wrongly accuse someone?**
Every link stays "suspected" until a person confirms it. Confidence fades without fresh evidence. Personal details stay masked. Nothing goes out without approval.

**Why is KyberSwap lower than reported?**
Its money passes through busy trading pools that are too big to load whole. Unmask counts only what it can verify and labels the rest "last seen".

**How does it actually freeze the money?**
No software can freeze crypto from outside: only the exchange (for deposits), Tether (USDT) or Circle (USDC) can. Unmask:
1. finds what's freezable and by whom;
2. predicts where the money goes next;
3. writes the freeze letter with the evidence, and says how to send it (the company's official security or law-enforcement channel, a police report, help from incident-response groups such as SEAL 911);
4. records what happened: sent → replied → frozen or declined. Each step goes into the audit chain, and confirmed money moves to "Frozen" in the money panel.

Sending stays manual on purpose: an accusation should never go out automatically.

**Does it cost anything?**
No. Everything runs on free tiers.
