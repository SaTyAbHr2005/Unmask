// Typed client for the Unmask API (backend/gt/api.py). Shapes mirror the backend dataclasses.
export const BASE: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";

export type Kind = "attacker" | "exchange" | "mixer" | "bridge" | "dex" | "victim" | "decoy" | "contract" | "wallet";

export interface Signal { name: string; lr: number; detail: string }
export interface Link {
  link_id: string; cluster_id: number; identity: string; score: number; signals: Signal[];
  status: "suspected" | "confirmed" | "rejected"; evidence: string[]; updated_ts: number;
  label: "high" | "medium" | "low" | "confirmed" | "rejected"; explanation: string;
}
export interface Alert {
  alert_id: string; kind: "exit" | "prewarn" | "freeze" | "decoy"; target: string; message: string;
  status: "pending" | "approved" | "sent" | "dismissed"; created_ts: number;
}
export interface Exit { exchange: string; address: string; share: number; usd: number; eta_s: number | null; arrived: boolean }
export interface Holding { address: string; asset: string; amount: number; usd: number; freezable: boolean; freezer: string }
export interface Timing {
  theft_ts?: number | null; first_cashout_ts?: number | null; time_to_first_cashout_s?: number | null;
  prewarn_ts?: number | null; prewarn_lead_s?: number | null; next_predicted_exit_s?: number | null; case_now_ts?: number;
}
export interface MoneyNow {
  total_usd: number; frozen_possible_usd: number; at_exchanges_usd: number; in_mixers_usd: number;
  unspent_usd: number; returned_usd?: number; exits: Exit[]; timing: Timing; eth_usd?: number;
}
export interface GraphNode { id: string; label: string; cluster: number | null; kind: Kind; usd: number; bot_score: number | null }
export interface GraphEdge { source: string; target: string; kind: string; usd: number; ts: number }
export interface Graph { nodes: GraphNode[]; edges: GraphEdge[] }
export interface WatchStatus {
  on: boolean; source?: "simulated" | "blockchain"; watching: number; started_ts: number; stops_ts: number;
  checks: number; new_transfers: number; reruns: number; last_check_ts: number | null; last_posts_ts: number | null;
  posts_found: number; error: string | null;
  recent: { ts: number; from: string; to: string; asset: string; amount: number; to_label: string }[];
}
export type TimelineEvent =
  | { ts: number; type: "tx"; who: string; usd: number; kind: string; cluster: number }
  | { ts: number; type: "post"; who: string; text: string; url: string };
export interface Heatmap { hours: number[]; utc_offset: number | null; confidence: number | null }
export interface Sankey { nodes: { name: string }[]; links: { source: number; target: number; value: number }[] }
export interface Matrix { wallets: string[]; buckets: number[]; counts: number[][] }
export interface Deposit {
  deposit_tx: string; wallet: string; exchange: string; asset: string; amount: number; usd: number;
  pieces: string[]; n_pieces: number; method: string; ts: number;
}
export interface Metrics { precision: number; recall: number; f1: number; handle_correct: boolean }
export interface Report {
  case: string; generated_ts: number; stolen_usd: number; metrics: Metrics | null; links: Link[]; exits: Exit[];
  holdings: Holding[]; timing: Timing; deposits: Deposit[]; freeze_requests: { to: string; text: string }[];
  audit_ok: boolean; audit_head: string; audit_entries: number; evidence_count: number;
}
export interface Wallet {
  address: string; label: string; cluster: number | null; kind: Kind; features: Record<string, number | null>;
  bot_score: number | null; utc_offset: number | null; holdings: Holding[]; deposits: Deposit[];
  transfers: { tx_hash: string; ts: number; from_addr: string; to_addr: string; asset: string; amount: number; kind: string; usd: number }[];
}

const ANALYST_KEY = "unmask.analyst";
export const analyst = {
  get: () => { try { return localStorage.getItem(ANALYST_KEY) || "analyst"; } catch { return "analyst"; } },
  set: (name: string) => { try { localStorage.setItem(ANALYST_KEY, name); } catch { /* private mode */ } },
};

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try {
    r = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", "X-Analyst": analyst.get(), ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, `Can't reach the Unmask API at ${BASE}. Start it with: py -3.11 -m uvicorn gt.api:app --app-dir backend --port 8000`);
  }
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new ApiError(r.status, typeof body.detail === "string" ? body.detail : `Request failed (${r.status})`);
  }
  return r.json() as Promise<T>;
}

const post = <T>(path: string, body?: unknown) => call<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });

export const api = {
  health: () => call<{ ok: boolean; db: string }>("/health"),
  simulate: (seed = 7) => post<{ transfers: number; posts: number }>(`/simulate?seed=${seed}`),
  replays: () => call<{ id: string; name: string; source: string }[]>("/replays"),
  replay: (id: string) => post<{ transfers: number; posts: number }>(`/replay/${encodeURIComponent(id)}`),
  investigate: (body: { addresses: string[]; start: string; end: string; chain: number; hops: number }) =>
    post<{ transfers: number; posts: number }>("/investigate", body),
  run: () => post<{ metrics: Metrics | null; links: number; alerts: number }>("/run"),
  collectOsint: () => post<{ rss: number; github: number; telegram: number; entities: number; total_posts: number }>("/osint/collect", {}),
  graph: (limit = 400) => call<Graph>(`/graph?cluster=0&limit=${limit}`),
  timeline: () => call<TimelineEvent[]>("/timeline"),
  heatmap: (key: string) => call<Heatmap>(`/heatmap/${encodeURIComponent(key).replace(/%3A/g, ":")}`),
  sankey: () => call<Sankey>("/sankey"),
  matrix: (top = 24) => call<Matrix>(`/matrix?top=${top}`),
  moneyNow: () => call<MoneyNow>("/money-now"),
  links: (polish = false) => call<Link[]>(`/links${polish ? "?polish=true" : ""}`),
  decide: (id: string, action: "confirm" | "reject") => post<Link>(`/links/${encodeURIComponent(id)}/${action}`),
  alerts: () => call<Alert[]>("/alerts"),
  approve: (id: string) => post<Alert>(`/alerts/${encodeURIComponent(id)}/approve`),
  dismiss: (id: string) => post<Alert>(`/alerts/${encodeURIComponent(id)}/dismiss`),
  wallet: (addr: string) => call<Wallet>(`/wallet/${addr}`),
  liveStart: () => post<WatchStatus>("/live/start"),
  liveStop: () => post<WatchStatus>("/live/stop"),
  liveStatus: () => call<WatchStatus>("/live/status"),
  mempool: () => call<{ available: boolean; pending: number; watching: number }>("/mempool"),
  report: (polish = false) => call<Report>(`/report${polish ? "?polish=true" : ""}`),
  exportReport: () => post<Report>("/report/export"),
  reveal: (reason: string) => post<{ revealed: boolean }>("/privacy/reveal", { reason }),
};
