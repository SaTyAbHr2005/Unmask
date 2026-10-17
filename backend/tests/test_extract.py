from gt.osint.extract import extract, make_post


def test_extracts_all_kinds():
    p = make_post("forum", "x", 1, "send to 0x" + "Ab" * 20 + " tx 0x" + "c" * 64 +
                  " ip 10.0.0.5 mail a@b.io @ghostfox vitalik.eth")
    kinds = {(e.kind, e.value) for e in extract(p)}
    assert ("address", "0x" + "ab" * 20) in kinds
    assert ("tx", "0x" + "c" * 64) in kinds
    assert {"ip", "email", "handle", "ens"} <= {k for k, _ in kinds}
    assert sum(1 for k, _ in kinds if k == "address") == 1   # tx hash not double-counted


def test_post_without_time_is_dropped():
    assert make_post("rss", "x", "garbage", "hi") is None


def test_no_entities_is_empty_not_error():
    assert extract(make_post("forum", "x", 1, "nothing here")) == []


def test_email_is_not_also_a_handle():
    vals = {(e.kind, e.value) for e in extract(make_post("forum", "x", 1, "write to Bob.Smith@Mail.io now"))}
    assert vals == {("email", "bob.smith@mail.io")}


def test_handle_and_ens_values():
    vals = {(e.kind, e.value) for e in extract(make_post("forum", "x", 1, "ping @Gh0st_Fox or Fox-Ghost.ETH"))}
    assert vals == {("handle", "gh0st_fox"), ("ens", "fox-ghost.eth")}


def test_invalid_ip_rejected():
    assert extract(make_post("forum", "x", 1, "version 999.1.2.3")) == []


def test_duplicates_collapse_and_ids_are_stable():
    p = make_post("forum", "x", 1, "0x" + "a" * 40 + " again 0x" + "A" * 40)
    a, b = extract(p), extract(p)
    assert len(a) == 1 and a == b and a[0].post_id == p.post_id


def test_make_post_normalizes_time_and_id():
    p = make_post("rss", "feed", "2026-10-17T02:14:00+05:30", "hello")
    q = make_post("rss", "feed", "2026-10-16T20:44:00Z", "hello")
    assert p.ts == q.ts and p.post_id == q.post_id and len(p.post_id) == 16
