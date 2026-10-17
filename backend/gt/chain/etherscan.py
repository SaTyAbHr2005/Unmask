"""Etherscan API V2 (one free key, many chains) with disk cache + backoff, and the replay loader."""
import hashlib
import json
import logging
import time
from pathlib import Path

import httpx

from gt.chain.labels import load_labels
from gt.chain.normalize import norm_addr, to_utc
from gt.config import DATA_DIR, env
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


def _account(action: str, address: str, chainid: int) -> list[dict]:
    return get({"module": "account", "action": action, "address": address, "startblock": 0,
                "endblock": 99999999, "page": 1, "offset": 1000, "sort": "asc"}, chainid)


def txlist(address: str, chainid: int = 1) -> list[Transfer]:
    out = []
    for r in _account("txlist", address, chainid):
        if r.get("isError") == "1":
            continue
        deploy = not r.get("to") and r.get("contractAddress")
        out.append(Transfer(norm_addr(r["hash"]), _chain(chainid), to_utc(r["timeStamp"]), norm_addr(r["from"]),
                            norm_addr(r["contractAddress"] if deploy else r["to"]), "ETH", int(r["value"]) / 1e18,
                            int(r.get("gasPrice") or 0) / 1e9, int(r.get("nonce") or -1), r.get("input") or "0x",
                            "deploy" if deploy else "transfer"))
    return out


def tokentx(address: str, chainid: int = 1) -> list[Transfer]:
    return [Transfer(f"{norm_addr(r['hash'])}:{r.get('logIndex', '0')}", _chain(chainid), to_utc(r["timeStamp"]),
                     norm_addr(r["from"]), norm_addr(r["to"]), r.get("tokenSymbol") or "TOKEN",
                     int(r["value"]) / 10 ** int(r.get("tokenDecimal") or 18),
                     int(r.get("gasPrice") or 0) / 1e9, int(r.get("nonce") or -1))
            for r in _account("tokentx", address, chainid)]


def get_code(address: str, chainid: int = 1) -> str:
    code = get({"module": "proxy", "action": "eth_getCode", "address": address, "tag": "latest"}, chainid)
    return code if isinstance(code, str) else "0x"


def load_replay(path: str, max_transfers: int = 3000) -> tuple[list[Transfer], dict[str, str]]:
    """BFS forward along the money from the seed addresses; labeled hubs (exchanges, mixers…) are not expanded."""
    cfg = json.loads(Path(path).read_text())
    labels = load_labels()
    seen: dict[str, Transfer] = {}
    frontier = [norm_addr(a) for a in cfg["seed_addresses"]]
    expanded: set[str] = set()
    for _ in range(cfg.get("hops", 2) + 1):
        nxt = []
        for addr in frontier:
            if addr in expanded or addr in labels:
                continue
            expanded.add(addr)
            for chainid in cfg.get("chainids", [1]):
                for t in txlist(addr, chainid) + tokentx(addr, chainid):
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
