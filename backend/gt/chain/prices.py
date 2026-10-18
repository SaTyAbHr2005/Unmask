"""Historical ETH price for a day, from Binance's free public market data (no key). CoinGecko's free API only
reaches back 365 days, which misses most hacks worth replaying."""
import logging
from datetime import date, datetime, timezone

import httpx

URL = "https://data-api.binance.vision/api/v3/klines"
log = logging.getLogger(__name__)


def eth_usd_on(day: date, http=None) -> float | None:
    """That day's closing ETH/USDT price, or None if it can't be fetched (callers fall back to the demo price)."""
    start = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp() * 1000)
    try:
        r = (http or httpx).get(URL, params={"symbol": "ETHUSDT", "interval": "1d", "startTime": start, "limit": 1},
                                timeout=15)
        return float(r.json()[0][4]) if r.status_code == 200 and r.json() else None
    except (httpx.HTTPError, ValueError, IndexError, KeyError, TypeError) as e:
        log.warning("ETH price for %s unavailable: %r", day, e)
        return None
