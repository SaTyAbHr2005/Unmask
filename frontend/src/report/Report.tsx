import { useEffect, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { analyst, api, type Report as R } from "../api";
import { date, hours, maskPII, pct, short, usd } from "../lib/format";
import { setRevealed, useRevealed } from "../lib/privacy";
import { PrintMark } from "../components/Nav";
import "./report.css";

export default function Report() {
  const [r, setR] = useState<R | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState(analyst.get());
  const [reason, setReason] = useState("");
  const [copied, setCopied] = useState<string | null>(null);
  const [polished, setPolished] = useState(false);
  const revealed = useRevealed();
  const clean = (t: string) => (revealed ? t : maskPII(t));

  useEffect(() => { api.report().then(setR).catch((e) => setError(e.message)); }, []);

  const exportPdf = async () => {
    analyst.set(name);
    try { setR(await api.exportReport()); } catch (e) { setError(e instanceof Error ? e.message : String(e)); return; }
    window.print();
  };
  const reveal = async () => {
    analyst.set(name);
    try { await api.reveal(reason); setRevealed(true); setReason(""); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };
  const copy = async (to: string, text: string) => {
    try { await navigator.clipboard.writeText(clean(text)); setCopied(to); setTimeout(() => setCopied(null), 1800); } catch { setCopied(null); }
  };

  if (error) return <main className="dossier"><p className="error" role="alert">{error}</p></main>;
  if (!r) return <main className="dossier" aria-busy="true" />;
  if (!r.case) {
    return (
      <main className="dossier">
        <h1>No case to report on yet.</h1>
        <p>Load and analyse a case in the <RouterLink to="/case">case file</RouterLink>, then come back for the letters and evidence.</p>
      </main>
    );
  }

  return (
    <main className="dossier">
      <header className="dossier-head">
        <PrintMark size={40} />
        <div>
          <h1>{r.case}</h1>
          <p className="muted">Dossier generated {date(r.generated_ts)}. All attributions are suspected until confirmed by law enforcement.</p>
        </div>
      </header>

      <div className="no-print controls">
        <label>Your name for the record <input value={name} onChange={(e) => setName(e.target.value)} onBlur={() => analyst.set(name)} /></label>
        <button className="btn btn-primary" onClick={exportPdf}>Download as PDF</button>
        <button className="btn" disabled={polished} onClick={() => api.report(true).then((x) => { setR(x); setPolished(true); })}>
          {polished ? "Summaries added" : "Add plain-language summaries"}
        </button>
      </div>

      <section className="facts" aria-label="Summary">
        <div><span className="num money">{usd(r.stolen_usd)}</span><span>stolen</span></div>
        <div><span className="num ok">{usd(r.holdings.filter((h) => h.freezable).reduce((a, h) => a + h.usd, 0))}</span><span>can still be frozen</span></div>
        <div><span className="num">{hours(r.timing.prewarn_lead_s)}</span><span>warning before the theft</span></div>
        <div><span className="num">{hours(r.timing.time_to_first_cashout_s)}</span><span>from theft to first cash-out</span></div>
      </section>

      <section aria-labelledby="d-suspects">
        <h2 id="d-suspects">Who is behind the wallets</h2>
        {r.links.map((l) => (
          <article key={l.link_id} className={`d-suspect lab-${l.label}`}>
            <h3><span className="mono">{l.identity}</span> <span className="num">{pct(l.score)}</span> <span className="muted">{l.label}</span></h3>
            <p>{clean(l.explanation)}</p>
            {l.evidence.length > 0 && <p className="muted small">Evidence hashes: <span className="mono">{l.evidence.slice(0, 3).map((h) => h.slice(0, 16)).join(", ")}</span></p>}
          </article>
        ))}
      </section>

      <section aria-labelledby="d-privacy" className="privacy no-print">
        <h2 id="d-privacy">Personal details</h2>
        {revealed ? (
          <p>Emails and IP addresses are shown in full in this tab. <button className="link-btn" onClick={() => setRevealed(false)}>Mask them again</button></p>
        ) : (
          <div className="reveal">
            <p>Emails and IP addresses found in public posts are masked. Showing them is recorded in the audit chain with your reason.</p>
            <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason, e.g. freeze request to Exch-A" aria-label="Reason for showing personal details" />
            <button className="btn" disabled={reason.trim().length < 3} onClick={reveal}>Show and record</button>
          </div>
        )}
      </section>

      <section aria-labelledby="d-letters">
        <h2 id="d-letters">Freeze requests</h2>
        <p className="muted">One letter per party that can freeze funds. Copy, check, send.</p>
        {r.freeze_requests.map((f) => (
          <article key={f.to} className="letter">
            <header>
              <h3>To {f.to}</h3>
              <button className="btn no-print" onClick={() => copy(f.to, f.text)}>{copied === f.to ? "Copied" : "Copy letter"}</button>
            </header>
            <pre>{clean(f.text)}</pre>
          </article>
        ))}
      </section>

      {r.deposits.length > 0 && (
        <section aria-labelledby="d-deposits">
          <h2 id="d-deposits">Deposits reconstructed</h2>
          <ul className="d-list">
            {r.deposits.map((d) => (
              <li key={d.deposit_tx}>
                {d.amount.toLocaleString(undefined, { maximumFractionDigits: 1 })} {d.asset} ({usd(d.usd)}) into {d.exchange} from <span className="mono">{short(d.wallet)}</span>:
                exactly {d.n_pieces} laundered pieces ({d.method}). Deposit <span className="mono">{short(d.deposit_tx)}</span>.
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="d-exits">
        <h2 id="d-exits">Exits and holdings</h2>
        <table className="plain-table">
          <thead><tr><th scope="col">Where</th><th scope="col">Amount</th><th scope="col">Status</th></tr></thead>
          <tbody>
            {r.exits.map((e) => (
              <tr key={`${e.address}${e.arrived}`}>
                <td>{e.exchange} <span className="mono muted">{short(e.address)}</span></td>
                <td className="num">{usd(e.usd)} <span className="muted">{pct(e.share)}</span></td>
                <td>{e.arrived ? "Arrived" : `Expected in ~${hours(e.eta_s)}`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section aria-labelledby="d-audit" className="audit">
        <h2 id="d-audit">Record of decisions</h2>
        <p className={r.audit_ok ? "ok" : "error"}>
          {r.audit_ok
            ? `The audit chain checks out: ${r.audit_entries} decisions, none edited or removed.`
            : "The audit chain does not check out: a recorded decision was edited or removed."}
        </p>
        <p className="muted small">
          Newest entry <span className="mono">{r.audit_head || "none yet"}</span>. Keep this number with the printed dossier: it pins the record.
          {` ${r.evidence_count} pieces of evidence are stored under the hash of their content.`}
        </p>
        {r.metrics && (
          <p className="muted small">
            Simulated case: {pct(r.metrics.precision)} precision and {pct(r.metrics.recall)} recall on the attacker's wallets against the simulator's answer key.
          </p>
        )}
      </section>
    </main>
  );
}
