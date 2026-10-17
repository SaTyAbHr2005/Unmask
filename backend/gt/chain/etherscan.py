"""Etherscan API V2 (one free key, many chains) with disk cache + backoff, and the replay loader."""
import hashlib
import json
import logging
import time
from pathlib import Path

import httpx

from gt.chain.labels import load_labels
from gt.chain.normalize import norm_addr, to_utc
from gt.config import DATA_DIR, env, usd
from gt.schema import Transfer

URL = "https://api.etherscan.io/v2/api"
CACHE_DIR = DATA_DIR / "cache"
CHAINS = {1: "eth", 10: "op", 56: "bsc", 137: "polygon", 8453: "base", 42161: "arb"}
MIN_GAP_S = 0.25          # ≤ 4 req/s; free tier allows 5
_last_call = [0.0]
_client: list[httpx.Client] = []
log = logging.getLogger(__name__)


def _retryable(status: int, body: dict) -> bool:
    if status == 429 or status >= 500:
        return True
    return body.get("status") == "0" and "rate limit" in str(body.get("result", "")).lower()


def get(params: dict, chainid: int = 1, *, http=None, sleep=time.sleep):
    """Return the `result` payload (list for account module, hex string for proxy), [] on failure."""
    key = hashlib.sha256(json.dumps({**params, "chainid": chainid}, sort_keys=True).encode()).hexdigest()
    path = Path(CACHE_DIR) / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())
    if http is None:
        _client or _client.append(httpx.Client())
        http = _client[0]
    for wait in (1, 2, 4, 8, None):
        gap = MIN_GAP_S - (time.monotonic() - _last_call[0])
        if gap > 0:
            sleep(gap)
        _last_call[0] = time.monotonic()
        try:
            r = http.get(URL, params={**params, "chainid": chainid, "apikey": env("ETHERSCAN_API_KEY") or ""}, timeout=20)
            body = r.json() if r.status_code == 200 else {}
        except (httpx.HTTPError, ValueError) as e:
            r, body = None, {"status": "0", "result": f"rate limit ({e!r})"}  # treat as retryable
        status = r.status_code if r is not None else 599
        if not _retryable(status, body):
            result = body.get("result", [])
            if body.get("status") == "0" or not isinstance(result, (list, str)):
                if "no transactions" not in str(body.get("message", "")).lower():
                    log.warning("etherscan error %s: %s", params, body.get("result"))
                result = []
            Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result))
            return result
        if wait is None:
            break
        sleep(wait)
    log.warning("etherscan gave up after retries: %s", params)
    return []


def _chain(chainid: int) -> str:
    return CHAINS.get(chainid, str(chainid))


ALL_BLOCKS = (0, 99999999)


def _account(action: str, address: str, chainid: int, blocks: tuple[int, int]) -> list[dict]:
    return get({"module": "account", "action": action, "address": address, "startblock": blocks[0],
                "endblock": blocks[1], "page": 1, "offset": 1000, "sort": "asc"}, chainid)


def block_at(ts: int, chainid: int = 1) -> int | None:
    b = get({"module": "block", "action": "getblocknobytime", "timestamp": ts, "closest": "before"}, chainid)
    return int(b) if isinstance(b, str) and b.isdigit() else None


def txlist(address: str, chainid: int = 1, blocks: tuple[int, int] = ALL_BLOCKS) -> list[Transfer]:
    out = []
    for r in _account("txlist", address, chainid, blocks):
        if r.get("isError") == "1":
            continue
        deploy = not r.get("to") and r.get("contractAddress")
        out.append(Transfer(norm_addr(r["hash"]), _chain(chainid), to_utc(r["timeStamp"]), norm_addr(r["from"]),
                            norm_addr(r["contractAddress"] if deploy else r["to"]), "ETH", int(r["value"]) / 1e18,
                            int(r.get("gasPrice") or 0) / 1e9, int(r.get("nonce") or -1), r.get("input") or "0x",
                            "deploy" if deploy else "transfer"))
    return out


def tokentx(address: str, chainid: int = 1, blocks: tuple[int, int] = ALL_BLOCKS) -> list[Transfer]:
    return [Transfer(f"{norm_addr(r['hash'])}:{r.get('logIndex', '0')}", _chain(chainid), to_utc(r["timeStamp"]),
                     norm_addr(r["from"]), norm_addr(r["to"]), r.get("tokenSymbol") or "TOKEN",
                     int(r["value"]) / 10 ** int(r.get("tokenDecimal") or 18),
                     int(r.get("gasPrice") or 0) / 1e9, int(r.get("nonce") or -1))
            for r in _account("tokentx", address, chainid, blocks)]


def get_code(address: str, chainid: int = 1) -> str:
    code = get({"module": "proxy", "action": "eth_getCode", "address": address, "tag": "latest"}, chainid)
    return code if isinstance(code, str) else "0x"


def load_replay(path: str, max_transfers: int = 3000) -> tuple[list[Transfer], dict[str, str]]:
    """BFS forward along the money from the seed addresses; labeled hubs (exchanges, mixers…) are not expanded.
    `window: [start, end]` (ISO dates) limits every lookup to the incident; without it busy wallets drag in years
    of unrelated history. Tokens with no known price are dropped: on hacker wallets they are spam airdrops."""
    cfg = json.loads(Path(path).read_text())
    labels = load_labels()
    chainids = cfg.get("chainids", [1])
    window = [to_utc(d) for d in cfg.get("window", [])]
    blocks = {c: (block_at(window[0], c) or 0, block_at(window[1], c) or ALL_BLOCKS[1]) if window else ALL_BLOCKS
              for c in chainids}
    seen: dict[str, Transfer] = {}
    frontier = [norm_addr(a) for a in cfg["seed_addresses"]]
    expanded: set[str] = set()
    for _ in range(cfg.get("hops", 2) + 1):
        nxt = []
        for addr in frontier:
            if len(seen) >= max_transfers:   # full: stop paying for API calls whose rows would be dropped
                break
            if addr in expanded or addr in labels:
                continue
            expanded.add(addr)
            for chainid in chainids:
                for t in txlist(addr, chainid, blocks[chainid]) + tokentx(addr, chainid, blocks[chainid]):
                    if usd(t.asset, t.amount) is None:
                        continue
                    if len(seen) >= max_transfers:
                        break
                    seen.setdefault(t.tx_hash, t)
                    if t.from_addr == addr:
                        nxt.append(t.to_addr)
        frontier = nxt
    transfers = list(seen.values())
    ids = {v: k for k, v in CHAINS.items()}
    codes = {t.to_addr: get_code(t.to_addr, ids.get(t.chain, 1)) for t in transfers if t.kind == "deploy"}
    return transfers, codes
