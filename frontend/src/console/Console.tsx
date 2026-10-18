import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { Link as RouterLink, useSearchParams } from "react-router-dom";
import { Orb } from "@yogesharc/thinking-orbs";
import { halftone } from "@yogesharc/thinking-orbs/renders";
import { api, type Link } from "../api";
import { pct, short, usd } from "../lib/format";
import ActivityMatrix from "./ActivityMatrix";
import AlertQueue from "./AlertQueue";
import ClockRings from "./ClockRings";
import MoneyLedger from "./MoneyLedger";
import RouteSankey from "./RouteSankey";
import Suspects from "./Suspects";
import Timeline from "./Timeline";
import LiveWatch from "./LiveWatch";
import { useCase, type Engine } from "./useCase";
import WalletDrawer from "./WalletDrawer";
import "./console.css";

const FlowGraph3D = lazy(() => import("./FlowGraph3D"));

const ENGINE: Record<Engine, { orb: "idle" | "working" | "searching" | "reasoning"; text: string }> = {
  idle: { orb: "idle", text: "Ready" },
  loading: { orb: "working", text: "Loading the case" },
  searching: { orb: "searching", text: "Reading public sources" },
  reasoning: { orb: "reasoning", text: "Analysing wallets and people" },
};

export default function Console() {
  const c = useCase();
  const [seed, setSeed] = useState(7);
  const [picked, setPicked] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [polished, setPolished] = useState<Link[] | null>(null);
  const [mempool, setMempool] = useState<{ available: boolean; pending: number } | null>(null);
  const [replays, setReplays] = useState<{ id: string; name: string; source: string }[]>([]);
  const [replay, setReplay] = useState("");

  // the landing page links here with ?hack=<replay> (load it) or ?trace=1 (open the address form)
  const [params, setParams] = useSearchParams();
  const asked = params.get("hack");
  useEffect(() => {
    api.replays().then((r) => { setReplays(r); setReplay((cur) => cur || (r.some((x) => x.id === asked) ? asked! : r[0]?.id) || ""); })
      .catch(() => setReplays([]));
  }, [asked]);
  useEffect(() => {
    if (!asked || !replays.some((r) => r.id === asked)) return;
    setParams({}, { replace: true });
    c.loadReplay(asked);
  }, [asked, replays]); // eslint-disable-line react-hooks/exhaustive-deps

  // charts refetch whenever the case data changes
  useEffect(() => { if (c.data) { setVersion((v) => v + 1); setPolished(null); } }, [c.data]);
  useEffect(() => { if (c.data) api.mempool().then(setMempool).catch(() => setMempool(null)); }, [c.data]);
  const pick = useCallback((id: string) => setPicked(id), []);
  const busy = c.engine !== "idle";
  const d = c.data;
  const top = d?.links[0];

  return (
    <main className="console" aria-busy={busy}>
      <header className="case-head">
        <div className="case-title">
          <h1>{d?.report.case || "No case loaded"}</h1>
          {c.metrics && (
            <p className="muted">
              Against the simulator's answer key: {pct(c.metrics.precision)} of flagged wallets are the attacker's, {pct(c.metrics.recall)} of the attacker's wallets found
              {c.metrics.handle_correct ? ", right person named." : ", wrong person named."}
            </p>
          )}
        </div>
        <div className="engine">
          <span className="engine-state" role="status">
            <Orb state={ENGINE[c.engine].orb} render={halftone} size={30} label={ENGINE[c.engine].text} className={`orb orb-${c.engine}`} />
            {ENGINE[c.engine].text}
          </span>
          <div className="engine-actions">
            <label className="seed">
              Attack
              <input type="number" min={0} max={999999} value={seed} onChange={(e) => setSeed(Number(e.target.value) || 0)} aria-label="Simulated attack number" />
            </label>
            <button className="btn btn-primary" disabled={busy} onClick={() => c.loadSimulation(seed)}>Load simulated attack</button>
            {replays.length > 0 && (
              <>
                <label className="seed">
                  Real hack
                  <select value={replay} onChange={(e) => setReplay(e.target.value)} aria-label="Real past hack">
                    {replays.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                  </select>
                </label>
                <button className="btn" disabled={busy || !replay} onClick={() => c.loadReplay(replay)}>Load real hack</button>
              </>
            )}
            <button className="btn" disabled={busy || !d} onClick={c.collectOsint}>Collect public posts</button>
            <button className="btn" disabled={busy || !d} onClick={c.rerun}>Run analysis again</button>
          </div>
        </div>
      </header>

      <details className="trace-form" open={params.get("trace") === "1" || undefined}>
        <summary>Trace any address</summary>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            const addresses = String(f.get("addresses")).split(/[\s,]+/).filter(Boolean);
            c.investigate({ addresses, start: String(f.get("start")), end: String(f.get("end")),
                            chain: Number(f.get("chain")), hops: Number(f.get("hops")) });
          }}
        >
          <p className="muted">
            Paste the attacker's address from any public post-mortem, pick the dates around the hack, and Unmask traces the
            money live from the blockchain. Up to 5 addresses and 120 days.
          </p>
          <label className="wide">
            Attacker address(es)
            <textarea name="addresses" required rows={2} spellCheck={false} placeholder="0x… (one per line)" />
          </label>
          <label>From <input type="date" name="start" required /></label>
          <label>To <input type="date" name="end" required /></label>
          <label>
            Chain
            <select name="chain" defaultValue="1">
              {/* the chains Etherscan's free plan covers (Optimism, Base and BNB Chain need a paid key) */}
              <option value="1">Ethereum</option>
              <option value="42161">Arbitrum</option>
              <option value="137">Polygon</option>
            </select>
          </label>
          <label>
            Follow the money
            <select name="hops" defaultValue="2">
              <option value="1">1 hop</option>
              <option value="2">2 hops</option>
              <option value="3">3 hops (slower)</option>
            </select>
          </label>
          <button className="btn btn-primary" disabled={busy}>Trace</button>
        </form>
      </details>

      {c.note && <p className="note" aria-live="polite">{c.note}</p>}
      {c.error && <p className="error" role="alert">{c.error}</p>}

      {!d ? (
        <section className="empty-case">
          <h2>Nothing developed yet.</h2>
          <p>
            Load the simulated attack to watch Unmask work end to end: millions split over hundreds of wallets, a mixer,
            a bridge, decoys, and an attacker who can't stop posting. Attack 7 is the one from the story; every other
            number is a different attacker, with its own name, amount and time zone. It takes a few seconds.
          </p>
          <button className="btn btn-primary" disabled={busy} onClick={() => c.loadSimulation(seed)}>Load simulated attack</button>
          {replays.length > 0 && (
            <p>
              Or trace a real one: pick a past hack under <b>Real hack</b> above. Its transactions come straight from the
              blockchain, with no answer key and no names attached.
            </p>
          )}
        </section>
      ) : (
        <>
          <LiveWatch onRerun={c.refresh} caseName={d.report.case} />

          <section className="bench" aria-label="Money flow">
            <div className="bench-graph">
              <Suspense fallback={<div className="graph3d" />}>
                <FlowGraph3D graph={d.graph} onPick={pick} />
              </Suspense>
              {top && (
                <p className="bench-caption">
                  {d.graph.nodes.filter((n) => n.kind === "attacker").length} attacker wallets shown.
                  Most likely behind them: <b className="mono">{top.identity.split(":").slice(1).join(":")}</b> ({pct(top.score)}).
                  {mempool && (mempool.available
                    ? ` ${mempool.pending} of their transactions are waiting to be confirmed right now.`
                    : " Live pending-transaction watch needs an Alchemy key.")}
                </p>
              )}
            </div>
            <MoneyLedger money={d.money} />
          </section>

          <div className="pair">
            <Suspects
              links={polished ?? d.links}
              polished={!!polished}
              onPolish={() => api.links(true).then(setPolished).catch(() => setPolished(null))}
              onDecide={(id, action) => c.act(() => api.decide(id, action))}
            />
            <AlertQueue
              alerts={d.alerts}
              onApprove={(id) => c.act(() => api.approve(id))}
              onDismiss={(id) => c.act(() => api.dismiss(id))}
            />
          </div>

          <Timeline version={version} />

          <div className="pair pair-even">
            <ClockRings identity={top?.identity ?? null} version={version} />
            <RouteSankey version={version} />
          </div>

          <ActivityMatrix version={version} onPick={pick} />

          {d.report.deposits.length > 0 && (
            <section className="panel deposits" aria-labelledby="t-deposits">
              <header className="panel-head">
                <h2 id="t-deposits">Deposits, piece by piece</h2>
                <p>Each exchange deposit below is exactly the sum of laundered pieces traced back to the theft.</p>
              </header>
              <table className="plain-table">
                <thead><tr><th scope="col">Exchange</th><th scope="col">Deposit</th><th scope="col">Made of</th><th scope="col">From wallet</th></tr></thead>
                <tbody>
                  {d.report.deposits.map((dep) => (
                    <tr key={dep.deposit_tx}>
                      <td>{dep.exchange}</td>
                      <td className="num">{dep.amount.toLocaleString(undefined, { maximumFractionDigits: 1 })} {dep.asset} <span className="muted">{usd(dep.usd)}</span></td>
                      <td>{dep.n_pieces} pieces</td>
                      <td><button className="link-btn mono" onClick={() => pick(dep.wallet)}>{short(dep.wallet)}</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          <p className="to-report">
            Ready to send freeze requests? <RouterLink to="/report">Open the dossier</RouterLink> for letters, evidence and the audit record.
          </p>
        </>
      )}
      <WalletDrawer address={picked} onClose={() => setPicked(null)} />
    </main>
  );
}
