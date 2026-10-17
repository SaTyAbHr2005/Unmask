"""Guards: spot an attack being prepared before it happens, and filter out the decoys an attacker plants."""
from gt.config import usd
from gt.schema import Alert, Transfer


def prewarn(transfers: list[Transfer], labels: dict[str, str], window_s: int = 24 * 3600) -> list[Alert]:
    """Flag wallet W when, within window_s of being funded through a mixer (directly or via one funder),
    W deploys a contract and makes ≥ 2 test calls — the usual run-up to an exploit."""
    txs = sorted(transfers, key=lambda t: t.ts)
    mixers = {a for a, l in labels.items() if l == "mixer"}
    direct: dict[str, int] = {}
    for t in txs:
        if (t.kind == "mixer_out" or t.from_addr in mixers) and t.to_addr not in labels:
            direct.setdefault(t.to_addr, t.ts)
    funded = dict(direct)
    for t in txs:
        if t.from_addr in direct and t.ts >= direct[t.from_addr] and t.asset == "ETH" and t.amount > 0 \
                and t.to_addr not in labels:
            funded.setdefault(t.to_addr, t.ts)

    by_sender: dict[str, list[Transfer]] = {}
    for t in txs:
        by_sender.setdefault(t.from_addr, []).append(t)
    alerts = []
    for w, f in sorted(funded.items()):
        mine = [t for t in by_sender.get(w, []) if f <= t.ts <= f + window_s]
        deploys = [t.ts for t in mine if t.kind == "deploy"]
        tests = [t.ts for t in mine if t.kind == "test_call"]
        if deploys and len(tests) >= 2:
            when = max(deploys[0], tests[1])
            alerts.append(Alert(f"prewarn:{w}", "prewarn", w,
                                f"Pre-attack pattern: {w[:12]}… was funded through a mixer, deployed a contract and "
                                f"ran {len(tests)} test calls within {(when - f) / 3600:.1f}h — an exploit may be "
                                f"being prepared.", "pending", when))
    return alerts


def is_lookalike(a: str, b: str) -> bool:
    """Address poisoning: same first 6 and last 4 hex characters (what wallets show), different address."""
    return a != b and a[2:8] == b[2:8] and a[-4:] == b[-4:]


def find_decoys(transfers: list[Transfer], attacker: set[str], known: set[str], dust_usd: float = 1.0) -> set[str]:
    """Wallets the attacker sprayed with dust (worth > $0 and < dust_usd) that never paid the attacker back,
    plus any look-alike of a known address that the attacker paid."""
    paid_back = {t.from_addr for t in transfers if t.to_addr in attacker}
    known_shapes = {(k[2:8], k[-4:]) for k in known}
    decoys = set()
    for t in transfers:
        if t.from_addr not in attacker or t.to_addr in attacker:
            continue
        value = usd(t.asset, t.amount)
        if value is not None and 0 < value < dust_usd and t.to_addr not in paid_back:
            decoys.add(t.to_addr)
        if t.to_addr not in known and (t.to_addr[2:8], t.to_addr[-4:]) in known_shapes:
            decoys.add(t.to_addr)
    return decoys
