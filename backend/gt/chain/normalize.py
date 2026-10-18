"""Ingestion boundary: everything downstream sees lowercase addresses and int UTC seconds."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from gt.schema import Transfer


def norm_addr(a: str | None) -> str:
    return (a or "").strip().lower()


# The real contracts of every token Unmask prices (Ethereum, Arbitrum, Polygon). Anyone can deploy a token called
# "DAI": address-poisoning scams emitted fake 10.8M "DAI" transfers from the Euler hacker to look-alike addresses,
# and pricing by symbol counted them as $75M "held".
REAL_TOKENS = {
    "0xdac17f958d2ee523a2206206994597c13d831ec7": "USDT", "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": "USDC",
    "0x6b175474e89094c44da98b954eedeac495271d0f": "DAI", "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": "WETH",
    "0xae7ab96520de3a18e5e111b5eaab095312d7fe84": "stETH", "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0": "wstETH",
    "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9": "USDT", "0xaf88d065e77c8cc2239327c5edb3a432268e5831": "USDC",
    "0xff970a61a04b1ca14834a43f5de4533ebddb5cc8": "USDC", "0xda10009cbd5d07dd0cecc66161fc93d7c9000da1": "DAI",
    "0x82af49447d8a07e3bd95bd0d56f35241523fbab1": "WETH", "0x5979d7b546e38e414f7e9822514be443a4800529": "wstETH",
    "0xc2132d05d31c914a87c6611c10748aeb04b58e8f": "USDT", "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359": "USDC",
    "0x2791bca1f2de4661ed88a30c99a7a9449aa84174": "USDC", "0x8f3cf7ad23cd3cadbd9735aff958023239c6a063": "DAI",
    "0x7ceb23fd6bc0add59e62ac25578270cff1b9f619": "WETH", "0x03b54a6e9a984069379fae1a4fc4dbae93b3bccd": "wstETH",
}


def token_asset(symbol: str | None, contract: str | None) -> str:
    """The asset name for a token transfer: the real symbol for a known contract; any other token keeps its own
    symbol unless it pretends to be a priced one, which becomes 'fake:<symbol>' (unpriced, so never counted)."""
    contract = norm_addr(contract)
    if contract in REAL_TOKENS:
        return REAL_TOKENS[contract]
    symbol = symbol or "TOKEN"
    return f"fake:{symbol}" if symbol in set(REAL_TOKENS.values()) else symbol


def to_utc(ts: int | str | None) -> int | None:
    if isinstance(ts, (int, float)):
        return int(ts)
    s = (ts or "").strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(s)
        except (TypeError, ValueError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def decode_message(input_data: str) -> str | None:
    """Readable text hidden in tx input data (hackers negotiate this way), else None."""
    try:
        text = bytes.fromhex(input_data.removeprefix("0x")).decode("utf-8").strip("\x00 ")
    except (ValueError, UnicodeDecodeError):
        return None
    if len(text) < 8 or sum(c.isprintable() for c in text) / len(text) < 0.7:
        return None
    return text


_ROLES = [("to", "mixer", "mixer_in"), ("from", "mixer", "mixer_out"),
          ("to", "bridge", "bridge_out"), ("from", "bridge", "bridge_in"),
          ("to", "dex", "swap"), ("from", "dex", "swap")]


def classify(t: Transfer, labels: dict[str, str]) -> str:
    if t.kind not in ("transfer", ""):
        return t.kind
    for side, label, kind in _ROLES:
        if labels.get(t.to_addr if side == "to" else t.from_addr) == label:
            return kind
    return t.kind
