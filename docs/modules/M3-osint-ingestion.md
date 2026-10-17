# M3: OSINT Ingestion (collecting what people say in public)

## In one sentence
M3 **collects public text** (hack reports, forum and Telegram posts, GitHub code), **pulls out identity clues** (wallet addresses, handles, emails, IPs, ENS names), and **works out which online accounts are really the same person**.

## Why it exists
Blockchain data shows *what* moved, but never *who* moved it. People leave traces in public: a hacker brags on a forum, tests exploit code on GitHub, or uses the same nickname with a "0" instead of an "o" on Telegram. M3 turns that messy text into clean, timestamped records the math layer (M4/M5) can line up against blockchain transactions.

## Where it sits

```
 RSS feeds ─┐
 GitHub    ─┼─► collectors.py ─► OsintPost (clean, UTC time) ─► extract.py ─► Entities (addresses, handles…)
 Telegram  ─┘                          │
                                       └─► style.py ─► "these 3 accounts are one person" ─► Fusion (M5)
```

## Files

| File | What it does | Features |
|---|---|---|
| [extract.py](../../backend/gt/osint/extract.py) | Builds clean posts and finds identity clues in text | #3, #4 |
| [collectors.py](../../backend/gt/osint/collectors.py) | Pulls posts from RSS, GitHub and Telegram | #1, #2 |
| [style.py](../../backend/gt/osint/style.py) | Username look-alikes plus writing-style comparison, merging accounts into identities | #5, #6 |
| [llm.py](../../backend/gt/llm.py) | Optional AI text polish (Groq, then Gemini); returns nothing when no key is set | (used by M5/M7) |
| [config.py](../../backend/gt/config.py) | `RSS_FEEDS`, `GITHUB_QUERIES`, `TELEGRAM_CHANNELS` | — |

---

## 1. `extract.py`: clean posts and identity clues

### `make_post(source, author, ts_raw, text, url="")`
Turns raw input into an `OsintPost`:
- The time can be in any format (ISO, RFC-822 like `Fri, 17 Oct 2026 02:14:00 GMT`, unix seconds). It is converted to **UTC seconds** using M2's `to_utc`.
- **A post with no readable time is dropped (returns `None`).** Without a time, it can't be matched against transactions, and storing 0 would mean 1970.
- `post_id` is a hash of source, author, time and text, so the same post collected twice is stored once.

### `extract(post)` → list of `Entity`
Finds these clues with regular expressions:

| Kind | Looks like | Notes |
|---|---|---|
| `tx` | `0x` + 64 hex | Checked carefully so a tx hash never also counts as an address |
| `address` | `0x` + 40 hex | Lowercased, matching wallets in the blockchain data |
| `email` | `name@domain.io` | The `@domain` part is **not** also counted as a handle |
| `handle` | `@ghostfox` | Lowercased |
| `ens` | `vitalik.eth` | Ethereum Name Service names point to wallets |
| `ip` | `10.0.0.5` | Validated: `999.1.2.3` is rejected |

All values are lowercased, duplicates in a post collapse to one, and every entity gets a stable id. A post with no clues returns an empty list.

**Why it matters:** if a forum post mentions an address that belongs to the hacker's wallet cluster, that's very strong evidence (M5 gives it a likelihood ratio of 30).

## 2. `collectors.py`: getting the text
Every collector **returns whatever it managed to collect and never crashes** on network or API trouble.

### `collect_rss(urls)`
Reads security news feeds. These five were **checked live on 2026-10-17** and all return fresh posts:

| Feed | Why |
|---|---|
| Rekt News | Detailed DeFi hack post-mortems |
| Web3 Is Going Great | Running log of crypto incidents |
| Cointelegraph, "hacks" tag | News on exploits |
| SlowMist (Medium) | Security firm incident analyses |
| Chainalysis blog | On-chain investigations |

Each entry becomes a post: author = feed title, text = title + summary, time = published (or updated) date. Entries with no date are dropped, and a broken feed is skipped.

**Live test result:** 77 posts with 16 identity clues, including real wallet addresses from hack reports.

### `collect_github(queries)`
Two GitHub searches per query:
1. **Commit search** works **without a token**, at a lower rate limit. Text = commit message, author = GitHub login, time = commit date.
2. **Code search** works **only with `GITHUB_TOKEN`** (GitHub requires it). Text = the matching code fragment, author = repo owner, time = the repo's last push. It's capped at 10 hits per query, because each hit costs one extra call.

If GitHub answers 403/429 (rate limit) or 401, it **stops and keeps what it already has**.

**Live test result (no token):** 29 commits for "flashloan exploit".

### `collect_telegram(channels, limit=200)`
Reads **public** channels only, using `telethon`. Returns an empty list when:
- `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` aren't set, or
- `telethon` isn't installed (it's optional and **not installed** right now), or
- no channels are given (`TELEGRAM_CHANNELS` in config starts empty; fill it per case).

The first real run asks for a phone login in the terminal once; the session is saved as `data/telegram.session` (gitignored).

## 3. `style.py`: which accounts are the same person?

### `username_similarity(a, b)` → 0 to 1
1. Lowercase, split on `_ - .` and spaces.
2. **Un-leet** each part: 0→o, 1/l→i, 3→e, 4→a, 5→s, 7→t, @→a, $→s.
3. Try **every ordering** of the parts, so `fox_ghost` also reads as `ghostfox`.
4. Take the best fuzzy-match score (rapidfuzz).

Examples: `ghostfox` vs `gh0st_fox` = 1.0; `ghostfox` vs `fox_ghost` = 1.0; `ghostfox` vs `alice` < 0.5.

### `style_similarity(texts_a, texts_b)` → 0 to 1
Writing style fingerprint. Each author's posts are broken into 2- to 4-character chunks (TF-IDF character n-grams, **case kept**, since lowercase-everything is itself a habit). The two average profiles are compared with cosine similarity. Slang writers ("lol ur … fr") score high with each other and low against formal writers.

### `resolve_identities(posts)` → `{"source:author": canonical identity}`
Compares every pair of accounts and merges them (union-find) when:
- **names match** (≥ 0.8), **or**
- **style matches (≥ 0.6) and names at least resemble each other (≥ 0.5)**

The canonical identity is the alphabetically first account in the group, for example `forum:ghostfox`.

**Why style alone can't merge accounts:** posts are short, and many people use the same phrases, so style by itself produces false matches. In testing, a style-only rule merged all 60 normal users into one "person". Requiring some name resemblance stops that and still catches the hacker's aliases.

**Simulator result:** 63 accounts become 61 identities. The **only** merge is `forum:ghostfox` + `github:gh0stfox` + `telegram:fox_ghost` → one person, which is correct.

## 4. `llm.py`: optional AI polish
`complete(prompt)` tries **Groq** first, then **Gemini** (both free tiers), and returns `None` if neither is set or both fail. It **never raises**. Later modules use it only to polish wording (explanations, freeze-request letters); every feature has a plain template fallback, so the app works fully without AI. The Gemini key is sent in a header, never in the URL, so it can't leak into logs.

## Keys (all optional)

| Key | Unlocks | Without it |
|---|---|---|
| `GITHUB_TOKEN` | GitHub code search + higher rate limit | Commit search still works |
| `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` | Telegram channels (also needs `py -3.11 -m pip install telethon`) | Telegram skipped |
| `GROQ_API_KEY` / `GEMINI_API_KEY` | AI polish | Template text is used |
| `GROQ_MODEL` / `GEMINI_MODEL` | Change the model if the default is retired | Defaults: `llama-3.3-70b-versatile`, `gemini-2.0-flash` |

## How to test
From `HackForge`:

```bash
py -3.11 -m pytest backend/tests/test_extract.py backend/tests/test_collectors.py backend/tests/test_style.py -q
```

25 tests, all offline (fake HTTP and fake feeds). They cover every entity kind; tx vs address; email vs handle; invalid IPs; duplicates; undated posts dropped; time zones; broken feeds skipped; GitHub 403, rate-limit stop, no-token behavior, network errors; Telegram without keys; AI fallback chain; leetspeak and reordered names; style ordering; style-alone not merging; the attacker's three handles merging; normal users staying separate.

Try the real collectors (no keys needed), from `backend/`:

```bash
py -3.11 -c "from gt.config import RSS_FEEDS; from gt.osint.collectors import collect_rss; print(len(collect_rss(RSS_FEEDS)))"
```

## Limitations
- X/Twitter, Pastebin and dark-web sources are **not** collected: no free API, and scraping them breaks their terms.
- Telegram needs `telethon` installed and a one-time phone login.
- Comparing every pair of accounts is fine for thousands of accounts, but would need grouping by name prefix beyond that.
- An alias with a **completely different name** but the same writing style won't be merged (the safety rule above).
- The simulator's normal users now get clearly distinct syllable usernames (like real strangers). Before this, word-pair names could genuinely collide.

## What later modules use from M3
- **M4 time-delta test:** post timestamps per identity
- **M5 fusion:** `resolve_identities` (who is one person), `extract` (address mentions → strong signal), `llm.complete` (explanation polish)
- **M4 bytecode similarity:** code text from GitHub posts
- **M7 API:** collectors behind the OSINT refresh endpoint
