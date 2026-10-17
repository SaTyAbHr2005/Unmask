import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
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
            <button className="btn" disabled={busy || !d} onClick={c.collectOsint}>Collect public posts</button>
            <button className="btn" disabled={busy || !d} onClick={c.rerun}>Run analysis again</button>
          </div>
        </div>
      </header>

      {c.note && <p className="note" aria-live="polite">{c.note}</p>}
      {c.error && <p className="error" role="alert">{c.error}</p>}

      {!d ? (
        <section className="empty-case">
          <h2>Nothing developed yet.</h2>
          <p>
            Load the simulated attack to watch Unmask work end to end: $42 million split over 300 wallets, a mixer, a bridge,
            decoys, and an attacker who can't stop posting. It takes about a second.
          </p>
          <button className="btn btn-primary" disabled={busy} onClick={() => c.loadSimulation(seed)}>Load simulated attack</button>
        </section>
      ) : (
        <>
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
