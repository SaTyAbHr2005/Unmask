// Point layouts for the story's particle field. Each returns n×3 floats. Deterministic (seeded) so the
// print looks the same on every visit.

function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const gauss = (r: () => number) => Math.sqrt(-2 * Math.log(r() + 1e-9)) * Math.cos(2 * Math.PI * r());

/** A whorl fingerprint: distorted concentric ridges clipped to a fingertip, with ridge breaks (minutiae). */
export function fingerprint(n: number, seed = 7): Float32Array {
  const r = rng(seed);
  const out = new Float32Array(n * 3);
  const ridges = 30;
  const lens: number[] = [];
  for (let k = 0; k < ridges; k++) lens.push(0.05 + k * 0.042);
  const total = lens.reduce((a, b) => a + b, 0);
  let i = 0;
  while (i < n) {
    // pick a ridge in proportion to its length
    let pick = r() * total;
    let k = 0;
    while (pick > lens[k] && k < ridges - 1) pick -= lens[k++];
    const rad = lens[k];
    const th = r() * Math.PI * 2;
    // minutiae: short gaps along each ridge
    if (Math.sin(th * (5 + (k % 4)) + k * 1.7) > 0.93) continue;
    const wobble = Math.sin(th * 3 + k * 0.45) * 0.014 * (k / ridges) + Math.sin(th * 7 + k) * 0.004;
    const x = Math.cos(th) * (rad * 0.8 + wobble) + Math.sin(rad * 6) * 0.05;
    const y = Math.sin(th) * (rad * 1.05 + wobble) - 0.06;
    // fingertip outline
    if ((x / 1.0) ** 2 + ((y + 0.1) / 1.3) ** 2 > 1) continue;
    const jitter = 0.0035;
    out[i * 3] = x + gauss(r) * jitter;
    out[i * 3 + 1] = y + gauss(r) * jitter;
    out[i * 3 + 2] = -0.22 * (x * x + y * y) + gauss(r) * 0.01;
    i++;
  }
  return out;
}

/** The split: 300 small clusters (fresh wallets) spread through space. */
export function wallets(n: number, count = 300, seed = 11): Float32Array {
  const r = rng(seed);
  const centers: number[][] = [];
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let c = 0; c < count; c++) {
    const y = 1 - (c / (count - 1)) * 2;
    const rad = Math.sqrt(1 - y * y);
    const th = golden * c;
    const dist = 0.85 + r() * 0.55;
    centers.push([Math.cos(th) * rad * dist * 1.1, y * dist * 1.05, Math.sin(th) * rad * dist * 0.7]);
  }
  const out = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const c = centers[i % count];
    const spread = 0.028 + (i % 7) * 0.004;
    out[i * 3] = c[0] + gauss(r) * spread;
    out[i * 3 + 1] = c[1] + gauss(r) * spread;
    out[i * 3 + 2] = c[2] + gauss(r) * spread;
  }
  return out;
}

/** The mixer: everything funnels into one vortex. */
export function vortex(n: number, seed = 13): Float32Array {
  const r = rng(seed);
  const out = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const t = r();
    const angle = t * 46 * Math.PI + i * 0.618;
    const rad = 0.08 + 1.45 * Math.pow(1 - t, 1.6) + gauss(r) * 0.02;
    out[i * 3] = Math.cos(angle) * rad;
    out[i * 3 + 1] = (t - 0.5) * 2.7;
    out[i * 3 + 2] = Math.sin(angle) * rad * 0.8;
  }
  return out;
}

/** The bridge: two chains as two tilted planes, with a thin arc of funds crossing between them. */
export function bridge(n: number, seed = 17): Float32Array {
  const r = rng(seed);
  const out = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const u = r();
    let x: number, y: number, z: number;
    if (u < 0.12) {
      // the crossing arc
      const t = r();
      x = -1.15 + t * 2.3;
      y = Math.sin(t * Math.PI) * 0.75 + 0.15 + gauss(r) * 0.02;
      z = gauss(r) * 0.03;
    } else {
      const side = u < 0.56 ? -1 : 1;
      const gx = Math.round(r() * 22) / 22 - 0.5;
      const gy = Math.round(r() * 22) / 22 - 0.5;
      x = side * 1.15 + gx * 0.9 * Math.cos(0.6) * side;
      y = gy * 1.6;
      z = gx * 0.9 * Math.sin(0.6) + gauss(r) * 0.008;
    }
    out[i * 3] = x;
    out[i * 3 + 1] = y;
    out[i * 3 + 2] = z;
  }
  return out;
}
