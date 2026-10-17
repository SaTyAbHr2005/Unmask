"""Shared data contract between every module. Change a field here = tell the team."""
from dataclasses import dataclass, field


@dataclass
class Transfer:
    tx_hash: str          # unique per row; token transfers use f"{hash}:{logIndex}"
    chain: str            # "eth" | "arb" | "sim"
    ts: int               # unix UTC seconds
    from_addr: str        # lowercase
    to_addr: str          # lowercase
    asset: str            # "ETH" | "USDT" | "USDC" | other symbol
    amount: float
    gas_price_gwei: float = 0.0
    nonce: int = -1
    input_data: str = "0x"
    kind: str = "transfer"  # transfer|swap|mixer_in|mixer_out|bridge_out|bridge_in|deploy|test_call


@dataclass
class OsintPost:
    post_id: str
    source: str           # "github" | "telegram" | "rss" | "forum" | "sim"
    author: str
    ts: int
    text: str
    url: str = ""


@dataclass
class Entity:
    entity_id: str        # sha1(post_id|kind|value)[:16]
    post_id: str
    kind: str             # "address" | "tx" | "ip" | "email" | "handle" | "ens"
    value: str


@dataclass
class Signal:
    name: str             # "time_delta" | "rhythm" | "address_mention" | "bytecode" | "onchain_message"
    lr: float             # likelihood ratio
    detail: str


@dataclass
class Link:
    link_id: str          # f"{cluster_id}:{identity}"
    cluster_id: int
    identity: str
    score: float          # posterior 0..1 after decay
    signals: list[Signal] = field(default_factory=list)
    status: str = "suspected"   # suspected | confirmed | rejected
    evidence: list[str] = field(default_factory=list)
    updated_ts: int = 0


@dataclass
class Alert:
    alert_id: str
    kind: str             # "exit" | "prewarn" | "freeze" | "decoy"
    target: str
    message: str
    status: str = "pending"     # pending | approved | sent | dismissed
    created_ts: int = 0


@dataclass
class Evidence:
    hash: str             # sha256 hex of the canonical JSON payload
    kind: str             # "transfer" | "post" | "signal" | …
    source_url: str
    captured_ts: int
    payload: str          # canonical JSON (sorted keys)


@dataclass
class AuditEntry:
    entry_id: str         # sha256(prev_hash|actor|action|target|ts)[:16]
    ts: int
    actor: str
    action: str           # "confirm_link" | "reject_link" | "approve_alert" | "send_alert" | "dismiss_alert" | "export_report" | "reveal_pii"
    target: str
    prev_hash: str        # entry_id of the previous entry ("" for the first) — tamper-evident chain


ALL = [Transfer, OsintPost, Entity, Link, Alert, Evidence, AuditEntry]
