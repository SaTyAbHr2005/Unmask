"""Gas-funder tracing: every fresh wallet needs a little ETH for fees before it can act — who sent it?"""
from gt.schema import Transfer


def gas_funders(transfers: list[Transfer], max_gas_eth: float = 0.1, min_gas_eth: float = 0.001) -> dict[str, str]:
    """wallet -> funder, when the wallet's FIRST incoming ETH is a small (≤ max_gas_eth) payment
    and the wallet sends its first transaction after receiving it. Dust below min_gas_eth is ignored:
    it can't pay for anything, and attackers spray it at innocent wallets to fake links."""
    first_in: dict[str, Transfer] = {}
    first_out: dict[str, int] = {}
    for t in sorted(transfers, key=lambda t: t.ts):
        first_out.setdefault(t.from_addr, t.ts)
        if t.asset == "ETH" and t.amount >= min_gas_eth:
            first_in.setdefault(t.to_addr, t)
    return {w: t.from_addr for w, t in first_in.items()
            if t.amount <= max_gas_eth and w in first_out and first_out[w] >= t.ts and t.from_addr != w}


def funding_clusters(funders: dict[str, str], exclude: set[str]) -> dict[str, int]:
    """Union wallets with their funders (never through excluded hubs). Returns wallet -> group id."""
    parent: dict[str, str] = {}

    def root(a: str) -> str:
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for w, f in funders.items():
        if w in exclude:
            continue
        root(w)
        if f not in exclude:
            ra, rb = root(w), root(f)
            parent[max(ra, rb)] = min(ra, rb)
    roots = sorted({root(a) for a in parent})
    ids = {r: i for i, r in enumerate(roots)}
    return {a: ids[root(a)] for a in parent}
