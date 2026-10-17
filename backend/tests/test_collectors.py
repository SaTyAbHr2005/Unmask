import asyncio

import httpx

from gt import llm
from gt.osint import collectors


class R:
    def __init__(self, code, body=None):
        self.status_code, self._b = code, body or {}

    def json(self):
        return self._b


class FakeHttp:
    """Answers by URL substring; records calls."""
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def _answer(self, url):
        self.calls.append(url)
        for key, resp in self.routes.items():
            if key in url:
                if isinstance(resp, Exception):
                    raise resp
                return resp
        return R(404)

    def get(self, url, params=None, headers=None, timeout=None):
        return self._answer(url)

    def post(self, url, json=None, headers=None, params=None, timeout=None):
        return self._answer(url)


FEED = {"feed": {"title": "rekt"}, "entries": [
    {"title": "Pool drained", "summary": "attacker 0x" + "a" * 40, "link": "https://rekt.news/x",
     "published": "Fri, 17 Oct 2026 02:14:00 GMT"},
    {"title": "no date", "summary": "dropped"}]}


def test_rss_parses_entries_and_drops_undated():
    posts = collectors.collect_rss(["u"], parse=lambda url, **kw: FEED)
    assert len(posts) == 1
    p = posts[0]
    assert (p.source, p.author, p.ts, p.url) == ("rss", "rekt", 1792203240, "https://rekt.news/x")
    assert "Pool drained" in p.text and "0x" + "a" * 40 in p.text


def test_rss_bad_feed_is_skipped():
    def boom(url, **kw):
        raise ValueError("bad xml")
    assert collectors.collect_rss(["u"], parse=boom) == []


COMMITS = {"items": [{"html_url": "https://github.com/gh0stfox/flash/commit/1",
                      "commit": {"message": "add drainPool", "author": {"date": "2026-10-14T02:14:00Z"}},
                      "author": {"login": "gh0stfox"}, "repository": {"owner": {"login": "gh0stfox"}}}]}
CODE = {"items": [{"html_url": "https://github.com/x/y/blob/main/F.sol",
                   "repository": {"owner": {"login": "Xdev"}, "url": "https://api.github.com/repos/x/y"},
                   "text_matches": [{"fragment": "function flashAttack(address a, uint256 b)"}]}]}


def test_github_403_returns_empty():
    assert collectors.collect_github(["exploit"], http=FakeHttp({"search": R(403)})) == []


def test_github_commits_and_code(monkeypatch):
    monkeypatch.setattr(collectors, "env", lambda k: "tok" if k == "GITHUB_TOKEN" else None)
    http = FakeHttp({"search/commits": R(200, COMMITS), "search/code": R(200, CODE),
                     "repos/x/y": R(200, {"pushed_at": "2026-10-15T00:00:00Z"})})
    posts = {p.author: p for p in collectors.collect_github(["flash"], http=http)}
    assert posts["gh0stfox"].text == "add drainPool" and posts["gh0stfox"].source == "github"
    assert posts["gh0stfox"].ts == 1791944040
    assert "flashAttack" in posts["xdev"].text and posts["xdev"].ts == 1792022400


def test_github_stops_at_rate_limit_but_keeps_what_it_has(monkeypatch):
    monkeypatch.setattr(collectors, "env", lambda k: "tok" if k == "GITHUB_TOKEN" else None)
    http = FakeHttp({"search/commits": R(200, COMMITS), "search/code": R(429)})
    posts = collectors.collect_github(["flash", "second-query"], http=http)
    assert [p.author for p in posts] == ["gh0stfox"]
    assert len(http.calls) == 2  # commits + code for the first query, then it stops


def test_github_skips_code_search_without_token(monkeypatch):
    monkeypatch.setattr(collectors, "env", lambda k: None)
    http = FakeHttp({"search/commits": R(200, COMMITS), "search/code": R(200, CODE)})
    assert [p.author for p in collectors.collect_github(["flash"], http=http)] == ["gh0stfox"]
    assert not any("search/code" in c for c in http.calls)


def test_github_network_error_is_safe():
    assert collectors.collect_github(["q"], http=FakeHttp({"search": httpx.ConnectError("down")})) == []


def test_telegram_without_keys_is_empty(monkeypatch):
    monkeypatch.setattr(collectors, "env", lambda k: None)
    assert asyncio.run(collectors.collect_telegram(["somechannel"])) == []


def test_llm_without_keys_returns_none(monkeypatch):
    monkeypatch.setattr(llm, "env", lambda k: None)
    assert llm.complete("hi") is None


def test_llm_groq_then_gemini_fallback(monkeypatch):
    monkeypatch.setattr(llm, "env", lambda k: {"GROQ_API_KEY": "g", "GEMINI_API_KEY": "m"}.get(k))
    ok_groq = FakeHttp({"groq": R(200, {"choices": [{"message": {"content": " groq says hi "}}]})})
    assert llm.complete("hi", http=ok_groq) == "groq says hi"
    fallback = FakeHttp({"groq": R(500), "generativelanguage": R(200, {
        "candidates": [{"content": {"parts": [{"text": "gemini says hi"}]}}]})})
    assert llm.complete("hi", http=fallback) == "gemini says hi"
    assert llm.complete("hi", http=FakeHttp({"groq": R(500), "generativelanguage": httpx.ConnectError("x")})) is None
    # a reasoning model that spent the whole budget thinking answers "" (or null): that's a miss, try Gemini
    empty = FakeHttp({"groq": R(200, {"choices": [{"message": {"content": None}}]}), "generativelanguage": R(200, {
        "candidates": [{"content": {"parts": [{"text": "gemini says hi"}]}}]})})
    assert llm.complete("hi", http=empty) == "gemini says hi"
