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
  "hops": 2
}
```

| Field | Meaning |
|---|---|
| `seed_addresses` | Where the trace starts: the attacker addresses named in the post-mortem |
| `chainids` | Chains to read (1 = Ethereum, 42161 = Arbitrum, …) |
| `window` | Only transactions between these dates are fetched. **Always set it.** Without it, busy wallets drag in years of unrelated history (Euler without a window: 2021 to 2026). |
| `hops` | How far to follow the money forward from the seeds |

## Rules
- Copy attacker addresses **only from a public post-mortem** (rekt.news, the protocol's own incident report), and open each one on etherscan.io to confirm it before adding it.
- Leave out any other address the post-mortem shows, such as the site's own donation address.
- Replays show wallet clustering, cash-out exits and freezability. Never attach a real person's name to a real wallet.
- Needs `ETHERSCAN_API_KEY` in `backend/.env`. Every response is cached in `data/cache/`, so the second load of a case makes no API calls.

## What the loader does to keep real data honest
- **Exchanges, mixers and bridges** in `data/labels/*.csv` are never followed further.
- **Tokens with no known price are dropped.** On hacker wallets these are spam airdrops (Euler: "CASH", "RHWASRIGHT").
- **Contracts the attacker didn't deploy** (multisigs, DEX pools, lending markets) are taken out of the attacker's cluster and shown as "Someone else's contract". On Euler this stopped the victim's own recovery Safe being flagged as the attacker's.
- The trace stops at 3,000 transfers and doesn't spend API calls past that limit.

## Limits
- Prices are fixed: ETH at $3,000 and stablecoins at $1. Euler happened when ETH was about $1,600, so dollar amounts are overstated.
- The last wallets in the trace weren't followed further, so their "held" balance means "last seen here".
- With no victim label, the total is "traced through the attacker's wallets", not "stolen", and there's no theft time or warning lead time.
- A 2023 case has no matching posts, so there are no suspects. That's correct: Unmask names nobody without evidence.

## Check a replay (run from `backend/`)

```bash
py -3.11 -c "from gt.chain.etherscan import load_replay; print(len(load_replay('../data/replays/euler-2023.json')[0]))"
```
