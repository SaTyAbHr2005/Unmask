"""Etherscan API V2 (one free key, many chains) with disk cache + backoff, and the replay loader."""
import hashlib
import json
import logging
import time
from pathlib import Path

import httpx

from gt.chain.labels import load_labels
from gt.chain.normalize import norm_addr, to_utc, token_asset
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
            empty = "no transactions" in str(body.get("message", "")).lower()
            if (body.get("status") == "0" and not empty) or not isinstance(result, (list, str)):
                # an error (bad key, chain not on the free plan…) is not an answer: never cache it as "no transactions"
                log.warning("etherscan error %s: %s", params, body.get("result"))
                return []
            if empty:
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


PAGE = 1000
MAX_PAGES = 10   # Etherscan serves at most page × offset = 10,000 rows per query


def _account(action: str, address: str, chainid: int, blocks: tuple[int, int]) -> list[dict]:
    """Every page, not just the first: Harmony's swap wallet had >1,000 token moves, and stopping at page 1
    left 38M USDC looking 'held' after it had been swapped away."""
    rows: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        batch = get({"module": "account", "action": action, "address": address, "startblock": blocks[0],
                     "endblock": blocks[1], "page": page, "offset": PAGE, "sort": "asc"}, chainid)
        rows += batch
        if len(batch) < PAGE:
            return rows
    log.warning("%s %s: more than %d rows in the window, history is cut off", action, address, PAGE * MAX_PAGES)
    return rows


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
        out += _weth_leg(out[-1], chainid)
    return out


WETH9 = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"   # mainnet WETH: wrap/unwrap emit Deposit/Withdrawal, not Transfer
NEVER_EXPAND = {WETH9, "0x" + "0" * 40}                # every swap and mint touches these: their history is the whole chain


def internal(address: str, chainid: int = 1, blocks: tuple[int, int] = ALL_BLOCKS) -> list[Transfer]:
    """ETH moved by contracts: swap payouts, WETH unwraps, refunds. Without these Harmony's 85,867 ETH looked
    spent (the hacker's ETH went out to Tornado but never came in) and Beanstalk's profit looked stuck as WETH.
    Mainnet WETH wraps/unwraps also get the WETH leg added, so a wallet's WETH balance is right too."""
    out = []
    for r in _account("txlistinternal", address, chainid, blocks):
        create = r.get("type", "").startswith("create")
        if r.get("isError") == "1" or not (int(r["value"]) or create):
            continue
        rid = f"{norm_addr(r['hash'])}:i{r.get('traceId') or _token_id(r).split(':')[1]}"
        frm, to, eth = norm_addr(r["from"]), norm_addr(r["contractAddress"] if create else r["to"]), int(r["value"]) / 1e18
        out.append(Transfer(rid, _chain(chainid), to_utc(r["timeStamp"]), frm, to, "ETH", eth,
                            kind="deploy" if create else "transfer"))
        out += _weth_leg(out[-1], chainid)
    return out


def _weth_leg(t: Transfer, chainid: int) -> list[Transfer]:
    """ETH paid into WETH = WETH minted to the payer; ETH paid out by WETH = WETH burned by the receiver."""
    if chainid != 1 or WETH9 not in (t.from_addr, t.to_addr) or t.kind == "deploy":
        return []
    holder = t.to_addr if t.from_addr == WETH9 else t.from_addr
    frm, to = (holder, WETH9) if t.from_addr == WETH9 else (WETH9, holder)
    return [Transfer(f"{t.tx_hash}:weth", t.chain, t.ts, frm, to, "WETH", t.amount)]


def _token_id(r: dict) -> str:
    """One id per token transfer, the same whichever wallet's history it was read from. Etherscan V2 dropped
    logIndex, and 'hash:0' for every row merged a swap's USDC-out into its WETH-in (Harmony: 111 rows became 32).
    ponytail: two identical transfers (same token, sender, receiver, amount) inside one tx still merge."""
    if "logIndex" in r:
        return f"{norm_addr(r['hash'])}:{r['logIndex']}"
    key = "|".join(str(r.get(k, "")).lower() for k in ("contractAddress", "from", "to", "value"))
    return f"{norm_addr(r['hash'])}:{hashlib.sha1(key.encode()).hexdigest()[:12]}"


def tokentx(address: str, chainid: int = 1, blocks: tuple[int, int] = ALL_BLOCKS) -> list[Transfer]:
    return [Transfer(_token_id(r), _chain(chainid), to_utc(r["timeStamp"]),
                     norm_addr(r["from"]), norm_addr(r["to"]), token_asset(r.get("tokenSymbol"), r.get("contractAddress")),
                     int(r["value"]) / 10 ** int(r.get("tokenDecimal") or 18),
                     int(r.get("gasPrice") or 0) / 1e9, int(r.get("nonce") or -1))
            for r in _account("tokentx", address, chainid, blocks)]


def get_code(address: str, chainid: int = 1) -> str:
    code = get({"module": "proxy", "action": "eth_getCode", "address": address, "tag": "latest"}, chainid)
    return code if isinstance(code, str) else "0x"


def load_replay(path: str, max_transfers: int = 3000) -> tuple[list[Transfer], dict[str, str], set[str]]:
    return trace(json.loads(Path(path).read_text()), max_transfers)


def trace(cfg: dict, max_transfers: int = 3000) -> tuple[list[Transfer], dict[str, str], set[str]]:
    """BFS forward along the money from cfg['seed_addresses']; labeled hubs (exchanges, mixers…) are not expanded.
    `window: [start, end]` (ISO dates) limits every lookup to the incident; without it busy wallets drag in years
    of unrelated history. Tokens with no known price are dropped: on hacker wallets they are spam airdrops.

    Returns (transfers, bytecodes, complete): `complete` = wallets whose whole history in the window was loaded.
    Only their balances are real; money that reached any other wallet is 'last seen there'. The seeds are always
    loaded in full; past them a wallet is loaded whole or not at all. (Cutting wallets halfway left Beanstalk's
    attack contract with its $350M flash loan in and no repayment out, and Harmony's swapped USDC looking unspent.)"""
    labels = {**load_labels(), **{norm_addr(a): "victim" for a in cfg.get("victims", [])}}   # never follow into the victim
    chainids = cfg.get("chainids", [1])
    window = [to_utc(d) for d in cfg.get("window", [])]
    blocks = {c: (block_at(window[0], c) or 0, block_at(window[1], c) or ALL_BLOCKS[1]) if window else ALL_BLOCKS
              for c in chainids}
    seeds = [norm_addr(a) for a in cfg["seed_addresses"]]
    seen: dict[str, Transfer] = {}
    complete: set[str] = set()
    frontier, expanded = list(seeds), set()
    for _ in range(cfg.get("hops", 2) + 1):
        nxt = []
        for addr in frontier:
            if len(seen) >= max_transfers and addr not in seeds:   # full: stop paying for rows we'd drop
                break
            if addr in expanded or addr in labels or addr in NEVER_EXPAND:
                continue
            expanded.add(addr)
            rows, cut = [], False
            for chainid in chainids:
                got = [f(addr, chainid, blocks[chainid]) for f in (txlist, internal, tokentx)]
                cut |= max(map(len, got)) >= PAGE * MAX_PAGES               # Etherscan's own ceiling was hit
                rows += [t for g in got for t in g if usd(t.asset, t.amount) is not None]
            if addr not in seeds and len(seen) + sum(t.tx_hash not in seen for t in rows) > max_transfers:
                continue                                                  # doesn't fit whole: leave it out
            for t in rows:
                seen.setdefault(t.tx_hash, t)
                # follow money and the attacker's own deployments, not 0-value calls (approve() to the USDC
                # contract pulled in 20,000 strangers' rows)
                if t.from_addr == addr and (t.amount > 0 or t.kind == "deploy"):
                    nxt.append(t.to_addr)
            if not cut:
                complete.add(addr)
        frontier = nxt
    transfers = list(seen.values())
    ids = {v: k for k, v in CHAINS.items()}
    codes = {t.to_addr: get_code(t.to_addr, ids.get(t.chain, 1)) for t in transfers if t.kind == "deploy"}
    return transfers, codes, complete
