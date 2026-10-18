import { useEffect, useRef, useState } from "react";
import { api, type WatchStatus } from "../api";
import { amount, clock, short } from "../lib/format";

/** Watch mode: the engine keeps checking for new transfers, reruns itself and queues alerts; this strip shows it
 * happening and refreshes the case whenever the analysis reran. */
export default function LiveWatch({ onRerun, caseName }: { onRerun: () => void; caseName: string }) {
  const [s, setS] = useState<WatchStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reruns = useRef(0);
  const [now, setNow] = useState(() => Date.now() / 1000);

  // keep polling while on (and once on mount, to pick up a watch that is already running)
  useEffect(() => {
    let stop = false;
    const tick = async () => {
      const st = await api.liveStatus().catch(() => null);
      if (stop || !st) return;
      setS(st);
      setNow(Date.now() / 1000);
      if (st.reruns > reruns.current) {
        reruns.current = st.reruns;
        onRerun();
      }
    };
    tick();
    const id = window.setInterval(tick, 3000);
    return () => { stop = true; window.clearInterval(id); };
  }, [onRerun]);

  // a new case means a new watch
  useEffect(() => { reruns.current = 0; }, [caseName]);

  const on = !!s?.on;
  const toggle = async () => {
    setError(null);
    try {
      const st = on ? await api.liveStop() : await api.liveStart();
      reruns.current = st.reruns;
      setS(st);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  const ago = (ts: number | null) => (ts == null ? "—" : `${Math.max(0, Math.round(now - ts))} s ago`);

  return (
    <section className={`live-watch ${on ? "on" : ""}`} aria-label="Watch live">
      <div className="lw-head">
        <button className={`btn ${on ? "" : "btn-primary"}`} onClick={toggle} aria-pressed={on}>
          <span className="lw-dot" aria-hidden />{on ? "Stop watching" : "Watch live"}
        </button>
        {on && s ? (
          <p className="lw-stats" role="status">
            Watching {s.watching} attacker wallets {s.source === "simulated" ? "(simulated attack: it keeps moving the money)" : "on the blockchain"}.
            {" "}Checked {s.checks}× · last {ago(s.last_check_ts)} · {s.new_transfers} new transfers · analysis reran {s.reruns}×
            {" "}· posts re-collected {ago(s.last_posts_ts)} · stops by itself at {clock(s.stops_ts)} UTC
          </p>
        ) : (
          <p className="lw-stats muted">
            Keeps checking the attacker's wallets every block (12 s), reruns the analysis when money moves, puts new
            alerts in the queue for approval, and re-collects public posts every 10 minutes.
          </p>
        )}
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {s?.error && <p className="error" role="alert">Watching stopped: {s.error}</p>}
      {on && s && s.recent.length > 0 && (
        <ol className="lw-feed" aria-label="New transfers" aria-live="polite">
          {s.recent.map((t, i) => (
            <li key={`${t.ts}-${t.from}-${i}`}>
              <span className="mono muted">{clock(t.ts)}</span>
              <span className="mono">{short(t.from)}</span>
              <span aria-hidden>→</span>
              <b>{t.to_label ? t.to_label.replace("exchange:", "") : short(t.to)}</b>
              <span className="num">{amount(t.amount)} {t.asset}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
