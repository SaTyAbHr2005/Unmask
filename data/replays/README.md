# Replays: real past hacks

Each `*.json` file here is one real incident. The case file's **Real hack** picker lists them (`GET /api/replays`), and
**Load real hack** loads one (`POST /api/replay/<name>`) through the Etherscan V2 API.

```json
{
  "name": "Euler Finance exploit (13 March 2023, ~$197M)",
  "source": "https://rekt.news/euler-rekt",
  "seed_addresses": ["0x… attacker address copied from the post-mortem"],
  "chainids": [1],
  "window": ["2023-03-12", "2023-04-10"],
  "eth_usd": 1673,
  "hops": 2
}
```

| Field | Meaning |
|---|---|
| `seed_addresses` | Where the trace starts: the attacker addresses named in the post-mortem |
| `chainids` | Chains to read (1 = Ethereum, 42161 = Arbitrum, …) |
| `window` | Only transactions between these dates are fetched. **Always set it.** Without it, busy wallets drag in years of unrelated history (Euler without a window: 2021 to 2026). |
| `eth_usd` | ETH's closing price on the hack date (from Binance's public daily prices). Dollar amounts use it, so a 2022 hack isn't valued at today's price. Without it, the window's start date is looked up automatically. |
| `hops` | How far to follow the money forward from the seeds |
| `victims` (optional) | The victim's own addresses: the drained contracts, or where returned money was sent. Money from them is measured as stolen (with a theft time and time to first cash-out), and money sent back to them is shown as "given back to the victim". They are never followed. |

Chains on Etherscan's free plan: **Ethereum (1), Arbitrum (42161), Polygon (137)**. Optimism, Base and BNB Chain need a paid key.

Any address can also be traced without a file: **Trace any address** in the case file (`POST /api/investigate`) takes up to 5 addresses, a date range of at most 120 days, a chain and 1–3 hops.

## Rules
- Copy attacker addresses **only from a public post-mortem** (rekt.news, the protocol's own incident report), and open each one on etherscan.io to confirm it before adding it.
- Leave out any other address the post-mortem shows, such as the site's own donation address.
- Replays show wallet clustering, cash-out exits and freezability. Never attach a real person's name to a real wallet.
- Needs `ETHERSCAN_API_KEY` in `backend/.env`. Every response is cached in `data/cache/`, so the second load of a case makes no API calls.

## What the loader does to keep real data honest
- **Exchanges, mixers and bridges** in `data/labels/*.csv` are never followed further.
- **Tokens with no known price are dropped.** On hacker wallets these are spam airdrops (Euler: "CASH", "RHWASRIGHT").
- **Contracts the attacker didn't deploy** (multisigs, DEX pools, lending markets) are taken out of the attacker's cluster and shown as "Someone else's contract". On Euler this stopped the victim's own recovery Safe being flagged as the attacker's.
- **Every page of a wallet's history is read** (up to Etherscan's 10,000 rows), not just the first 1,000. Stopping at page 1 left Harmony's 38M USDC looking unspent after it had been swapped to ETH in hundreds of pieces.
- **Only transfers that carry value are followed**, plus the attacker's own contract deployments. Following a zero-value `approve()` to the USDC token contract pulled in 20,000 strangers' transfers.
- **Internal ETH transfers are read too** (`txlistinternal`): swap payouts, refunds and WETH unwraps. Without them the hacker's ETH went out but never came in. Harmony's 85,700 ETH Tornado deposits looked like spending money the hacker didn't have, and Beanstalk's profit looked stuck as $74M of WETH.
- **WETH wraps and unwraps** on Ethereum emit no token transfer, so Unmask adds the WETH side itself (10 ETH paid out by WETH = 10 WETH given back to it).
- **Tokens are priced by contract address, not by name.** Anyone can deploy a token called "DAI". Address-poisoning scammers made fake 10.8M "DAI" transfers appear from the Euler hacker to look-alike addresses, and pricing by name counted them as $270M "held". A token that copies a priced name from another contract becomes `fake:DAI` and is never counted.
- **A wallet is loaded whole or not at all.** Only wallets whose whole history was read count as "held"; money that reached any other wallet was only "last seen" there.
- Hubs every swap touches (the WETH contract, the zero address) are never followed.
- The trace stops at 3,000 transfers and doesn't spend API calls past that limit.

## The four cases, checked against the public record

| Case | What Unmask finds | Public record |
|---|---|---|
| **Euler (Mar 2023)** | $191.6M traced: **$189.4M given back to Euler's multisig**, $1.8M into Tornado, $0.16M at Binance | ~$197M taken; nearly all returned by early April |
| **KyberSwap (Nov 2023)** | $33.5M traced on 3 chains, $10.3M into Tornado; Circle and Tether freeze letters | ~$48M reported |
| **Harmony bridge (Jun 2022)** | $72.3M stolen from the bridge, **$98.1M into Tornado** in 857 deposits of 100 ETH, 27 Jun – 2 Jul | Elliptic: 85,700 ETH (~$98M) laundered through Tornado by 2 July |
| **Beanstalk (Apr 2022)** | $74.4M traced, $74.3M of it into Tornado; a Tether freeze letter | ~$76M profit |

Harmony's stolen total is below the ~$100M reported because WBTC and other tokens Unmask can't price aren't counted. Its mixer total is higher than the stolen total because those tokens were swapped to ETH before they went into Tornado.

## Limits
- Only ETH (and WETH/stETH), USDT, USDC and DAI have prices. Stolen tokens Unmask can't price (WBTC, AAVE…) aren't counted as stolen, but once the attacker swaps them to ETH they show up as held, so "held" can exceed "stolen".
- With no theft seen, the total is "traced through the attacker's wallets": still held, plus sent to mixers and bridges, plus given back. There's no theft time or warning lead time.
- Wallets past the last hop, or too busy to load whole, aren't counted as held: money that reached them was only "last seen" there.
- A 2023 case has no matching posts, so there are no suspects. That's correct: Unmask names nobody without evidence.

## Check a replay (run from `backend/`)

```bash
py -3.11 -c "from gt.chain.etherscan import load_replay; print(len(load_replay('../data/replays/euler-2023.json')[0]))"
```
