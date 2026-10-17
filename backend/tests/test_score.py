import pytest

from gt.analytics.funding import gas_funders
from gt.analytics.graph import build_graph, cluster_wallets, link_bridges
from gt.fusion import score
from gt.fusion.score import build_signals, decay, explain, label, link_for, posterior
from gt.osint.extract import extract
from gt.osint.style import resolve_identities
from gt.schema import Link, Signal
from gt.simulator import simulate


def test_posterior_math():
    assert abs(posterior([], 0.01) - 0.01) < 1e-9
    assert posterior([Signal("a", 30, ""), Signal("b", 20, "")], 0.01) > 0.85


def test_single_signal_is_capped():
    assert posterior([Signal("a", 1e9, "")], 0.01) < 0.34   # cap 50 → odds 0.505


def test_evidence_against_lowers_score():
    assert posterior([Signal("rhythm", 0.5, "")], 0.01) < 0.01
    assert posterior([Signal("x", 0.0, "")], 0.01) > 0     # floor 0.1, never exactly zero


def test_decay_half_life():
    assert abs(decay(0.8, 3600, 3600) - 0.4) < 1e-9
    assert decay(0.8, 0) == 0.8


def test_labels():
    assert label(0.9, "suspected") == "high" and label(0.2, "confirmed") == "confirmed"
    assert label(0.6, "suspected") == "medium" and label(0.1, "suspected") == "low"
    assert label(0.99, "rejected") == "rejected"


def test_explain_template_orders_by_strength():
    l = Link("0:forum:ghostfox", 0, "forum:ghostfox", 0.82,
             [Signal("rhythm", 3, "same time zone"), Signal("address_mention", 30, "posted wallet 0xab")])
    text = explain(l)
    assert text.startswith("Suspected (82%): forum:ghostfox ↔ cluster 0.")
    assert text.index("posted wallet") < text.index("same time zone")


def test_explain_polish_uses_llm_only_when_asked(monkeypatch):
    calls = []
    monkeypatch.setattr(score.llm, "complete", lambda p, **k: calls.append(p) or "Strong link.")
    l = Link("0:x", 0, "x", 0.5, [Signal("rhythm", 3, "tz")])
    assert "Strong link." not in explain(l) and not calls
    assert explain(l, polish=True).startswith("Strong link.")
    monkeypatch.setattr(score.llm, "complete", lambda p, **k: None)
    assert explain(l, polish=True).startswith("Suspected (50%)")


def test_link_for_builds_scored_link():
    l = link_for(0, "forum:x", [Signal("address_mention", 30, "d")], age_s=0, now_ts=100)
    assert l.link_id == "0:forum:x" and l.status == "suspected" and l.updated_ts == 100
    assert abs(l.score - posterior(l.signals)) < 1e-12


@pytest.fixture(scope="module")
def case():
    s = simulate(seed=3)
    G = build_graph(s.transfers)
    link_bridges(G, s.transfers)
    c = cluster_wallets(G, gas_funders(s.transfers), {sorted(s.truth.attacker_wallets)[0]}, s.labels)
    cluster = {w for w, k in c.items() if k == 0}
    ids = resolve_identities(s.posts)
    entities = [e for p in s.posts for e in extract(p)]
    by_id: dict[str, list] = {}
    for p in s.posts:
        by_id.setdefault(ids[f"{p.source}:{p.author}"], []).append(p)
    return s, cluster, by_id, entities


def test_attacker_identity_scores_high(case):
    s, cluster, by_id, entities = case
    sig = build_signals(cluster, by_id["forum:ghostfox"], entities, s.transfers, s.bytecodes)
    names = {x.name for x in sig}
    assert {"time_delta", "rhythm", "address_mention", "bytecode", "onchain_message"} <= names
    assert posterior(sig) >= 0.8


def test_busiest_noise_identity_scores_low(case):
    s, cluster, by_id, entities = case
    noise = max((k for k in by_id if k != "forum:ghostfox"), key=lambda k: len(by_id[k]))
    sig = build_signals(cluster, by_id[noise], entities, s.transfers, s.bytecodes)
    assert posterior(sig) <= 0.2
    assert all(x.lr != 1.0 or x.name in {"time_delta", "bytecode"} for x in sig)   # no fake placeholders


def test_missing_inputs_emit_nothing():
    assert build_signals(set(), [], [], [], {}) == []
