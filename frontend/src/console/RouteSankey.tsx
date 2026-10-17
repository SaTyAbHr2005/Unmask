import { useEffect, useMemo, useState } from "react";
import { sankey, sankeyLinkHorizontal, type SankeyLink, type SankeyNode } from "d3-sankey";
import { api, type Sankey } from "../api";
import { usd } from "../lib/format";

type NodeExtra = { name: string };
type LinkExtra = { value: number };

function colorFor(name: string) {
  if (name === "Stolen funds") return "#b9801f";
  if (name === "Held · not freezable") return "#34322f";
  if (name === "Held · freezable") return "#7fa89c";
  if (["Mixer", "Bridge", "DEX swap", "Direct"].includes(name)) return "#6b6862";
  return "#3e7a6a"; // an exchange
}

const display = (name: string) => name.replace("Held · freezable", "Held, freezable").replace("Held · not freezable", "Held, not freezable");

export default function RouteSankey({ version }: { version: number }) {
  const [raw, setRaw] = useState<Sankey | null>(null);
  useEffect(() => { api.sankey().then(setRaw).catch(() => setRaw(null)); }, [version]);

  const W = 640, H = 300;
  const layout = useMemo(() => {
    if (!raw || !raw.links.length) return null;
    const gen = sankey<NodeExtra, LinkExtra>().nodeWidth(10).nodePadding(16).extent([[1, 8], [W - 190, H - 8]]);
    return gen({ nodes: raw.nodes.map((n) => ({ ...n })), links: raw.links.map((l) => ({ ...l })) });
  }, [raw]);

  return (
    <section className="panel sankey-panel" aria-labelledby="t-routes">
      <header className="panel-head">
        <h2 id="t-routes">Where the money went</h2>
        <p>From the theft, through each laundering route, to where it sits now.</p>
      </header>
      {layout ? (
        <svg viewBox={`0 0 ${W} ${H}`} className="sankey-svg" role="img" aria-label="Laundering routes and where the funds are now">
          {layout.links.map((l: SankeyLink<NodeExtra, LinkExtra>, i) => (
            <path key={i} d={sankeyLinkHorizontal()(l) ?? ""} fill="none" stroke="#b9801f" strokeOpacity={0.28}
              strokeWidth={Math.max(1, l.width ?? 1)}>
              <title>{`${display((l.source as NodeExtra).name)} to ${display((l.target as NodeExtra).name)}: ${usd(l.value)}`}</title>
            </path>
          ))}
          {layout.nodes.map((n: SankeyNode<NodeExtra, LinkExtra>, i) => (
            <g key={i}>
              <rect x={n.x0} y={n.y0} width={(n.x1 ?? 0) - (n.x0 ?? 0)} height={Math.max(1, (n.y1 ?? 0) - (n.y0 ?? 0))} fill={colorFor(n.name)} />
              <text x={(n.x1 ?? 0) + 6} y={((n.y0 ?? 0) + (n.y1 ?? 0)) / 2} dy="0.35em" className="sankey-label">
                {display(n.name)} <tspan className="muted">{usd(n.value ?? 0)}</tspan>
              </text>
            </g>
          ))}
        </svg>
      ) : <p className="empty">No routes yet. Run the analysis first.</p>}
    </section>
  );
}
