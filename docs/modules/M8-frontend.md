# M8: Frontend (the story, the case file, the dossier)

## In one sentence
M8 is the website: a **scroll-driven 3D story** that explains the problem (now at `/how-it-works`; the home page is the M8.2 landing page), a **case file** where an investigator works the case live, and a **printable dossier** with freeze letters, evidence and the audit record.

## Design concept: "Latent"
In forensics, a **latent print** is a fingerprint that is invisible until it is *developed* with powder or reagents. That is exactly what Unmask does to a hacker, so the whole site is built on it: the story opens in the dark ("2:14 AM, nothing visible") and, as you scroll, the evidence *develops* into daylight and a name.

**Palette.** Each colour is a real forensic material, and each means one thing everywhere:

| Name | Hex | Meaning |
|---|---|---|
| Soot | `#2A2630` | black fingerprint powder: night, before anything is developed |
| Lift | `#ECEDE6` | lift card / lab bench: the working surface |
| Graphite | `#34322F` | ink |
| Ninhydrin | `#8E2F78` | the reagent that turns prints purple: **the attacker / evidence** |
| Iodine | `#B9801F` | iodine fuming turns prints amber: **money** |
| Ammonium | `#3E7A6A` | **can still be frozen** |
| Seal red | `#C2362B` | **act now** (only on urgent alerts and predicted cash-outs) |

**Type:**
- **Big Shoulders Display** (condensed, like stencilled case numbers) for clocks and amounts
- **Schibsted Grotesk** (made for a news publisher) for prose
- **Martian Mono** only for real machine strings: addresses and hashes

**What it avoids on purpose:** dark backgrounds with one neon accent, bluish dark themes, cream + serif + terracotta, identical rounded cards, ALL-CAPS labels and "→" buttons.

## Pages

### 1. The story (`/how-it-works`; it was the home page until M8.2), [src/story/](../../frontend/src/story)
Seven chapters that follow the problem statement, driven by scroll:

| Chapter | On screen | The 3D field |
|---|---|---|
| 02:14 | A giant stencil clock ticks over; "$42 million has just left their contracts" | A **latent fingerprint** of 15,000 particles, invisible until your cursor "dusts" it (on phones the light rests on it) |
| $42,000,000 | A counter climbs from 1 to **300 wallets** as you scroll | The print **bursts into 300 amber wallet clusters** |
| Into the mixer | Why the paper trail breaks, and why the gas trail doesn't | The clusters **funnel into a spinning vortex** |
| Over the bridge | Funds leave Ethereum and reappear on Arbitrum | **Two tilted planes** (two chains) with an arc of money crossing |
| Two rooms, two languages | Forum posts on the left, transactions on the right; amber threads draw themselves between matching times | Dims into the background |
| Every ghost leaves a print | Night turns to day; **"ghostfox" decrypts into view**; the five clues with their strengths | The particles **re-form the print, developed in ninhydrin purple** |
| $31.8M can still be frozen | Freezable / not-freezable bar, the freeze window (5.5 h warning, 20.1 h to cash-out, ~11 h to the next wave) and the button into the case file | Fades to a watermark |

**How it's built:**
- [LatentField.tsx](../../frontend/src/story/LatentField.tsx): one Three.js `Points` object (React Three Fiber) with a **custom shader**. Each particle carries all five positions, and the shader blends between them, so scrolling never re-renders React.
- [shapes.ts](../../frontend/src/story/shapes.ts): the five point layouts (whorl fingerprint with ridge breaks, 300 wallets, vortex, two-chain bridge), generated deterministically.
- **GSAP ScrollTrigger** maps each chapter to a shape, the counter, the threads and the night-to-day colour change. **Lenis** gives smooth scrolling on the same clock.
- **React Bits' DecryptedText** reveals the name.

### 2. The case file (`/case`), [src/console/](../../frontend/src/console)

| Panel | What you see and do |
|---|---|
| **Engine bar** | Load a simulated attack (any number), collect public posts (RSS + GitHub), run the analysis again. The **Thinking Orb** (halftone engraving style) shows what the engine is doing: idle, working, searching or reasoning. |
| **3D money flow** ([FlowGraph3D.tsx](../../frontend/src/console/FlowGraph3D.tsx)) | The attacker's wallets (purple) around mixer/bridge hubs and exchange exits (green), with **amber particles moving along the money edges**. Drag to turn; zoom with Ctrl + scroll (or a touchpad pinch) or the **+ / −** buttons; **Re-centre** brings the whole cluster back. Click a wallet to open it. |
| **Money now** | Stolen, **can still be frozen**, at exchanges, freezable by the issuer, nobody can freeze, still in the mixer; the freeze window; exits marked arrived or "in ~10.8 h" |
| **Suspects** | Each identity with a confidence bar and label; the top name decrypts; open one for the plain-English reasons and clue strengths; **Confirm** / **Reject** (written to the audit chain); optional plain-language AI summaries |
| **Alerts** | Pending alerts on raised cards; **Approve and send** asks for a second confirmation ("Send now" / "Keep waiting"); Dismiss |
| **Posts against transactions** | Purple post dots above amber transaction ticks; a curve joins each post to the attacker transaction that followed within 15 minutes; point at a post to read it (personal details masked) |
| **Waking hours** | A 24-hour clock: outer ring = when the wallets act, inner ring = when the suspect posts; the inferred time zone in the middle, with its waking window drawn as an arc |
| **Where the money went** | Stolen funds → Mixer / Bridge / DEX swap → each exchange / held and freezable / held and not freezable |
| **The ledger as a matrix** | The busiest attacker wallets × every hour (quiet hours included); click a row to open the wallet |
| **Deposits, piece by piece** | Each exchange deposit and how many laundered pieces it's exactly made of |
| **Wallet drawer** | Bot-likeness, behaviour in plain words ("gas price varies by 0.00 gwei"), holdings and who can freeze them, deposit composition, latest transfers |

### 3. The dossier (`/report`), [src/report/](../../frontend/src/report)
- Headline facts: stolen, freezable, warning lead time, time to first cash-out
- **Who is behind the wallets:** every suspect with the full reasoning and evidence hashes
- **Personal details:** emails and IPs found in posts are **masked**. Showing them needs a written reason, which is **recorded in the audit chain** (`POST /api/privacy/reveal`). "Mask them again" hides them.
- **Freeze requests:** one letter per party that can freeze funds (each exchange, Tether…), with **Copy letter**
- Deposits reconstructed, exits and holdings
- **Record of decisions:** whether the audit chain checks out, the **newest entry ID** to keep with the printout, and the evidence count
- **Download as PDF:** records the export in the audit chain, then opens the print dialog (print styles hide the controls)

## Libraries

| Library | Used for |
|---|---|
| three + @react-three/fiber | The story's particle field and shader |
| react-force-graph-3d | The 3D money-flow graph with moving particles |
| gsap (ScrollTrigger) | Scroll-driven morphs, counter, threads, night-to-day transition, opening sequence |
| lenis | Smooth scrolling synced with GSAP |
| d3 + d3-sankey | Timeline, clock rings, route diagram |
| @yogesharc/thinking-orbs | Engine status orb ([thinkingorbs.com](https://thinkingorbs.com), MIT) |
| React Bits DecryptedText (+ motion) | The name reveal ([DavidHDev/react-bits](https://github.com/DavidHDev/react-bits), MIT + Commons Clause: used inside the app, not redistributed) |
| react-router-dom | The three pages, each loaded lazily |

The 3D graph library loads only on the case file; the story's 3D code only on the story.

## Problems found while verifying in the browser (fixed)

| Problem | Fix |
|---|---|
| Story particles rendered as one giant blur (point size about 100× too large) | Rescaled point size to about 2 px at 900 px screen height (larger on phones) |
| The fingerprint read as a cloud | Less drift while it's a print, finer jitter, 15,000 particles on desktop |
| The developed print ended up edge-on | Rotation now returns to face-on for the reveal |
| The nav overlapped chapter headings | The nav fades into the page colour, night and day |
| 3D graph: the layout never ran, then the camera sat inside the cluster | The layout is now computed up front (static, cheaper), and the camera is framed on the **drawn** node meshes. The library's own "zoom to fit" reads a copy of the positions that never gets the layout. |
| React StrictMode broke the graph's camera in development | StrictMode removed (it only affects development builds) |
| Scrolling over the graph zoomed it instead of the page | Plain wheel scrolls the page; Ctrl/⌘ + wheel zooms |
| Ctrl + scroll barely zoomed (~3% per notch, then a long glide) | The wheel is handled by Unmask, not the trackball: ~15% per mouse notch, smooth for touchpad pinch, and the browser's page zoom is blocked over the graph |
| The graph could end up empty: a right-drag panned the cluster away, or a new case was framed before its layout existed | Pan is off; the camera is fitted when the layout finishes (not on a timer); **+ / − / Re-centre** buttons |
| The timeline was squashed by one post from 3 days earlier | The axis follows the attacker's activity ±2 h and mentions posts outside it |
| The matrix skipped quiet hours, so time looked continuous when it wasn't | The API fills empty hours; a test guards it |
| The route diagram showed a $0 "Direct" route and clipped labels | Crumb routes (< 0.1% of the theft) are dropped (tested); more label room |
| The clock clipped its 06:00 / 18:00 labels | Larger canvas |
| Dust showed as "0 ETH" | Shown as "<0.001 ETH" |
| On phones the case file overflowed and the print was invisible | Grid columns may shrink; bigger, brighter particles on phones |
| Shared styles were missing when the dossier opened directly | Moved to the global stylesheet |

## Accessibility and quality floor
- Every page works with the keyboard and has a visible focus ring (ninhydrin outline).
- `prefers-reduced-motion`: no smooth scrolling, no opening animation, no bar fills; morphs jump instead of easing.
- Charts have text alternatives (`role="img"` + `aria-label`, `<title>` per segment). The engine status is announced (`role="status"`), and so are errors (`role="alert"`).
- The wallet drawer closes with Esc and moves focus to its Close button.
- Checked at 1440×900 and 375×812.

## How to run
Two terminals, from `HackForge`. The API:

```bash
py -3.11 -m uvicorn gt.api:app --app-dir backend --port 8000
```

The website (first time: `npm install --prefix frontend`):

```bash
npm --prefix frontend run dev
```

Open **http://localhost:5173**. The case file has a "Load simulated attack" button, so no keys are needed.

Production build:

```bash
npm --prefix frontend run build
```

The frontend reads the API address from `VITE_API_URL` (default `http://localhost:8000/api`); set it on Vercel when deploying (M9). `frontend/vercel.json` already routes every page to the app.

## Limitations
- The 3D money graph is drawn with a static layout (dragging nodes is off). Turning and zooming the camera still work.
- The story's numbers are fixed values from the simulated attack (seed 7); the case file is the live engine.
- No login: the analyst's name for the audit record is typed in the dossier.
- There are no automated browser tests; verification was done by hand in the browser at desktop and phone sizes.
