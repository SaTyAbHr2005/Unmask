import { useEffect, useState } from "react";
import * as d3 from "d3";
import { api, type Heatmap } from "../api";

/** A 24-hour clock: outer ring = when the attacker's wallets act, inner ring = when the suspect posts (UTC).
 * People sleep; matching rings point to one person in one time zone. */
export default function ClockRings({ identity, version }: { identity: string | null; version: number }) {
  const [wallets, setWallets] = useState<Heatmap | null>(null);
  const [posts, setPosts] = useState<Heatmap | null>(null);

  useEffect(() => {
    api.heatmap("cluster:0").then(setWallets).catch(() => setWallets(null));
    if (identity) api.heatmap(`identity:${identity}`).then(setPosts).catch(() => setPosts(null));
  }, [identity, version]);

  const size = 360, c = size / 2;   // room outside the rings for the hour labels
  const ring = (h: Heatmap | null, r0: number, r1: number, color: string) => {
    if (!h) return null;
    const max = Math.max(...h.hours, 1);
    const arc = d3.arc<number>().innerRadius(r0).outerRadius(r1).padAngle(0.012);
    return h.hours.map((v, i) => (
      <path key={i} d={arc({ startAngle: (i / 24) * 2 * Math.PI, endAngle: ((i + 1) / 24) * 2 * Math.PI } as never) ?? ""}
        fill={color} fillOpacity={0.08 + 0.92 * (v / max)} transform={`translate(${c},${c})`}>
        <title>{`${String(i).padStart(2, "0")}:00 UTC: ${v}`}</title>
      </path>
    ));
  };
  const offset = wallets?.utc_offset;
  // waking window 09:00–23:59 local, drawn in UTC
  const wake = offset != null
    ? d3.arc()({ innerRadius: 132, outerRadius: 135, startAngle: (((9 - offset + 24) % 24) / 24) * 2 * Math.PI,
        endAngle: (((9 - offset + 24) % 24) / 24) * 2 * Math.PI + (15 / 24) * 2 * Math.PI })
    : null;

  return (
    <section className="panel clock-panel" aria-labelledby="t-clock">
      <header className="panel-head">
        <h2 id="t-clock">Waking hours</h2>
        <p>Outer ring: when the attacker's wallets act. Inner ring: when the suspect posts. Both in UTC.</p>
      </header>
      <svg viewBox={`0 0 ${size} ${size}`} className="clock-svg" role="img"
        aria-label={offset != null ? `Activity matches a UTC${offset >= 0 ? "+" : ""}${offset} daily schedule` : "Activity by hour"}>
        {ring(wallets, 96, 128, "#b9801f")}
        {ring(posts, 62, 92, "#8e2f78")}
        {wake && <path d={wake} transform={`translate(${c},${c})`} fill="#34322f" />}
        {[0, 6, 12, 18].map((h) => {
          const a = (h / 24) * 2 * Math.PI - Math.PI / 2;
          return <text key={h} x={c + Math.cos(a) * 146} y={c + Math.sin(a) * 146 + 4} textAnchor="middle" className="tick-label">{`${String(h).padStart(2, "0")}:00`}</text>;
        })}
        <text x={c} y={c - 4} textAnchor="middle" className="clock-center num">
          {offset != null ? `UTC${offset >= 0 ? "+" : ""}${offset}` : "—"}
        </text>
        <text x={c} y={c + 18} textAnchor="middle" className="tick-label">
          {wallets?.confidence != null ? `fit ${Math.round(wallets.confidence * 100)}%` : ""}
        </text>
      </svg>
      <p className="panel-foot">
        {offset != null && posts?.utc_offset != null
          ? posts.utc_offset === offset || Math.abs(posts.utc_offset - offset) === 1
            ? `Wallets and posts both follow a UTC${offset >= 0 ? "+" : ""}${offset} day. The dark arc marks 09:00 to midnight there.`
            : `Wallets look like UTC${offset >= 0 ? "+" : ""}${offset}, posts like UTC${posts.utc_offset >= 0 ? "+" : ""}${posts.utc_offset}: different schedules.`
          : "Needs at least 15 timestamps on each side."}
      </p>
    </section>
  );
}
