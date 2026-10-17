"""Who is the same person? Username look-alikes (leetspeak, reordered parts) + writing-style similarity."""
import itertools
import re

import numpy as np
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer

from gt.schema import OsintPost

LEET = str.maketrans({"0": "o", "1": "i", "l": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})
NAME_GATE = 0.5   # style may only merge two authors whose names at least resemble each other


def _variants(name: str) -> set[str]:
    """'Fox-Gh0st' -> {'foxghost', 'ghostfox'}: de-leet each part, then every ordering of the parts."""
    parts = [re.sub(r"[^a-z]", "", p.translate(LEET)) for p in re.split(r"[_\-.\s]+", name.lower())]
    parts = [p for p in parts if p][:4]
    return {"".join(p) for p in itertools.permutations(parts)} or {""}


def username_similarity(a: str, b: str) -> float:
    return max(fuzz.ratio(x, y) for x in _variants(a) for y in _variants(b)) / 100


def style_similarity(texts_a: list[str], texts_b: list[str]) -> float:
    """Cosine of the authors' mean character n-gram profiles (case kept: casing is part of style)."""
    if not texts_a or not texts_b:
        return 0.0
    try:
        X = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), lowercase=False).fit_transform(texts_a + texts_b)
    except ValueError:   # nothing but whitespace
        return 0.0
    a = np.asarray(X[:len(texts_a)].mean(axis=0)).ravel()
    b = np.asarray(X[len(texts_a):].mean(axis=0)).ravel()
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(a @ b / denom) if denom else 0.0


def resolve_identities(posts: list[OsintPost], name_thr: float = 0.8, style_thr: float = 0.6) -> dict[str, str]:
    """Map every 'source:author' to one canonical identity (alphabetically first member of its group).
    Merge when names match (≥ name_thr), or when style matches (≥ style_thr) and names resemble (≥ NAME_GATE).
    ponytail: O(n²) author pairs — fine for a few thousand authors; block by name prefix if it grows."""
    texts: dict[str, list[str]] = {}
    for p in posts:
        texts.setdefault(f"{p.source}:{p.author}", []).append(p.text)
    keys = sorted(texts)
    parent = {k: k for k in keys}

    def root(k: str) -> str:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for a, b in itertools.combinations(keys, 2):
        ns = username_similarity(a.split(":", 1)[1], b.split(":", 1)[1])
        if ns >= name_thr or (ns >= NAME_GATE and style_similarity(texts[a], texts[b]) >= style_thr):
            ra, rb = root(a), root(b)
            parent[max(ra, rb)] = min(ra, rb)
    return {k: root(k) for k in keys}
