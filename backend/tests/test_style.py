from gt.osint.extract import make_post
from gt.osint.style import resolve_identities, style_similarity, username_similarity
from gt.simulator import simulate


def test_leet_usernames_match():
    assert username_similarity("ghostfox", "gh0st_fox") > 0.9
    assert username_similarity("ghostfox", "alice") < 0.5


def test_reordered_name_parts_match():
    assert username_similarity("ghostfox", "fox_ghost") >= 0.9
    assert username_similarity("Fox-Ghost", "GH0STFOX") >= 0.9


def test_style_similarity():
    a = ["lol ur pool is cooked fr", "ngl ur devs r slow lol"]
    b = ["ur bridge is free money fr", "lol who audits this ngl"]
    c = ["The governance proposal looks reasonable.", "Please review the audit report next week."]
    assert style_similarity(a, b) > style_similarity(a, c)
    assert style_similarity([], b) == 0.0


def _posts(*rows):
    return [make_post(src, author, i, text) for i, (src, author, text) in enumerate(rows)]


def test_style_alone_does_not_merge_unrelated_names():
    same = "Gas is quite low this morning, good time to bridge."
    ids = resolve_identities(_posts(("forum", "river_maple", same), ("forum", "cobalt_orbit", same)))
    assert ids["forum:river_maple"] != ids["forum:cobalt_orbit"]


def test_canonical_is_alphabetically_first_member():
    ids = resolve_identities(_posts(("telegram", "fox_ghost", "lol"), ("forum", "ghostfox", "fr")))
    assert ids == {"telegram:fox_ghost": "forum:ghostfox", "forum:ghostfox": "forum:ghostfox"}


def test_simulator_handles_resolve_to_one_identity():
    s = simulate(seed=5)
    ids = resolve_identities(s.posts)
    att = {ids[f"{p.source}:{p.author}"] for p in s.posts if p.author in s.truth.attacker_handles}
    assert len(att) == 1


def test_simulator_noise_authors_stay_separate():
    s = simulate(seed=5)
    ids = resolve_identities(s.posts)
    att_id = ids[f"forum:ghostfox"]
    noise_keys = {f"{p.source}:{p.author}" for p in s.posts if p.author not in s.truth.attacker_handles}
    assert all(ids[k] != att_id for k in noise_keys)
    assert len({ids[k] for k in noise_keys}) >= 55   # 60 noise authors, almost none merged
