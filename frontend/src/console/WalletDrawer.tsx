import { useEffect, useRef, useState } from "react";
import { api, type Wallet } from "../api";
import { amount, date, hours, pct, short, usd } from "../lib/format";
import { KIND_COLOR, KIND_NAME } from "./kinds";

const FEATURE_TEXT: [string, string, (v: number) => string][] = [
  ["n_tx", "Transactions sent", (v) => v.toLocaleString()],
  ["mean_gas", "Typical gas price", (v) => `${v.toFixed(1)} gwei`],
  ["std_gas", "Gas price varies by", (v) => `${v.toFixed(2)} gwei`],
  ["round_frac", "Round amounts", (v) => pct(v)],
  ["mean_gap_s", "Typical gap between transactions", (v) => hours(v)],
  ["cv_gap", "Gap regularity (lower is steadier)", (v) => v.toFixed(2)],
  ["active_hours", "Active hours of the day", (v) => `${v} of 24`],
];

export default function WalletDrawer({ address, onClose }: { address: string | null; onClose: () => void }) {
  const [w, setW] = useState<Wallet | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const close = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!address) return;
    setW(null); setErr(null);
    api.wallet(address).then(setW).catch((e) => setErr(e.message));
    close.current?.focus();
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [address, onClose]);

  if (!address) return null;
  return (
    <div className="drawer-scrim" onClick={onClose}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={`Wallet ${address}`} onClick={(e) => e.stopPropagation()}>
        <button ref={close} className="btn drawer-close" onClick={onClose}>Close</button>
        <p className="mono drawer-addr">{address}</p>
        {err && <p className="error">{err}</p>}
        {w && (
          <>
            <p className="drawer-kind"><i style={{ background: KIND_COLOR[w.kind] }} />{w.label || KIND_NAME[w.kind]}</p>
            {w.bot_score != null && (
              <div className="bot">
                <span className="num">{pct(w.bot_score)}</span>
                <span>bot-like. Timing, round amounts and first digits compared with how people actually transact.</span>
              </div>
            )}
            <dl className="ledger-rows">
              {FEATURE_TEXT.filter(([k]) => w.features[k] != null).map(([k, label, fmt]) => (
                <div key={k}><dt>{label}</dt><dd className="num">{fmt(w.features[k]!)}</dd></div>
              ))}
              {w.utc_offset != null && <div><dt>Its own schedule looks like</dt><dd className="num">UTC{w.utc_offset >= 0 ? "+" : ""}{w.utc_offset}</dd></div>}
            </dl>
            {w.holdings.length > 0 && (
              <>
                <h3>Holding now</h3>
                <ul className="plain">{w.holdings.map((h) => <li key={h.asset}>{amount(h.amount)} {h.asset} <span className="muted">{usd(h.usd)}</span> {h.freezable ? <b className="ok">freezable by {h.freezer.replace("exchange:", "")}</b> : <span className="muted">not freezable</span>}</li>)}</ul>
              </>
            )}
            {w.deposits.map((d) => (
              <p key={d.deposit_tx} className="deposit-note">
                Deposited {d.amount.toLocaleString(undefined, { maximumFractionDigits: 1 })} {d.asset} at {d.exchange}: exactly the sum of {d.n_pieces} incoming {d.n_pieces === 1 ? "piece" : "pieces"} ({d.method}).
              </p>
            ))}
            <h3>Latest transfers</h3>
            <ul className="tx-list">
              {w.transfers.map((t) => (
                <li key={t.tx_hash}>
                  <span className="muted">{date(t.ts)}</span>
                  <span>{t.from_addr === w.address ? "sent to" : "received from"} <span className="mono">{short(t.from_addr === w.address ? t.to_addr : t.from_addr)}</span></span>
                  <span className="num">{amount(t.amount)} {t.asset}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </aside>
    </div>
  );
}
