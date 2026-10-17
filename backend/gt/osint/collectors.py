"""Collect public text: RSS threat feeds, GitHub commits/code, public Telegram channels. Every collector
returns what it managed to get and never raises on network/API trouble."""
import logging

import feedparser
import httpx

from gt.config import DATA_DIR, env
from gt.osint.extract import make_post
from gt.schema import OsintPost

GITHUB_API = "https://api.github.com"
USER_AGENT = "Mozilla/5.0 (Unmask OSINT reader)"
CODE_HITS_PER_QUERY = 10   # each code hit costs one extra call to read the repo's push date
log = logging.getLogger(__name__)


def collect_rss(urls: list[str], parse=feedparser.parse) -> list[OsintPost]:
    posts = []
    for url in urls:
        try:
            d = parse(url, agent=USER_AGENT)
        except Exception as e:  # feedparser surfaces many parser/network error types
            log.warning("rss %s failed: %r", url, e)
            continue
        author = d.get("feed", {}).get("title") or url
        for e in d.get("entries", []):
            text = f"{e.get('title', '')}\n{e.get('summary', '')}".strip()
            p = make_post("rss", author, e.get("published") or e.get("updated"), text, e.get("link", ""))
            if p:
                posts.append(p)
    return posts


class _Stop(Exception):
    """GitHub said no (rate limit / auth) — stop querying, keep what we have."""


def _get(http, url: str, headers: dict, params: dict | None = None) -> dict:
    r = http.get(url, params=params, headers=headers, timeout=20)
    if r.status_code != 200:
        raise _Stop(f"{url} -> HTTP {r.status_code}")
    return r.json()


def collect_github(queries: list[str], http=None) -> list[OsintPost]:
    http = http or httpx.Client(headers={"User-Agent": USER_AGENT})
    token = env("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json", **({"Authorization": f"Bearer {token}"} if token else {})}
    posts: dict[str, OsintPost] = {}
    pushed: dict[str, str | None] = {}

    def add(p: OsintPost | None):
        if p:
            posts.setdefault(p.post_id, p)
    try:
        for q in queries:
            for it in _get(http, f"{GITHUB_API}/search/commits", headers, {"q": q, "per_page": 30}).get("items", []):
                login = (it.get("author") or {}).get("login") or it["repository"]["owner"]["login"]
                add(make_post("github", login.lower(), it["commit"]["author"]["date"],
                              it["commit"]["message"], it.get("html_url", "")))
            if not token:   # code search requires auth
                continue
            code = _get(http, f"{GITHUB_API}/search/code",
                        {**headers, "Accept": "application/vnd.github.text-match+json"}, {"q": q, "per_page": 30})
            for it in code.get("items", [])[:CODE_HITS_PER_QUERY]:
                repo = it["repository"]
                if repo["url"] not in pushed:
                    pushed[repo["url"]] = _get(http, repo["url"], headers).get("pushed_at")
                text = "\n".join(m.get("fragment", "") for m in it.get("text_matches", []))
                add(make_post("github", repo["owner"]["login"].lower(), pushed[repo["url"]], text, it.get("html_url", "")))
    except (_Stop, httpx.HTTPError, KeyError, ValueError, TypeError) as e:
        log.warning("github collection stopped: %r", e)
    return list(posts.values())


async def collect_telegram(channels: list[str], limit: int = 200) -> list[OsintPost]:
    """Public channels only. The first run asks for a phone login in the terminal; the session is kept in data/."""
    api_id, api_hash = env("TELEGRAM_API_ID"), env("TELEGRAM_API_HASH")
    if not (api_id and api_hash and channels):
        return []
    try:
        from telethon import TelegramClient   # optional dependency: py -3.11 -m pip install telethon
    except ImportError:
        log.warning("telethon not installed; skipping Telegram")
        return []
    posts = []
    async with TelegramClient(str(DATA_DIR / "telegram"), int(api_id), api_hash) as client:
        for ch in channels:
            try:
                async for m in client.iter_messages(ch, limit=limit):
                    if m.message:
                        author = (getattr(m.sender, "username", None) or ch).lower()
                        p = make_post("telegram", author, m.date.isoformat(), m.message, f"https://t.me/{ch}/{m.id}")
                        if p:
                            posts.append(p)
            except Exception as e:  # telethon raises many RPC error types per channel
                log.warning("telegram %s failed: %r", ch, e)
    return posts
