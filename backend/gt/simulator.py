"""Synthetic 'Ghost Attack' with ground truth — the offline demo backbone and the accuracy benchmark.

Story: a mixer-funded wallet deploys an exploit, steals 14,000 ETH ($42M), a bot splits it over
hundreds of gas-funded wallets, routes the pieces through a mixer / a bridge / a DEX, consolidates,
and cashes out at two exchanges. The attacker chats on a forum minutes before acting.
"""
from dataclasses import dataclass

import numpy as np
from eth_hash.auto import keccak

from gt.config import ETH_USD
from gt.osint.extract import make_post
from gt.osint.style import NAME_GATE, username_similarity
from gt.schema import OsintPost, Transfer

TOTAL_ETH = 42_000_000 / ETH_USD
EXPLOIT_FUNCS = ["flashAttack(address,uint256)", "drainPool(address)", "withdrawAll()"]
HANDLES = {"forum": "ghostfox", "github": "gh0stfox", "telegram": "fox_ghost"}
DAY = 86_400

ATTACKER_LINES = [
    "lol ur bridge devs never check reentrancy fr", "ngl this pool is free money lol",
    "ur oracle is cooked fr fr", "who even audits these lol", "gm. ur liquidity looks juicy ngl",
    "flashloans r too ez lol", "ur multisig is a joke fr", "ngl i'd patch that if i were u lol",
    "imagine not using a timelock lol", "ur tvl wont last the week fr",
]
NOISE_LINES = [
    "The new governance proposal looks reasonable to me.", "Has anyone benchmarked the latest rollup fees?",
    "Reminder: never share your seed phrase with anyone.", "Gas is quite low this morning, good time to bridge.",
    "Our audit report will be published next Tuesday.", "Is the staking dashboard down for anyone else?",
    "Interesting thread on MEV protection, worth reading.", "We have shipped v2 of the SDK. Feedback welcome!",
    "Could someone explain how the liquidation threshold works?", "Market looks sideways; I am mostly holding.",
]
NAME_A = ["night", "void", "rust", "cold", "grey", "null", "iron", "dark", "frost", "zero", "lunar", "quiet", "static",
          "ember", "neon"]
NAME_B = ["owl", "cat", "wolf", "moth", "crow", "lynx", "viper", "raven", "hare", "mole", "wasp", "yak", "newt", "orca"]
SYLLABLES = ["ka", "lo", "mi", "zen", "tor", "vi", "ra", "ne", "dus", "pe", "qu", "bri", "sol", "am", "jet",
             "won", "hex", "yur", "gal", "fen", "ok", "tuz", "bax", "ru", "sig", "dor", "ip", "wex", "cha", "mun"]


@dataclass
class Truth:
    attacker_wallets: set[str]
    attacker_handles: set[str]
    decoy_wallets: set[str]
    exit_exchanges: set[str]
    utc_offset: int


@dataclass
class Scenario:
    transfers: list[Transfer]
    posts: list[OsintPost]
    labels: dict[str, str]
    bytecodes: dict[str, str]
    truth: Truth


def selector(sig: str) -> str:
    return keccak(sig.encode()).hex()[:8]


class _Gen:
    def __init__(self, seed: int, utc_offset: int, t0: int):
        self.rng = np.random.default_rng(seed)
        self.off = utc_offset
        self.clock = float(t0)
        self.transfers: list[Transfer] = []
        self.nonce: dict[str, int] = {}

    def addr(self, prefix: str = "") -> str:
        while True:
            a = "0x" + prefix + self.rng.bytes(20).hex()[len(prefix):]
            if prefix or not a.startswith("0x00"):
                return a

    def awake(self, ts: float, off: int | None = None) -> float:
        """Push a timestamp forward into local 09:00–23:59."""
        h = int((ts + (self.off if off is None else off) * 3600) // 3600) % 24
        return ts + (9 - h) * 3600 if h < 9 else ts

    def step(self, lo: float = 20, hi: float = 40) -> int:
        """Advance the attacker bot's clock (uniform gaps = bot signature), staying in waking hours."""
        self.clock = self.awake(self.clock + self.rng.uniform(lo, hi))
        return int(self.clock)

    def tx(self, ts: float, frm: str, to: str, amount: float, asset: str = "ETH", kind: str = "transfer",
           chain: str = "eth", gas: float = 25.0, data: str = "0x") -> Transfer:
        n = self.nonce.get(frm, 0)
        self.nonce[frm] = n + 1
        t = Transfer("0x" + self.rng.bytes(32).hex(), chain, int(ts), frm, to, asset, float(amount),
                     float(gas), n, data, kind)
        self.transfers.append(t)
        return t


def _post(source: str, author: str, ts: int, text: str, url: str = "") -> OsintPost:
    return make_post(source, author, int(ts), text, url)


def _noise_names(rng, n: int, handles: dict[str, str]) -> list[str]:
    """Distinct-looking usernames, like real strangers (no two resemble each other or the attacker's handles)."""
    names: list[str] = []
    for _ in range(20_000):
        cand = "".join(rng.choice(SYLLABLES, size=int(rng.integers(2, 4))))
        if all(username_similarity(cand, m) < NAME_GATE for m in names + list(handles.values())):
            names.append(cand)
            if len(names) == n:
                break
    return names


def variant(seed: int) -> dict:
    """What makes attack <seed> a different attacker on the website: name, amount, time zone, wallet count.
    Seed 7 is the story's attack and stays as it is. Drawn from its own random stream, so the rest of the
    scenario for a given seed doesn't shift."""
    if seed == 7:
        return {}
    v = np.random.default_rng([seed, 2026])
    a, b = str(v.choice(NAME_A)), str(v.choice(NAME_B))
    leet = str.maketrans({"o": "0", "e": "3", "a": "4"})
    return {"handles": {"forum": a + b, "github": (a + b).translate(leet), "telegram": f"{b}_{a}"},
            "total_usd": round(float(v.uniform(8, 150)), 1) * 1e6,
            "utc_offset": int(v.choice([-7, -5, -4, -3, 0, 1, 2, 3, 5, 7, 8, 9, 10])),
            "n_split": int(v.integers(120, 401))}


def simulate(seed: int = 7, n_split: int = 300, n_noise_wallets: int = 1500,
             utc_offset: int = 9, t0: int = 1_760_000_000, handles: dict[str, str] | None = None,
             total_usd: float = 42_000_000) -> Scenario:
    handles = handles or HANDLES
    total_eth = total_usd / ETH_USD
    g = _Gen(seed, utc_offset, t0)
    rng = g.rng

    victim, mixer, dex = g.addr(), g.addr(), g.addr()
    bridge_eth, bridge_arb = g.addr(), g.addr()
    ex_a, ex_b, ex_b_arb = g.addr(), g.addr(), g.addr()
    labels = {victim: "victim", mixer: "mixer", dex: "dex", bridge_eth: "bridge", bridge_arb: "bridge",
              ex_a: "exchange:Exch-A", ex_b: "exchange:Exch-B", ex_b_arb: "exchange:Exch-B"}

    main = g.addr("00")
    funder0, f1, f2, contract = g.addr(), g.addr(), g.addr(), g.addr()
    attacker = [main, funder0, f1, f2, contract]

    # 1. Pre-attack: mixer-funded gas wallet → main → exploit deploy + test calls
    g.clock = float(t0 - 6 * 3600)
    g.tx(g.clock, mixer, funder0, 10.0, kind="mixer_out")
    g.tx(g.step(60, 120), funder0, main, 0.05)
    g.tx(g.step(60, 120), funder0, f1, 4.0)
    g.tx(g.step(60, 120), funder0, f2, 4.0)
    code = "0x6080604052" + "".join(f"8063{selector(s)}1461010057" for s in EXPLOIT_FUNCS) + "00"
    g.tx(g.step(300, 600), main, contract, 0.0, kind="deploy")
    for _ in range(3):
        g.tx(g.step(300, 900), main, contract, 0.0, kind="test_call")

    # 2. Theft
    g.tx(t0, victim, main, total_eth)
    g.clock = max(g.clock, float(t0))
    msg = "0x" + f"contact {handles['forum']} on forum for bounty".encode().hex()
    g.tx(g.step(), main, victim, 0.0, data=msg)

    # 3. Split: each child gets gas from a funder first, then its share
    shares = rng.dirichlet([0.8] * n_split) * total_eth
    children = [g.addr() for _ in range(n_split)]
    for child, amt in zip(children, shares):
        g.tx(g.step(), f1 if rng.random() < 0.5 else f2, child, 0.01)
        g.tx(g.step(), main, child, amt)
    attacker += children

    # 4. Route: 40% mixer, 30% bridge, 30% DEX→USDT
    mixed, bridged, swapped = [], [], []
    for child, amt in zip(children, shares):
        route = rng.choice(3, p=[0.4, 0.3, 0.3])
        if route == 0:
            t_in = g.step()
            g.tx(t_in, child, mixer, amt, kind="mixer_in")
            w = g.addr()
            g.tx(g.step(), f1 if rng.random() < 0.5 else f2, w, 0.01)
            out = amt * 0.997
            g.tx(t_in + rng.uniform(600, 3600), mixer, w, out, kind="mixer_out")
            mixed.append((w, out))
        elif route == 1:
            t_out = g.step()
            g.tx(t_out, child, bridge_eth, amt, kind="bridge_out")
            w = g.addr()
            out = amt * 0.999
            g.tx(t_out + rng.uniform(120, 900), bridge_arb, w, out, kind="bridge_in", chain="arb", gas=0.01)
            bridged.append((w, out))
        else:
            g.tx(g.step(), child, dex, amt, kind="swap")
            usdt = amt * ETH_USD * 0.997
            g.tx(g.clock + 12, dex, child, usdt, asset="USDT", kind="swap")
            swapped.append((child, usdt))
    attacker += [w for w, _ in mixed] + [w for w, _ in bridged]

    # 5. Consolidate and cash out (after every routed piece has landed)
    g.clock = g.awake(max(t.ts for t in g.transfers) + 600.0)
    cons = [g.addr() for _ in range(5)]
    attacker += cons
    for c in cons:
        g.tx(g.step(), f1, c, 0.01)
    held = dict.fromkeys(cons, 0.0)
    for w, amt in mixed:
        c = cons[int(rng.integers(0, 4))]
        g.tx(g.step(), w, c, amt)
        held[c] += amt
    for child, usdt in swapped:
        if rng.random() < 0.5:
            g.tx(g.step(), child, cons[4], usdt, asset="USDT")
    for w, amt in bridged:
        if rng.random() < 0.6:
            g.tx(g.step(), w, ex_b_arb, amt, chain="arb", gas=0.01)
    g.tx(g.step(), cons[0], ex_a, held[cons[0]])
    g.tx(g.step(), cons[1], ex_a, held[cons[1]])
    g.tx(g.step(), cons[2], ex_b, held[cons[2]])
    # cons[3] keeps raw ETH (unfreezable), cons[4] keeps USDT (freezable)

    # 6. Noise: humans with round-ish amounts, Poisson timing, their own timezones
    noise = [g.addr() for _ in range(n_noise_wallets)]
    offsets = rng.integers(-8, 10, size=n_noise_wallets)
    for i, w in enumerate(noise):
        for ts in np.sort(rng.uniform(t0 - DAY, t0 + 2 * DAY, size=rng.poisson(4) + 1)):
            amt = float(rng.lognormal(-1, 1.5))
            if rng.random() < 0.3:
                grid = float(rng.choice([0.1, 1.0, 10.0]))
                amt = max(grid, round(amt / grid) * grid)
            to = (ex_a, ex_b)[int(rng.integers(0, 2))] if rng.random() < 0.15 else noise[int(rng.integers(0, n_noise_wallets))]
            g.tx(g.awake(ts, int(offsets[i])), w, to, amt, gas=float(max(1.0, rng.normal(20, 5))))

    # 7. Decoys: dust to innocent wallets + look-alikes of an exchange deposit address
    decoys = [noise[int(i)] for i in rng.choice(n_noise_wallets, size=20, replace=False)]
    decoys += ["0x" + ex_a[2:8] + rng.bytes(15).hex() + ex_a[-4:] for _ in range(2)]
    for d in decoys:
        g.tx(g.step(), main, d, 0.0001)

    # 8. OSINT: the attacker posts 2–6 min before acting; noise authors post whenever
    att_set = set(attacker)
    att_tx = sorted((t for t in g.transfers if t.from_addr in att_set), key=lambda t: t.ts)
    picks = sorted(rng.choice(len(att_tx), size=32, replace=False))
    posts = []
    for j, k in enumerate(picks):
        ts = att_tx[k].ts - int(rng.uniform(120, 360))
        line = ATTACKER_LINES[int(rng.integers(0, len(ATTACKER_LINES)))]
        if j < 25:
            posts.append(_post("forum", handles["forum"], ts, line))
        elif j == 25:
            posts.append(_post("forum", handles["forum"], ts, f"lol ur fees r insane, test wallet {children[0]} fr"))
        else:
            posts.append(_post("telegram", handles["telegram"], ts, line))
    source = "\n".join(f"    function {s.split('(')[0]}({', '.join(f'{ty} a{i}' for i, ty in enumerate(filter(None, s[s.index('(') + 1:-1].split(','))))}) external {{}}"
                       for s in EXPLOIT_FUNCS)
    posts.append(_post("github", handles["github"], t0 - 3 * DAY,
                       f"// lol ez money fr\ncontract Flash {{\n{source}\n}}", f"https://github.example/{handles['github']}/flash-tools"))
    for name in _noise_names(rng, 60, handles):
        src = "forum" if rng.random() < 0.6 else "telegram"
        for ts in rng.uniform(t0 - DAY, t0 + 2 * DAY, size=int(rng.integers(3, 16))):
            posts.append(_post(src, name, int(ts), NOISE_LINES[int(rng.integers(0, len(NOISE_LINES)))]))

    return Scenario(
        transfers=sorted(g.transfers, key=lambda t: t.ts),
        posts=sorted(posts, key=lambda p: p.ts),
        labels=labels,
        bytecodes={contract: code},
        truth=Truth(set(attacker), set(handles.values()), set(decoys), {"Exch-A", "Exch-B"}, utc_offset),
    )


def evaluate(predicted_wallets: set[str], predicted_handle: str | None, truth: Truth) -> dict:
    tp = len(predicted_wallets & truth.attacker_wallets)
    precision = tp / len(predicted_wallets) if predicted_wallets else 0.0
    recall = tp / len(truth.attacker_wallets) if truth.attacker_wallets else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1,
            "handle_correct": predicted_handle in truth.attacker_handles}
