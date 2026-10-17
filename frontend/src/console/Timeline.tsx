import { useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import { api, type TimelineEvent } from "../api";
import { date, maskPII, usd } from "../lib/format";
import { useRevealed } from "../lib/privacy";

const LAG = 900; // a post "precedes" a transaction if one follows within 15 minutes

export default function Timeline({ version }: { version: number }) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [hover, setHover] = useState<number | null>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(900);
  const revealed = useRevealed();

  useEffect(() => { api.timeline().then(setEvents).catch(() => setEvents([])); }, [version]);
  useEffect(() => {
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width));
    ro.observe(wrap.current!);
    return () => ro.disconnect();
  }, []);

  const { posts, txs, x, threads, hits, outside } = useMemo(() => {
    const allPosts = events.filter((e): e is Extract<TimelineEvent, { type: "post" }> => e.type === "post");
    const txs = events.filter((e): e is Extract<TimelineEvent, { type: "tx" }> => e.type === "tx");
    // the axis follows the attacker's activity (±2 h); a post from days earlier would squash everything else
    const [t0, t1] = txs.length ? [txs[0].ts - 7200, txs[txs.length - 1].ts + 7200] : d3.extent(events, (e) => e.ts) as [number, number];
    const posts = allPosts.filter((p) => p.ts >= t0 && p.ts <= t1);
    const x = d3.scaleTime().domain([new Date(t0 * 1000), new Date(t1 * 1000)]).range([24, Math.max(w - 24, 100)]);
    const txTimes = txs.map((t) => t.ts);
    const threads = posts.map((p) => {
      const i = d3.bisectRight(txTimes, p.ts);
      const next = txs[i];
      return next && next.ts - p.ts <= LAG ? next : null;
    });
    return { posts, txs, x, threads, hits: threads.filter(Boolean).length, outside: allPosts.length - posts.length };
  }, [events, w]);

  const H = 210, postY = 46, txY = 160;
  const maxUsd = d3.max(txs, (t) => t.usd) ?? 1;
  const tickH = (v: number) => 6 + 40 * Math.log10(1 + v) / Math.log10(1 + maxUsd);
  const active = hover != null ? posts[hover] : null;

  return (
    <section className="panel timeline" aria-labelledby="t-timeline">
      <header className="panel-head">
        <h2 id="t-timeline">Posts against transactions</h2>
        <p>
          {posts.length
            ? `${hits} of ${posts.length} posts by the top suspect are followed by an attacker transaction within 15 minutes.` +
              (outside ? ` ${outside} earlier ${outside === 1 ? "post sits" : "posts sit"} outside this window.` : "")
            : "Run the analysis to line up what people posted with what the wallets did."}
        </p>
      </header>
      <div ref={wrap} className="timeline-plot">
        {events.length > 0 && (
          <svg width={w} height={H} role="img" aria-label={`Timeline of ${posts.length} posts and ${txs.length} transactions`}>
            <text x={0} y={postY - 26} className="lane">Posts</text>
            <text x={0} y={txY + 52} className="lane">Attacker transactions</text>
            <line x1={0} x2={w} y1={txY} y2={txY} className="axis-line" />
            {txs.map((t, i) => (
              <line key={i} x1={x(t.ts * 1000)} x2={x(t.ts * 1000)} y1={txY} y2={txY - tickH(t.usd)} className="tx-tick" />
            ))}
            {posts.map((p, i) => {
              const nx = threads[i];
              const px = x(p.ts * 1000);
              return (
                <g key={i} className={hover === i ? "is-on" : undefined}>
                  {nx && (
                    <path className="thread-line" d={`M${px},${postY} C${px},${(postY + txY) / 2} ${x(nx.ts * 1000)},${(postY + txY) / 2} ${x(nx.ts * 1000)},${txY}`} />
                  )}
                  <circle cx={px} cy={postY} r={hover === i ? 7 : 4.5} className={nx ? "post-dot hit" : "post-dot"}
                    tabIndex={0} onMouseEnter={() => setHover(i)} onFocus={() => setHover(i)} onMouseLeave={() => setHover(null)}
                    aria-label={`Post at ${date(p.ts)}`} />
                </g>
              );
            })}
            {x.ticks(6).map((t, i) => (
              <text key={i} x={x(t)} y={H - 4} className="tick-label" textAnchor="middle">{d3.utcFormat("%b %d %H:%M")(t)}</text>
            ))}
          </svg>
        )}
      </div>
      <div className="timeline-note" aria-live="polite">
        {active ? (
          <>
            <b>{active.who}</b> <span className="muted">{date(active.ts)}</span>
            <q>{revealed ? active.text : maskPII(active.text)}</q>
            {threads[hover!] ? (
              <span>followed {Math.round((threads[hover!]!.ts - active.ts) / 60)} min later by a {usd(threads[hover!]!.usd)} transaction</span>
            ) : <span className="muted">no attacker transaction within 15 minutes</span>}
          </>
        ) : <span className="muted">Point at a post to read it and see what the wallets did next.</span>}
      </div>
    </section>
  );
}
