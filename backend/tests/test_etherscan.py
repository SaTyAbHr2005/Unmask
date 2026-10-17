import json

import httpx
import pytest

from gt.chain import etherscan
from gt.schema import Transfer


class FakeHttp:
    def __init__(self, responses):
        self.responses, self.calls, self.params = list(responses), 0, []

    def get(self, url, params, timeout):
        self.calls += 1
        self.params.append(params)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class R:
    def __init__(self, code, body):
        self.status_code, self._b = code, body

    def json(self):
        return self._b


@pytest.fixture(autouse=True)
def _cache(tmp_path, monkeypatch):
    monkeypatch.setattr(etherscan, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(etherscan, "_last_call", [0.0])


def nosleep(s):
    pass


def test_retries_on_429_then_succeeds():
    http = FakeHttp([R(429, {}), R(200, {"status": "1", "result": [{"hash": "0x1"}]})])
    assert etherscan.get({"a": 1}, http=http, sleep=nosleep) == [{"hash": "0x1"}]
    assert http.calls == 2


def test_gives_up_without_crashing():
    http = FakeHttp([R(429, {})] * 5)
    assert etherscan.get({"b": 1}, http=http, sleep=nosleep) == []
    assert http.calls == 5


def test_rate_limit_message_and_timeout_are_retried():
    http = FakeHttp([R(200, {"status": "0", "message": "NOTOK", "result": "Max rate limit reached"}),
                     httpx.TimeoutException("slow"),
                     R(200, {"status": "1", "result": [7]})])
    assert etherscan.get({"d": 1}, http=http, sleep=nosleep) == [7]


def test_no_transactions_is_empty_without_retry():
    http = FakeHttp([R(200, {"status": "0", "message": "No transactions found", "result": []})])
    assert etherscan.get({"e": 1}, http=http, sleep=nosleep) == [] and http.calls == 1


def test_cache_hit_skips_network():
    http = FakeHttp([R(200, {"status": "1", "result": [1]})])
    etherscan.get({"c": 1}, http=http, sleep=nosleep)
    assert etherscan.get({"c": 1}, http=http, sleep=nosleep) == [1] and http.calls == 1


def test_failures_are_not_cached():
    etherscan.get({"f": 1}, http=FakeHttp([R(429, {})] * 5), sleep=nosleep)
    assert etherscan.get({"f": 1}, http=FakeHttp([R(200, {"status": "1", "result": [2]})]), sleep=nosleep) == [2]


def test_proxy_result_and_api_key_not_in_cache_key(monkeypatch):
    monkeypatch.setattr(etherscan, "env", lambda k: "SECRET")
    http = FakeHttp([R(200, {"jsonrpc": "2.0", "id": 1, "result": "0x6080"})])
    assert etherscan.get({"module": "proxy"}, http=http, sleep=nosleep) == "0x6080"
    assert http.params[0]["apikey"] == "SECRET" and http.params[0]["chainid"] == 1
    assert "SECRET" not in "".join(p.read_text() for p in etherscan.CACHE_DIR.glob("*.json"))


TX = {"hash": "0xH", "from": "0xAA", "to": "0xBB", "value": "1500000000000000000", "gasPrice": "20000000000",
      "nonce": "5", "input": "0x", "timeStamp": "1760000000", "isError": "0", "contractAddress": ""}


def test_txlist_converts_rows(monkeypatch):
    rows = [TX, {**TX, "hash": "0xD", "to": "", "contractAddress": "0xCC", "value": "0"},
            {**TX, "hash": "0xF", "isError": "1"}]
    monkeypatch.setattr(etherscan, "get", lambda params, chainid=1: rows)
    out = etherscan.txlist("0xAA", chainid=42161)
    assert out[0] == Transfer("0xh", "arb", 1760000000, "0xaa", "0xbb", "ETH", 1.5, 20.0, 5, "0x", "transfer")
    assert out[1].to_addr == "0xcc" and out[1].kind == "deploy"
    assert len(out) == 2  # failed tx dropped


def test_tokentx_converts_rows(monkeypatch):
    row = {**TX, "value": "2500000", "tokenDecimal": "6", "tokenSymbol": "USDT", "logIndex": "3"}
    monkeypatch.setattr(etherscan, "get", lambda params, chainid=1: [row])
    t = etherscan.tokentx("0xaa")[0]
    assert (t.tx_hash, t.asset, t.amount, t.chain) == ("0xh:3", "USDT", 2.5, "eth")


def _fake_chain(monkeypatch, edges, labels=None):
    def rows(addr, chainid=1, blocks=etherscan.ALL_BLOCKS):
        return [Transfer(f"0x{a}{b}", "eth", 1, a, b, "ETH", 1.0) for a, b in edges if addr in (a, b)]
    monkeypatch.setattr(etherscan, "txlist", rows)
    monkeypatch.setattr(etherscan, "tokentx", lambda addr, chainid=1, blocks=etherscan.ALL_BLOCKS: [])
    monkeypatch.setattr(etherscan, "get_code", lambda addr, chainid=1: "0x60")
    monkeypatch.setattr(etherscan, "load_labels", lambda: labels or {})


def _replay(tmp_path, hops=2):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"name": "t", "seed_addresses": ["0xA"], "chainids": [1], "hops": hops}))
    return str(p)


def test_replay_follows_money_forward_for_n_hops(tmp_path, monkeypatch):
    _fake_chain(monkeypatch, [("0xf", "0xa"), ("0xa", "0xb"), ("0xb", "0xc"), ("0xc", "0xd"), ("0xd", "0xe")])
    transfers, _ = etherscan.load_replay(_replay(tmp_path, hops=2))
    hashes = {t.tx_hash for t in transfers}
    assert hashes == {"0x0xf0xa", "0x0xa0xb", "0x0xb0xc", "0x0xc0xd"}  # funder kept; 0xd not expanded


def test_replay_does_not_expand_labeled_hubs(tmp_path, monkeypatch):
    _fake_chain(monkeypatch, [("0xa", "0xex"), ("0xex", "0xz")], labels={"0xex": "exchange:X"})
    transfers, _ = etherscan.load_replay(_replay(tmp_path))
    assert {t.tx_hash for t in transfers} == {"0x0xa0xex"}


def test_replay_cap_and_bytecodes(tmp_path, monkeypatch):
    _fake_chain(monkeypatch, [("0xa", f"0x{i}") for i in range(50)])
    transfers, _ = etherscan.load_replay(_replay(tmp_path), max_transfers=10)
    assert len(transfers) == 10
    calls = []
    monkeypatch.setattr(etherscan, "tokentx", lambda addr, chainid=1, blocks=None: calls.append(addr) or [])
    etherscan.load_replay(_replay(tmp_path), max_transfers=10)
    assert calls == ["0xa"]   # the cap was hit on the seed: none of its 50 recipients is fetched
    monkeypatch.setattr(etherscan, "txlist",
                        lambda a, chainid=1, blocks=None: [Transfer("0xd", "eth", 1, "0xa", "0xc", "ETH", 0.0, kind="deploy")])
    _, codes = etherscan.load_replay(_replay(tmp_path))
    assert codes == {"0xc": "0x60"}


def test_replay_window_limits_blocks_and_drops_spam_tokens(tmp_path, monkeypatch):
    _fake_chain(monkeypatch, [("0xa", "0xb")])
    asked = []
    monkeypatch.setattr(etherscan, "block_at", lambda ts, chainid=1: {1678665600: 100, 1682812800: 200}[ts])
    monkeypatch.setattr(etherscan, "tokentx", lambda a, chainid=1, blocks=None: asked.append(blocks) or [
        Transfer("0xspam", "eth", 1, "0xa", "0xs", "CASH", 9e9), Transfer("0xdai", "eth", 1, "0xa", "0xd", "DAI", 5.0)])
    p = tmp_path / "w.json"
    p.write_text(json.dumps({"seed_addresses": ["0xA"], "hops": 0, "window": ["2023-03-13", "2023-04-30"]}))
    transfers, _ = etherscan.load_replay(str(p))
    assert asked == [(100, 200)]                                 # Etherscan is asked only for the incident's blocks
    assert {t.tx_hash for t in transfers} == {"0x0xa0xb", "0xdai"}   # unpriced airdrop dropped
