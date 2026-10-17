import { useEffect, useState } from "react";
import { api, type Matrix } from "../api";
import { clock, short } from "../lib/format";

/** The ledger as a matrix: the attacker's busiest wallets (rows) × hours (columns). Bots show as hard, regular blocks. */
export default function ActivityMatrix({ version, onPick }: { version: number; onPick: (id: string) => void }) {
  const [m, setM] = useState<Matrix | null>(null);
  useEffect(() => { api.matrix(18).then(setM).catch(() => setM(null)); }, [version]);
  if (!m || !m.wallets.length) return null;
  const max = Math.max(...m.counts.flat(), 1);
  return (
    <section className="panel matrix-panel" aria-labelledby="t-matrix">
      <header className="panel-head">
        <h2 id="t-matrix">The ledger as a matrix</h2>
        <p>The attacker's {m.wallets.length} busiest wallets, hour by hour (UTC). Darker means more transactions.</p>
      </header>
      <div className="matrix-scroll">
        <table className="matrix">
          <thead>
            <tr>
              <th scope="col"><span className="visually-hidden">Wallet</span></th>
              {m.buckets.map((b, i) => <th key={b} scope="col" className="tick-label">{i % 3 === 0 ? clock(b) : ""}</th>)}
            </tr>
          </thead>
          <tbody>
            {m.wallets.map((w, r) => (
              <tr key={w}>
                <th scope="row"><button className="link-btn mono" onClick={() => onPick(w)}>{short(w)}</button></th>
                {m.counts[r].map((c, i) => (
                  <td key={i} style={{ opacity: c ? 0.15 + 0.85 * (c / max) : 0.05 }} title={`${c} transactions at ${clock(m.buckets[i])} UTC`} />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
