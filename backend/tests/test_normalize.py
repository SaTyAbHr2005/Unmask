from gt.chain.labels import load_labels
from gt.chain.normalize import classify, decode_message, norm_addr, to_utc
from gt.schema import Transfer


def test_checksum_and_lower_are_same_wallet():
    assert norm_addr(" 0xAbCDef ") == norm_addr("0xabcdef") == "0xabcdef"
    assert norm_addr(None) == ""


def test_to_utc_offsets():
    assert to_utc("2026-10-17T02:14:00+05:30") == to_utc("2026-10-16T20:44:00Z")
    assert to_utc("Fri, 17 Oct 2026 02:14:00 GMT") == to_utc("2026-10-17T02:14:00Z")
    assert to_utc("not a date") is None


def test_to_utc_numbers_and_naive():
    assert to_utc(1760000000) == 1760000000
    assert to_utc("1760000000") == 1760000000            # Etherscan sends timeStamp as a digit string
    assert to_utc("2026-10-17T02:14:00") == to_utc("2026-10-17T02:14:00Z")  # naive = UTC
    assert to_utc(None) is None and to_utc("") is None


def test_decode_message():
    assert decode_message("0x" + b"contact me for bounty".hex()) == "contact me for bounty"
    assert decode_message("0xa9059cbb000000000000") is None   # ERC-20 call data, not text
    assert decode_message("0x") is None and decode_message("0xabc") is None  # empty / odd length
    assert decode_message("0x" + b"hi".hex()) is None          # too short


def test_classify_mixer():
    t = Transfer("h", "eth", 1, "0xa", "0xmix", "ETH", 1.0)
    assert classify(t, {"0xmix": "mixer"}) == "mixer_in"


def test_classify_all_directions():
    def k(frm, to, kind="transfer"):
        return classify(Transfer("h", "eth", 1, frm, to, "ETH", 1.0, kind=kind),
                        {"0xmix": "mixer", "0xbr": "bridge", "0xdex": "dex"})
    assert k("0xmix", "0xa") == "mixer_out"
    assert k("0xa", "0xbr") == "bridge_out" and k("0xbr", "0xa") == "bridge_in"
    assert k("0xa", "0xdex") == "swap" and k("0xdex", "0xa") == "swap"
    assert k("0xa", "0xb") == "transfer"
    assert k("0xa", "0xmix", kind="deploy") == "deploy"   # explicit kinds are kept


def test_load_labels_merges_and_normalizes(tmp_path):
    (tmp_path / "a.csv").write_text("# source: test\naddress,label\n0xABC,mixer\n", encoding="utf-8")
    (tmp_path / "b.csv").write_text("address,label\n0xdef,exchange:Binance\n\n", encoding="utf-8")
    assert load_labels(str(tmp_path)) == {"0xabc": "mixer", "0xdef": "exchange:Binance"}
    assert load_labels(str(tmp_path / "missing")) == {}
