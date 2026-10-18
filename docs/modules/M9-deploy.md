# M9: Deploy (Render + Vercel + MongoDB Atlas, all free)

## In one sentence
The engine runs on **Render** (free web service, from `render.yaml`), the website on **Vercel**, and the data in **MongoDB Atlas**. The four real hacks ship as recorded traces, so a fresh server loads them in seconds with no Etherscan calls.

```
 Browser ──HTTPS──► Vercel (website, frontend/)
                       │ VITE_API_URL
                       ▼
                    Render (FastAPI engine, render.yaml) ──► MongoDB Atlas (cases, alerts, audit chain)
                       │
                       └──► Etherscan · Alchemy · GitHub · RSS · Groq/Gemini · Discord/Telegram (free tiers)
```

## What was added for deployment

| File | Why |
|---|---|
| [render.yaml](../../render.yaml) | Render Blueprint for the engine: free plan, Singapore region, `pip install -r backend/requirements.txt`, `uvicorn gt.api:app --app-dir backend --host 0.0.0.0 --port $PORT`, health check `/api/health`. Every key is `sync: false`, so Render asks for it in its dashboard and nothing secret is in the repo. Only changes to `backend/`, `data/`, `render.yaml` or `.python-version` rebuild it. |
| [.python-version](../../.python-version) | Pins Python 3.11 (what the code is tested on); Render's default is 3.14 |
| [backend/requirements.txt](../../backend/requirements.txt) | Exact package versions that pass the 200 tests, so the server installs the same thing |
| [data/replays/snapshots/](../../data/replays/snapshots/) (about 780 KB) | The recorded trace of each stored hack (transfers, fully loaded wallets, third-party contracts). Render's free disk is wiped on every restart, and the Etherscan cache (≈1 GB) isn't in git. Without these files the first load of each hack on a fresh server took 1–10 minutes. Now it takes seconds and needs no Etherscan key. **Trace any address** still traces live. |
| [backend/gt/snapshot.py](../../backend/gt/snapshot.py) | Re-records them: `py -3.11 -m gt.snapshot` (from `backend/`) after changing a replay file or the trace logic |
| [frontend/vercel.json](../../frontend/vercel.json) (already there) | Sends every page to the app, so `/case` and `/report` work on refresh |

Checked before deploying:
- `render.yaml` validates against Render's published JSON schema.
- Peak memory loading KyberSwap, Euler and a simulation is about 220 MB, inside the free plan's 512 MB.
- A test loads Euler with no Etherscan key and gets $191.6M traced and $189.4M returned.

## Deploy, step by step

**0. Push.** Render and Vercel deploy from GitHub, so commit and push first.

**1. MongoDB Atlas: let Render connect.** Atlas → your project → **Network Access** → **Add IP Address** → **Allow access from anywhere** (`0.0.0.0/0`) → Confirm. Render's free plan has no fixed IP address. The database is still protected by its username and password.

**2. Render: the engine.**
1. Open https://dashboard.render.com/blueprint/new?repo=https://github.com/SaTyAbHr2005/Unmask and sign in with GitHub. Allow Render to read the repo if asked.
2. Render reads `render.yaml` and shows the service **unmask-api**. Fill in the values:
   - Copy each one from your own `backend/.env`.
   - Leave **FRONTEND_ORIGINS** empty for now; you'll set it in step 4.
   - Leave any service you don't use empty.
3. Click **Apply**. The first build takes about 5 minutes.
4. When it's **Live**, copy its address (like `https://unmask-api.onrender.com`). Opening `…/api/health` should show `{"ok":true,"db":"mongo"}`.

**3. Vercel: the website.**
1. https://vercel.com/new → **Import** the GitHub repo `SaTyAbHr2005/Unmask`.
2. **Root Directory:** `frontend`. **Framework Preset:** Vite (detected automatically).
3. **Environment Variables:** `VITE_API_URL` = your Render address + `/api` (e.g. `https://unmask-api.onrender.com/api`).
4. **Deploy**, then copy the site address (like `https://unmask-xyz.vercel.app`).

**4. Connect them (CORS).** Render → unmask-api → **Environment** → set `FRONTEND_ORIGINS` to the Vercel address (no trailing slash; comma-separate several, e.g. a custom domain too) → **Save, rebuild and deploy**. Until this is set, the browser blocks the website from calling the engine.

**5. Smoke test.** Open the Vercel site:
- the home page sky appears;
- the case file loads attack 7;
- **Real hack → Euler** loads in seconds with $191.6M;
- the dossier shows freeze letters.

## Before the demo
- **Wake the engine 2–3 minutes before presenting.** Render's free plan sleeps after 15 minutes without traffic, and waking takes about a minute. Open `https://<your-render-address>/api/health`, then the website.
- Load attack 7 so the case file isn't empty when you start.
- Keep a browser tab open on the case file. Its watch-status polling keeps the engine awake while you present.
- Have the local version ready as a backup (two terminals, see the judges guide); it doesn't depend on the internet except for live tracing.

## Limits
- **Cold start:** about a minute after 15 idle minutes (free plan). A paid plan or an uptime pinger removes it.
- **Watch mode** stops when the server sleeps or restarts (it lives in the server process).
- **One case at a time,** shared by everyone using the site; there's no login yet.
- **MongoDB Atlas M0** shares a small free cluster. If calls feel slow, setting `MONGODB_URI` to `mongomock://` keeps everything in memory (fast, but cases and the audit chain reset on restart).
