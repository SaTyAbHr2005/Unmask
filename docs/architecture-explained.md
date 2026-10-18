# The architecture, explained from zero

This guide explains every term in the [architecture diagram](architecture.png) for someone new to blockchain and security. Each term gets **what it is**, in plain words (often with an everyday comparison), and **what Unmask uses it for**.

Read part 1 first: it covers the blockchain basics that everything else builds on. Parts 2–7 follow the diagram from left to right. Part 8 runs one hack through the whole system so you can see the terms working together.

---

## Part 1: blockchain basics (read this first)

**Blockchain**
A public record book of every money movement, copied on thousands of computers around the world. Anyone can read it, nobody can secretly change it, and nothing is ever deleted.
*In Unmask:* this is half of our evidence. Every movement of stolen money is recorded on it forever.

**Block**
One page of that record book. On Ethereum a new page is added roughly every **12 seconds**, holding the latest batch of transactions.
*In Unmask:* Watch mode checks for new moves once per block, every 12 seconds.

**Transaction (tx)**
One entry in the record book: "this wallet sent this much to that wallet", or "this wallet ran this program".
*In Unmask:* we call each money movement a **transfer**. Thousands of them make up one case.

**Transaction hash (tx hash)**
A unique ID for every transaction, like a receipt number (e.g. `0x298bde3f…`).
*In Unmask:* used to tell transfers apart, to avoid counting one twice, and to point at exact evidence in alerts and reports.

**Wallet and address**
A wallet is like a bank account; its address is its public account number, a long code like `0x7a1b…e3f0`. Anyone can create as many wallets as they like, for free, without giving a name. That's why hackers are anonymous.
*In Unmask:* the whole job is to work out which of thousands of anonymous addresses belong to the same hacker, and who that hacker is.

**Private key**
The secret password that controls a wallet. Whoever has it can move the money.
*In Unmask:* never used. We only read public data.

**ETH (Ether)**
The main currency of the Ethereum blockchain.
*In Unmask:* valued in dollars at its price **on the day of the hack** (Euler 2023: $1,673), so old hacks aren't valued at today's price.

**Token (ERC-20)**
Other currencies that live on top of Ethereum, created by programs. ERC-20 is the standard rulebook most tokens follow, so wallets and exchanges can handle them the same way.
*In Unmask:* stolen money is often tokens, so we read token transfers as well as ETH.

**Stablecoin: USDT, USDC, DAI**
Tokens designed to always be worth $1.
- **USDT** is issued by the company **Tether**, and **USDC** by the company **Circle**. Because a company controls them, **the company can freeze them** in a hacker's wallet.
- **DAI** is run by a program, so nobody can freeze it.

*In Unmask:* USDT and USDC holdings are marked **freezable**, and Unmask drafts the freeze request to Tether or Circle.

**WETH (Wrapped ETH)**
ETH packed into token form so programs can trade it. "Wrapping" turns ETH into WETH and "unwrapping" turns it back, always one for one.
*In Unmask:* wrapping doesn't produce a normal token record, so Unmask adds the WETH side itself. Without this, Beanstalk's profit looked stuck as $74M of WETH.

**Smart contract**
A program that lives on the blockchain and runs automatically, like a vending machine: put money in, get a fixed result out. Nobody can stop or change it once it's running.
*In Unmask:* hackers attack bugs in contracts, and also write their own contracts to carry out the attack.

**DeFi protocol**
"Decentralized finance": a bank-like service (lending, trading, savings) run entirely by smart contracts, with no bank staff. Euler, Beanstalk and KyberSwap are DeFi protocols.
*In Unmask:* these are the victims in the real cases.

**Exploit / hack**
Using a bug in a contract to take money it was never meant to give out. The Ghost Attacks problem statement describes a $42M exploit.

**Flash loan**
A huge loan (millions) that must be borrowed and repaid within **one transaction**. If it isn't repaid, the whole transaction is cancelled. Hackers use flash loans to get enormous temporary funds for an attack.
*In Unmask:* flash loans make totals look huge, because money comes in and goes straight back out. Counting only fully loaded wallets keeps the numbers honest.

**Gas, gas fee, gas price**
Every transaction costs a small fee, called gas, paid in ETH to the computers that run the network. A brand-new wallet has no ETH, so **someone has to send it ETH first** to pay its fees.
*In Unmask:* this is the **gas-funder** clue. Whoever paid a fresh wallet's fees is probably its owner. Hackers often fund all their new wallets from one place, which links them.

**Nonce**
A counter of how many transactions a wallet has sent (0, 1, 2…).
*In Unmask:* kept with each transfer; it helps describe a wallet's habits.

**Internal transaction**
A movement of ETH made **by a program** rather than a person, for example a trading contract paying out ETH after a swap. It doesn't appear in a wallet's normal transaction list.
*In Unmask:* we read internal transactions too. Without them, Harmony's hacker seemed to send 85,700 ETH to Tornado Cash that he'd never received.

**Chains: Ethereum, Arbitrum, Polygon**
Separate blockchains. Ethereum is the main one. Arbitrum and Polygon are cheaper, faster networks connected to it. Money can move between them.
*In Unmask:* we read all three, because they're the ones Etherscan's free plan covers. KyberSwap's hack spanned all three.

**Mempool**
The waiting room: transactions that have been sent but aren't in a block yet. Seeing them means seeing a move **before it's final**.
*In Unmask:* the case file shows how many of the hacker's transactions are waiting in the mempool right now.

**Block explorer (Etherscan)**
A website (and API) for reading the blockchain: look up any address and see its history.
*In Unmask:* Etherscan is where real hack histories come from.

**Mixer (Tornado Cash)**
A service that pools many people's coins and pays them out to fresh addresses, so you can't tell whose coins went where. It's like many people putting cash into one bag and each taking the same amount back out. Hackers use it to break the money trail.
*In Unmask:* money sent to a mixer is tracked as "Still inside the mixer". A mixer breaks the money trail, but not the **timing** trail.

**Bridge**
A service that moves money from one blockchain to another: money locked on chain A, the same amount released on chain B. Hackers use bridges to jump chains and confuse trackers.
*In Unmask:* **bridge matching** pairs "X left chain A" with "X arrived on chain B minutes later".

**DEX and swap**
A decentralized exchange: a smart contract that trades one token for another (a swap) with no company involved. Uniswap is one.
*In Unmask:* swaps are labeled, so a hacker turning USDC into ETH isn't mistaken for the money disappearing.

**Exchange (centralized, e.g. Binance)**
A company where people buy and sell crypto for normal money. Exchanges check customers' identities (KYC, below) and **can freeze accounts**. This is where hackers **cash out**.
*In Unmask:* the most important place to watch. Money arriving at an exchange can still be frozen if the exchange is told in time.

**Deposit address**
The address an exchange gives one customer to send money into their account. It points to one specific account.
*In Unmask:* the freeze letter names the exact deposit address, so the exchange knows which account to freeze.

**Cash-out**
Turning stolen crypto into normal money in a bank. Once that happens, as the problem statement says, the money is gone for good.
*In Unmask:* the whole defense side exists to catch the money before cash-out.

**Freeze**
Locking money so it can't move. Exchanges can freeze accounts, and Tether and Circle can freeze USDT and USDC.

**KYC (Know Your Customer)**
The identity checks exchanges must do (ID card, selfie). It's why a hacker's exchange account can lead to a real person, through the police, not through us.

**Address poisoning, fake tokens and dust**
- **Address poisoning:** scammers create addresses that look like real ones (same first and last characters), hoping someone copies the wrong one.
- **Fake tokens:** anyone can create a token and call it "DAI", even though it's worthless.
- **Dust:** tiny amounts sent to wallets to plant traps or noise.

*In Unmask:* tokens are priced only by their **real contract address**, so fake "DAI" counts as $0. This once inflated Euler to $272M before it was fixed. Dust and look-alike addresses are filtered out as **decoys**.

**On-chain message**
A transaction can carry a short text note in its data field. Some hackers leave messages ("contact me for a bounty").
*In Unmask:* if a message names a username, that's a strong clue linking the wallet to that person.

**Bytecode, function selectors, deploy**
- **Deploying** a contract means uploading a program to the blockchain.
- **Bytecode** is the program in machine form.
- **Function selectors** are short codes for each command the program has (like the names of its buttons).

*In Unmask:* if code someone posted on GitHub has the same buttons as the attack contract, that's a clue they wrote it (**bytecode similarity**).

---

## Part 2: column 1, data sources

**Etherscan API V2**
- An **API** is a way for one program to ask another for data (like ordering from a menu instead of walking into the kitchen).
- An **API key** is a password that identifies you to the service.

Etherscan's API returns any wallet's full history.
*In Unmask:* loads the real hacks and "Trace any address" on Ethereum, Arbitrum and Polygon.

**Free tier and rate limit**
Services let you use them free up to a limit, such as 5 requests per second. Go over and you're blocked for a moment.
*In Unmask:* everything runs on free tiers. We pace requests, retry politely ("backoff") and save answers on disk ("cache") so we stay under the limits.

**Alchemy (node / RPC)**
A **node** is a computer that holds a copy of the blockchain; **RPC** is how you ask it questions. Alchemy runs nodes you can rent, with a free tier.
*In Unmask:* used for **live** data: new blocks for the watched wallets (Watch mode) and the mempool count.

**Binance prices**
Binance's public daily prices.
*In Unmask:* gives ETH's price on the hack date.

**OSINT (Open-Source Intelligence)**
Gathering information from **public** sources: news, forums, code sites, social media. Detectives use it to find clues like usernames, leaked emails or code.
*In Unmask:* the other half of our evidence. The problem statement's core ask is fusing OSINT with blockchain data.

**RSS feed**
A standard way websites publish their latest articles, so programs can read them automatically.
*In Unmask:* we read five security news feeds (rekt.news, SlowMist, Chainalysis, Cointelegraph, Web3 Is Going Great).

**GitHub commits and code search**
GitHub is where programmers store code. A **commit** is a saved change with an author and a time. **Code search** finds code containing a phrase, such as a wallet address.
*In Unmask:* we search for attack-style code and for the hacker's addresses. Hackers sometimes test their attack code in public first.

**Telegram public channels**
Public group chats; hackers and scammers sometimes talk there.
*In Unmask:* optional source of posts.

**Attack simulator and answer key ("ground truth")**
A program that creates a realistic fake hack: wallets, splitting into hundreds of pieces, mixer, bridge, exchange, plus fake forum and Telegram posts by the "hacker". It also records the **answer key**: which wallets and which username really belong to the attacker.
*In Unmask:* real hacks never publish who did it, so the simulator is how we **prove accuracy**: we compare Unmask's answer with the key. It named the right attacker in 20 of 20 random attacks. Each attack number is a different attacker; number 7 is the problem statement's $42M story.

**Labels**
A list of known addresses and what they are: "Binance hot wallet", "Tornado Cash", a bridge, and the real contracts of USDT, USDC, DAI and WETH.
*In Unmask:* tells the engine which addresses are exchanges, mixers or bridges, which aren't followed further, and which tokens are real.

---

## Part 3: column 2, ingest and store

**Ingestion**
Bringing raw data in and cleaning it into one standard format.

**Normalization**
Making everything consistent: all addresses lowercase, all times in one format (UTC seconds), all amounts in normal units rather than the blockchain's tiny units.
*In Unmask:* the same wallet written two ways (`0xAbC…` and `0xabc…`) must count as one wallet.

**"Follows the money hop by hop" (a trace)**
Start at the hacker's address, see where it sent money, then where *those* wallets sent money, and so on. Each step is a **hop**. Searching level by level like this is called **breadth-first search (BFS)**.
*In Unmask:* real cases start from the addresses named in a public post-mortem (the **seeds**) and follow the money a set number of hops (usually 2).

**"Every page"**
Etherscan returns a wallet's history in pages of 1,000 rows. Busy wallets have many pages.
*In Unmask:* we read every page, up to 10,000 rows. Reading only page one once made Harmony's swapped money look unspent.

**"Priced by real contract (fake tokens and spam dropped)"**
See address poisoning in part 1. Only genuine USDT, USDC, DAI, WETH and similar get a dollar value; unknown tokens are dropped as spam.

**"Whole wallets only → honest balances"**
A wallet's balance is only trustworthy if **all** its history was loaded; half a history gives a nonsense balance.
*In Unmask:* "held" counts only fully loaded wallets. Money reaching any other wallet is described as "last seen there".

**Entity extraction**
Pulling the useful bits out of text automatically. Unmask looks for:
- **wallet addresses** (`0x` + 40 characters);
- **transaction hashes**;
- **handles** (usernames like `@ghostfox`);
- **emails**;
- **IP addresses** (a computer's internet address, which can point to a location or internet provider);
- **ENS names** (human-readable wallet names like `alice.eth`).

**Aliases and writing style (stylometry)**
People use several usernames (`ghostfox`, `fox_ghost`). **Stylometry** compares *how* people write (favourite words, spelling, slang) to spot that two accounts are the same person.
*In Unmask:* merges one person's accounts into a single identity before scoring.

**MongoDB / MongoDB Atlas**
- **MongoDB** is a database that stores records as flexible documents.
- **Atlas** is MongoDB's cloud service, with a free plan (M0).

*In Unmask:* stores everything, so nothing is lost when the server restarts.

**Collections (the database's drawers)**

| Collection | Holds |
|---|---|
| **transfers** | every money movement |
| **posts** | public posts collected (OSINT) |
| **entities** | the identity markers extracted from posts |
| **links** | "this group of wallets ↔ this online identity", with a score |
| **alerts** | proposed actions waiting for a person |
| **evidence** | fingerprinted copies of each clue |
| **audit chain** | the record of every human decision |
| **case meta** | which case is loaded, its labels, its ETH price… |

---

## Part 4: column 3, the engine

**Engine / pipeline / `pipeline.run()`**
The main program. It takes the stored data and runs every analysis step in order: analytics → fusion → defense. It runs in **under one second** and is the same for simulated, real and live cases.

### A. Analytics: "the ledger as a matrix"
**Ledger** is another word for the blockchain's record book. Treating it as a **matrix** (a grid of numbers) lets us use maths on it. The problem statement asks for exactly this.

**Transaction graph**
A network picture: every wallet is a dot (a **node**) and every transfer is an arrow between dots (an **edge**).
*In Unmask:* the 3D picture in the case file, and the basis for clustering.

**Wallet clustering and Louvain**
- **Clustering** means grouping wallets that belong to the same owner.
- **Louvain** is a well-known method that finds groups in a network that are tightly connected inside and loosely connected to the outside, like friend groups in a school.

*In Unmask:* combined with gas funders and the seed addresses to find the attacker's wallets (purple in the graph). Other people's contracts the money passed through are split off.

**Shared gas-funder tracing**
See "gas" in part 1: whoever paid for a fresh wallet's first fees is likely its owner. Many fresh wallets funded by the same wallet → probably one person.

**Bridge matching (amount + time)**
The same amount leaving one chain and arriving on another within minutes → probably the same person's money.

**Wallet × time matrix**
A grid: rows are wallets, columns are hours, and each cell counts that wallet's transactions in that hour.
*In Unmask:* shown as "The ledger as a matrix" in the case file. It reveals wallets acting in lockstep (one bot or one person).

**Behaviour feature vectors**
A list of numbers describing a wallet's habits: how much it moves, how often, at what hours, how much fee it pays. Like a fingerprint made of numbers.
*In Unmask:* shown when you click a wallet.

**Bot score: KS test and Benford's law**
The problem statement mentions hackers using **bots** (automatic programs) that disguise transfers as normal market activity. The bot score (0 to 1) checks three things:
- **KS test (Kolmogorov–Smirnov):** compares a wallet's timing with natural, random-looking human timing. Bots are too regular or follow a pattern.
- **Round amounts:** people send round numbers (1 ETH, 0.5 ETH); bots send odd amounts (0.4837…).
- **Benford's law:** in natural numbers, the first digit is "1" about 30% of the time and "9" only about 5%. Amounts made up by a program often break this pattern.

**Time-zone inference**
People are active during their waking hours. Look at what hours of the day a wallet (or a person's posts) is active, and find the time zone where those hours are daytime.
*In Unmask:* if the wallets and a suspect's posts both look like UTC+9 (e.g. Korea or Japan), that's a clue they're the same person. It's the clock in the case file.

**Latency permutation test (time-delta latency analysis)**
This is the core idea of the problem statement.
- **Latency** is the delay between two events, here between a person posting and the hacker's wallets moving.
- If someone's posts keep appearing **just minutes before** the money moves, that's suspicious: maybe they're the one moving it.
- How do we know it isn't luck? We **shuffle** that person's post times randomly 500 times and count how often the shuffled times match the money moves as well as the real ones did. That's the **permutation test**.
- The answer is a **p-value**: the chance it happened by luck. In the simulated attack, 32 of 33 posts land minutes before a move, which by chance happens about 2 times in 1,000 (p ≈ 0.002), so it's very unlikely to be luck.

**Bytecode similarity**
See "bytecode" in part 1: code posted online that has the same commands as the attack contract.

### B. Fusion: "who is behind the wallets"
**Fusion** means combining many weak clues into one strong conclusion.

**Bayes' rule: prior, likelihood ratio, posterior**
A standard way to update a belief with evidence.
- **Prior:** how likely before any evidence. Unmask starts every person at **1%**.
- **Likelihood ratio (LR):** how much more likely the clue is *if* this person is the attacker than if they aren't. Examples:
  - posting an address only the attacker knew: ×30;
  - a username in an on-chain message: ×30;
  - posts timed before the moves: up to ×20;
  - matching code: ×10;
  - same time zone: ×3.
- **Posterior:** the updated probability after multiplying in all the clues. That's the % shown next to each suspect.

**Plain-English reason per clue**
Every clue comes with a sentence ("32 of 33 posts land minutes before the wallets move…"), so a person can check it. No black box.

**Confidence fades over time (decay)**
If neither the wallets nor the person do anything new for a week, the score halves (a **half-life** of one week). Old leads lose weight.

**Public-address filter**
Quoting a wallet address everyone already knows isn't evidence. A mention only counts if the address isn't a seed from a public report and only one person posted it.
*In Unmask:* this stops researchers who wrote about a hack being flagged as suspects (it happened on Euler before the fix).

**Evidence hashed**
A **hash** is a fingerprint of data: a short code calculated from it. Change even one letter and the fingerprint changes completely.
*In Unmask:* each clue is stored with its fingerprint, so anyone can prove later that the evidence wasn't changed.

**Tamper-evident audit chain**
A log of every human decision (confirm, reject, approve, reveal personal data, export). Each entry includes the fingerprint of the entry before it, like links in a chain. Edit or delete one in the middle and the chain no longer checks out.
*In Unmask:* the dossier says "The audit chain checks out: N decisions, none edited or removed".

**Suspected vs. confirmed**
Every link starts as **suspected**. Only a human can mark it **confirmed** (or rejected). The machine never accuses anyone on its own.

### C. Defense: "catch the cash-out"

**Where the money is now**
Splits the stolen money into: still **held** in the attacker's wallets, **inside a mixer**, **at an exchange**, or **given back** to the victim (Euler's hacker returned $189M).

**Who can freeze it**
For each holding: an exchange deposit (the exchange), USDT (Tether), USDC (Circle), or nobody (plain ETH in a private wallet).

**Next exit predicted (+ ETA)**
From where the money has already been cashed out, Unmask predicts which exchange it will go to next and roughly **when** (ETA, estimated time of arrival). It only predicts when cash-outs already seen cover at least 5% of the money; one small deposit isn't a pattern.

**Pre-attack warning**
A typical run-up to a hack: a wallet funded through a mixer deploys a contract and makes two or more **test calls** within a day. Spotting that can give a warning **before** the theft.

**Decoy / poisoning filter**
Hackers sometimes send dust to random wallets, or to look-alikes of known addresses, to confuse trackers. Those wallets are kept out of the attacker's group.

**Alert queue (human approves)**
Unmask proposes actions ("warn Binance", "ask Tether to freeze"). They wait in a queue, and **nothing is sent until a person clicks Approve**.

### Watch mode
**Watch mode / continuous monitoring**
The engine keeps running on its own while a case is live:
- **every block (12 s)** it checks the attacker's wallets for new transfers;
- if money moved, it **reruns** the engine and creates **one alert per new deposit** at an exchange or mixer;
- **every 10 minutes** it re-collects public posts.

**Source: Alchemy or the simulator.** On real cases new transfers come from the real blockchain (Alchemy). On a simulated case the fake hacker keeps moving money, so you can see alerts arrive live in a demo. It stops by itself after 30 minutes.

---

## Part 5: column 4, the API

**API (FastAPI)**
The engine's front desk: the website asks it questions over the internet and it answers. **FastAPI** is the Python library used to build it.

**Endpoint**
One specific "question" the API answers, like `GET /money-now` ("where is the money?") or `POST /alerts/…/approve`.
- **GET** = read something.
- **POST** = do something.

**JSON**
The text format the API answers in, readable by both people and programs: `{"total_usd": 191600000, …}`.

**HTTPS**
The secure, encrypted way web pages talk to servers (the padlock in the browser).

**SSE (server-sent events)**
A connection the server keeps open to push news as it happens. Watch mode can stream each new transfer this way.

**Safety gates**
- **Nothing is sent without a person's approval.**
- **Suspected until confirmed.**
- **Personal data masked:** emails and IPs found in posts are hidden (`a•••@•••.com`). Showing them needs a written reason, which goes into the audit chain.

---

## Part 6: column 5, the website

| Term | What it is | In Unmask |
|---|---|---|
| **React 19** | A popular library for building web pages out of reusable pieces ("components") | The whole website |
| **Vite** | A tool that bundles the code and runs a fast development server | `npm run dev` |
| **three.js** | A library for 3D graphics in the browser | The night sky on the home page and the 3D story |
| **GSAP + Lenis** | GSAP animates things (especially on scroll); Lenis makes scrolling smooth | The home page and story animations |
| **react-force-graph-3d** | Draws a network graph in 3D, where connected dots pull together | The money graph in the case file |

The pages:
- **Home:** what Unmask is, the real hacks.
- **How it works:** the 3-minute story.
- **Case file:** the working tool.
- **Dossier:** the printable report.

**Analyst**
The human investigator using Unmask. They confirm or reject suspects and approve each alert.

**Out to the people**
- **Discord / Telegram alert:** an approved alert is posted to the team's chat.
- **Freeze letter:** a ready-to-send request to an exchange, Tether or Circle, naming the address, the amount and the evidence, and asking them to freeze the funds.

---

## Part 7: the bottom band

| Term | What it is |
|---|---|
| **Deploy** | Putting the app on the internet so anyone can open it |
| **Vercel** | Free hosting for the website |
| **Render** | Free hosting for the Python engine (the API) |
| **MongoDB Atlas M0** | The free cloud database |
| **Free API tiers** | Etherscan, Alchemy and GitHub at no cost, within their limits |
| **Automated tests (197)** | Small programs that check the code still gives the right answers after every change |
| **Matches the public record** | Unmask's totals on four real hacks agree with what investigators reported, e.g. Harmony: 85,700 ETH into Tornado Cash, the same figure Elliptic (a blockchain analytics company) published |

---

## Part 8: one hack through the whole diagram

1. **2:14 AM, the exploit.** A hacker abuses a bug in a DeFi protocol's smart contract and takes $42M. *(Column 1: this lands on the blockchain.)*
2. **Splitting.** A bot splits the money over hundreds of fresh wallets, each funded with a little ETH for gas, then sends pieces through a mixer and a bridge.
3. **Ingest.** Unmask traces the money hop by hop from the first address and stores every transfer. It collects posts from news, GitHub and Telegram and extracts the handles and addresses in them. *(Column 2.)*
4. **Analytics.**
   - Clustering plus shared gas funders group the fresh wallets into one attacker.
   - Bridge matching links the two chains.
   - The bot score flags machine-like timing.
   - The matrix shows the wallets moving in lockstep.
5. **Fusion.** User `ghostfox` scores high:
   - posted a wallet address only the attacker knew (×30);
   - an on-chain message names them (×30);
   - their posts land minutes before the moves, p ≈ 0.002 (×20);
   - GitHub code matches the attack contract (×10);
   - same time zone, UTC+9 (×3).

   The result is a high probability, with every reason listed, still marked **suspected**.
6. **Defense.** $21M is already at exchange A, and some USDT can be frozen by Tether. Exchange B is predicted next, with an estimated arrival time. Freeze letters are drafted.
7. **Watch mode.** Every 12 seconds new moves appear: "Just now: 28 ETH moved to exchange A". New alerts land in the queue.
8. **The analyst** confirms the suspect and approves the alerts. Discord gets the message, the freeze letter goes to the exchange, and every click is recorded in the tamper-evident audit chain.
9. **Before cash-out** the exchange freezes the account. Its KYC records point the police to a real person. That's the bridge between the investigators and the analysts that the problem statement asked for.
