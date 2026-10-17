"""Does the exploit contract on-chain contain the same functions as code someone posted on GitHub?
A function's 4-byte selector = first 4 bytes of keccak256("name(type1,type2)"); compiled contracts embed
each selector after a PUSH4 opcode, so selectors can be read from both source and bytecode."""
import re

from eth_hash.auto import keccak

PUSH1, PUSH4, PUSH32 = 0x60, 0x63, 0x7F
FUNC = re.compile(r"function\s+(\w+)\s*\(([^)]*)\)")
ALIASES = [(re.compile(r"\buint\b"), "uint256"), (re.compile(r"\bint\b"), "int256"), (re.compile(r"\bbyte\b"), "bytes1")]


def selectors_from_bytecode(code_hex: str) -> set[str]:
    try:
        code = bytes.fromhex(code_hex.removeprefix("0x"))
    except ValueError:
        return set()
    out, i = set(), 0
    while i < len(code):
        op = code[i]
        if PUSH1 <= op <= PUSH32:
            data = code[i + 1:i + 1 + op - PUSH1 + 1]
            if op == PUSH4 and len(data) == 4:
                out.add(data.hex())
            i += op - PUSH1 + 1          # skip the pushed data: it is not code
        i += 1
    return out


def _canonical_type(param: str) -> str:
    t = param.split()[0] if param.split() else ""
    for rx, full in ALIASES:
        t = rx.sub(full, t)
    return t


def selectors_from_source(solidity: str) -> set[str]:
    out = set()
    for name, params in FUNC.findall(solidity):
        types = ",".join(_canonical_type(p) for p in params.split(",") if p.strip())
        out.add(keccak(f"{name}({types})".encode()).hex()[:8])
    return out


def similarity(a: set[str], b: set[str]) -> float:
    """Jaccard overlap of two selector sets; 0.0 if either is empty."""
    return len(a & b) / len(a | b) if a and b else 0.0
