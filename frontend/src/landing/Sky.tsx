import { useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { reducedMotion } from "../lib/motion";
import sky from "./euler-sky.json";

/** Written by the landing page's scroll timeline, so scrolling never re-renders React.
 * reveal: 0→1 intro · dive: 0 hero → 1 graph moved aside for "what it does" · step: 0 hero, 1 trace, 2 locate, 3 freeze */
export interface SkyState { reveal: number; dive: number; step: number; mouse: THREE.Vector2; visible: boolean }

const KINDS = ["other", "attacker", "victim", "mixer", "exchange"] as const;
const COLOR = ["#8d879a", "#e07cc8", "#62c2a6", "#e3a948", "#f0c76a"];
// how bright each kind is at step 0..3 (other, attacker, victim, mixer, exchange)
const WEIGHTS = [
  [0.4, 1.1, 1, 1, 1],
  [0.1, 1.5, 0.25, 0.25, 0.25],
  [0.1, 0.35, 1.6, 1.6, 1.6],
  [0.08, 0.25, 0.35, 0.5, 2.0],
];
const SCALE = 5.2;

const vertex = /* glsl */ `
  attribute float aKind; attribute float aSize; attribute float aDelay; attribute vec3 aColor;
  uniform float uReveal; uniform float uTime; uniform float uPixel; uniform float uW[5];
  varying vec3 vColor; varying float vAlpha;
  void main() {
    float w = uW[int(aKind)];
    float on = smoothstep(aDelay, aDelay + 0.25, uReveal);
    vec3 p = position + 0.03 * vec3(sin(uTime * 0.5 + aDelay * 40.0), cos(uTime * 0.4 + aDelay * 31.0), 0.0);
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;
    float pulse = aKind > 3.5 ? 1.0 + 0.35 * sin(uTime * 3.0) * step(1.5, w) : 1.0;
    gl_PointSize = aSize * uPixel * (0.6 + 0.4 * w) * pulse * on / -mv.z;
    vColor = aColor;
    vAlpha = clamp(w, 0.0, 1.0) * on;
  }`;
const fragment = /* glsl */ `
  varying vec3 vColor; varying float vAlpha;
  void main() {
    float d = length(gl_PointCoord - 0.5);
    float core = smoothstep(0.5, 0.0, d);
    float glow = pow(core, 2.2) + 0.35 * pow(core, 0.8);
    gl_FragColor = vec4(vColor * glow, glow * vAlpha);
  }`;

function useGraph() {
  return useMemo(() => {
    const n = sky.nodes.length;
    const pos = new Float32Array(n * 3), col = new Float32Array(n * 3);
    const kind = new Float32Array(n), size = new Float32Array(n), delay = new Float32Array(n);
    const c = new THREE.Color();
    sky.nodes.forEach((node, i) => {
      const k = KINDS.indexOf(node.k as (typeof KINDS)[number]);
      pos.set(node.p.map((v) => v * SCALE), i * 3);
      c.set(COLOR[Math.max(k, 0)]).toArray(col, i * 3);
      kind[i] = Math.max(k, 0);
      size[i] = (k > 0 ? 70 : 42) + Math.log10(1 + node.u) * (k > 0 ? 9 : 5);
      delay[i] = k > 0 ? 0.15 + 0.25 * (i / n) : 0.05 + 0.7 * ((i * 0.6180339) % 1);   // the cluster lands first
    });
    const lines = new Float32Array(sky.edges.length * 6), lcol = new Float32Array(sky.edges.length * 6);
    sky.edges.forEach(([a, b], i) => {
      lines.set(pos.subarray(a * 3, a * 3 + 3), i * 6);
      lines.set(pos.subarray(b * 3, b * 3 + 3), i * 6 + 3);
      const hot = kind[a] > 0 && kind[b] > 0;
      c.set(hot ? "#b0549b" : "#4a4254").toArray(lcol, i * 6);
      c.toArray(lcol, i * 6 + 3);
    });
    const dust = new Float32Array(1400 * 3);
    for (let i = 0; i < dust.length; i += 3) {
      const r = 14 + ((i * 7.31) % 18), t = (i * 2.399) % (Math.PI * 2), f = Math.acos(1 - 2 * (((i * 0.618) % 1)));
      dust.set([r * Math.sin(f) * Math.cos(t), r * Math.sin(f) * Math.sin(t), r * Math.cos(f)], i);
    }
    return { pos, col, kind, size, delay, lines, lcol, dust };
  }, []);
}

function Scene({ state, tags }: { state: SkyState; tags: React.RefObject<(HTMLElement | null)[]> }) {
  const g = useGraph();
  const group = useRef<THREE.Group>(null!);
  const lineMat = useRef<THREE.LineBasicMaterial>(null!);
  const { camera, size, gl } = useThree();
  const uniforms = useMemo(() => ({
    uReveal: { value: 0 }, uTime: { value: 0 }, uPixel: { value: 1 }, uW: { value: [...WEIGHTS[0]] },
  }), []);
  const tagged = useMemo(() => sky.nodes.flatMap((n, i) => ("t" in n ? [i] : [])), []);
  const v = useMemo(() => new THREE.Vector3(), []);
  const tilt = useRef(new THREE.Vector2());
  const still = useMemo(reducedMotion, []);

  useFrame((_, dt) => {
    if (!state.visible) return;
    const u = uniforms;
    u.uTime.value += dt;
    u.uReveal.value = state.reveal * 1.25;
    u.uPixel.value = size.height * gl.getPixelRatio() * 0.012;
    // blend the per-kind brightness between the two steps around `step`
    const s = Math.min(state.step, 2.999), i = Math.floor(s), f = THREE.MathUtils.smoothstep(s - i, 0, 1);
    u.uW.value = WEIGHTS[i].map((w, k) => w + (WEIGHTS[i + 1][k] - w) * f);
    lineMat.current.opacity = 0.2 * state.reveal * (1 - 0.6 * Math.min(state.step, 1) + 0.25 * Math.max(state.step - 2, 0));

    tilt.current.lerp(state.mouse, 0.04);
    const g0 = group.current;
    if (!still) g0.rotation.y += dt * 0.05;
    g0.rotation.x = tilt.current.y * 0.18;
    g0.rotation.z = tilt.current.x * -0.06;
    // dive: closer, and the graph slides right to make room for the text column
    const wide = size.width > 820;
    camera.position.z = 10.5 - state.dive * 3.2;
    g0.position.x = wide ? 1.7 + state.dive * 0.9 : 0;
    g0.position.y = wide ? 0 : 1.9 - state.dive * 3.4;   // phones: in the empty space above the headline

    tags.current?.forEach((el, j) => {
      if (!el) return;
      v.fromArray(g.pos, tagged[j] * 3).applyMatrix4(g0.matrixWorld).project(camera);
      const shown = v.z < 1 && Math.abs(v.x) < 0.95 && Math.abs(v.y) < 0.9;
      el.style.transform = `translate3d(${(v.x * 0.5 + 0.5) * size.width}px, ${(-v.y * 0.5 + 0.5) * size.height}px, 0)`;
      el.style.opacity = shown ? String(Math.min(state.reveal * 1.4 - 0.4, 1) * (state.step < 0.5 || state.step > 1.5 ? 1 : 0.25)) : "0";
    });
  });

  return (
    <group ref={group}>
      <points>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[g.pos, 3]} />
          <bufferAttribute attach="attributes-aColor" args={[g.col, 3]} />
          <bufferAttribute attach="attributes-aKind" args={[g.kind, 1]} />
          <bufferAttribute attach="attributes-aSize" args={[g.size, 1]} />
          <bufferAttribute attach="attributes-aDelay" args={[g.delay, 1]} />
        </bufferGeometry>
        <shaderMaterial vertexShader={vertex} fragmentShader={fragment} uniforms={uniforms}
                        transparent depthWrite={false} blending={THREE.AdditiveBlending} />
      </points>
      <lineSegments>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[g.lines, 3]} />
          <bufferAttribute attach="attributes-color" args={[g.lcol, 3]} />
        </bufferGeometry>
        <lineBasicMaterial ref={lineMat} vertexColors transparent opacity={0} depthWrite={false} blending={THREE.AdditiveBlending} />
      </lineSegments>
      <points>
        <bufferGeometry><bufferAttribute attach="attributes-position" args={[g.dust, 3]} /></bufferGeometry>
        <pointsMaterial color="#6d6578" size={0.05} transparent opacity={0.55} depthWrite={false} />
      </points>
    </group>
  );
}

export const SKY_TAGS = sky.nodes.flatMap((n) => ("t" in n ? [{ text: n.t as string, addr: n.a, kind: n.k }] : []));

export default function Sky({ state, tags }: { state: SkyState; tags: React.RefObject<(HTMLElement | null)[]> }) {
  return (
    <Canvas camera={{ position: [0, 0, 10.5], fov: 45 }} dpr={[1, 2]} gl={{ antialias: true, alpha: true }}
            aria-hidden style={{ position: "absolute", inset: 0 }}>
      <Scene state={state} tags={tags} />
    </Canvas>
  );
}

export { sky };
