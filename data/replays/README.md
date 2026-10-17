# Replays: real past hacks

Each `*.json` file here is one real incident that `POST /api/replay/<name>` loads through the Etherscan V2 API.

```json
{
  "name": "short-name",
  "source": "URL of the public post-mortem the addresses came from",
  "seed_addresses": ["0x… attacker address copied from the post-mortem"],
  "chainids": [1],
  "hops": 2
}
```

Rules:
- Copy attacker addresses **only from a public post-mortem** (rekt.news, the protocol's own incident report), and open each one on etherscan.io to confirm it before adding it.
- Replays show wallet clustering and cash-out exits only. Never attach a real person's name to a real wallet.
- `hops` is how far to follow the money forward from the seeds. Exchanges, mixers and bridges listed in `data/labels/*.csv` are never expanded.
- Needs `ETHERSCAN_API_KEY` in `backend/.env`. Responses are cached in `data/cache/`, so a second run makes no API calls.

Check a replay (run from `backend/`):

```bash
py -3.11 -c "from gt.chain.etherscan import load_replay; print(len(load_replay('../data/replays/<name>.json')[0]))"
```

Expect more than 100 transfers.
