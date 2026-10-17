import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import ForceGraph3D, { type ForceGraphMethods, type LinkObject, type NodeObject } from "react-force-graph-3d";
import type { Graph, GraphEdge, GraphNode, Kind } from "../api";
import { KIND_COLOR, KIND_NAME } from "./kinds";
import { usd } from "../lib/format";

type N = GraphNode & { x?: number; y?: number; z?: number };
type L = GraphEdge & { weight: number };

export default function FlowGraph3D({ graph, onPick }: { graph: Graph; onPick: (id: string) => void }) {
  const wrap = useRef<HTMLDivElement>(null);
  const fg = useRef<ForceGraphMethods<NodeObject<N>, LinkObject<N, L>> | undefined>(undefined);
  const [size, setSize] = useState({ w: 800, h: 560 });

  useEffect(() => {
    const el = wrap.current!;
    const ro = new ResizeObserver(([e]) => setSize({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // frame the whole cluster
  useEffect(() => {
    // The library's zoomToFit reads node positions from a copy that never receives the layout, so frame
    // the camera on the node meshes actually drawn in the scene. The library applies data on a debounce: fit twice.
    const fit = () => {
      const g = fg.current;
      if (!g) return;
      const box = new THREE.Box3();
      const p = new THREE.Vector3();
      g.scene().traverse((o) => {
        if ((o as { __graphObjType?: string }).__graphObjType === "node") box.expandByPoint(o.getWorldPosition(p));
      });
      if (box.isEmpty()) return;
      const center = box.getCenter(new THREE.Vector3());
      const span = box.getSize(new THREE.Vector3());
      const cam = g.camera() as THREE.PerspectiveCamera;
      const t = Math.tan(((cam.fov ?? 50) * Math.PI) / 360);
      const dist = Math.max(span.y / 2 / t, span.x / 2 / (t * cam.aspect)) * 1.12 + span.z / 2;
      g.cameraPosition({ x: center.x, y: center.y, z: center.z + dist }, center, 700);
    };
    const t1 = setTimeout(fit, 500), t2 = setTimeout(fit, 1600);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [graph]);

  const data = useMemo(() => {
    const top = Math.max(...graph.edges.map((e) => e.usd), 1);
    return {
      nodes: graph.nodes.map((n) => ({ ...n })),
      links: graph.edges.map((e) => ({ ...e, weight: e.usd / top })),
    };
  }, [graph]);

  return (
    <div
      className="graph3d"
      ref={wrap}
      // a plain wheel scrolls the page; Ctrl/⌘ + wheel zooms the graph (keeps long pages from trapping the scroll)
      onWheelCapture={(e) => { if (!e.ctrlKey && !e.metaKey) e.stopPropagation(); }}
    >
      <ForceGraph3D
        ref={fg}
        width={size.w}
        height={size.h}
        graphData={data}
        backgroundColor="#e1e3da"
        showNavInfo={false}
        warmupTicks={160}
        cooldownTicks={0}
        enableNodeDrag={false}
        nodeId="id"
        nodeRelSize={1.9}
        nodeVal={(n: N) => (n.kind === "attacker" ? 1 : 2.2) + Math.log10(1 + n.usd) * 0.9}
        nodeColor={(n: N) => KIND_COLOR[n.kind]}
        nodeOpacity={0.92}
        nodeResolution={12}
        nodeLabel={(n: N) =>
          `<div class="g-tip"><b>${n.label}</b><br/>${KIND_NAME[n.kind]}<br/>${usd(n.usd)} moved` +
          (n.bot_score != null ? `<br/>Bot-like: ${Math.round(n.bot_score * 100)}%` : "") + "</div>"}
        linkColor={(l: { kind: string }) => (l.kind === "bridge_link" ? "#b9801f" : "rgba(52,50,47,0.32)")}
        linkWidth={(l: { kind: string }) => (l.kind === "bridge_link" ? 0.5 : 0)}
        linkOpacity={0.5}
        linkDirectionalParticles={(l: { weight: number }) => (l.weight > 0.002 ? 1 + Math.round(l.weight * 3) : 0)}
        linkDirectionalParticleWidth={(l: { weight: number }) => 1.1 + l.weight * 2}
        linkDirectionalParticleColor={() => "#b9801f"}
        linkDirectionalParticleSpeed={(l: { weight: number }) => 0.004 + l.weight * 0.01}
        onNodeClick={(n: N) => onPick(n.id)}
      />
      <ul className="graph-legend" aria-label="Legend">
        {(["attacker", "exchange", "mixer", "bridge", "victim", "decoy"] as Kind[]).map((k) => (
          <li key={k}><i style={{ background: KIND_COLOR[k] }} />{KIND_NAME[k]}</li>
        ))}
        <li><i className="particle" />Money moving</li>
      </ul>
      <p className="graph-hint">Drag to turn, Ctrl + scroll to zoom, click a wallet to open it.</p>
    </div>
  );
}
