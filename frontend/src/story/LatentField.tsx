import { useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { bridge, fingerprint, vortex, wallets } from "./shapes";

/** progress: 0 print (night) → 1 split → 2 mixer → 3 bridge → 4 developed print. Written by the story's
 * scroll timeline into this mutable object, so scrolling never re-renders React. */
export interface FieldState { progress: number; mouse: THREE.Vector2; reveal: number }

const vertex = /* glsl */ `
  attribute vec3 aB; attribute vec3 aC; attribute vec3 aD; attribute float aRand;
  uniform float uProgress; uniform float uTime; uniform vec2 uMouse; uniform float uAspect;
  uniform float uSize; uniform float uPixel; uniform float uReveal;
  uniform vec3 uNight; uniform vec3 uMoney; uniform vec3 uEvidence;
  varying vec3 vColor; varying float vAlpha;

  vec3 at(float s) {               // s in [0,4]: A → B → C → D → A
    float seg = floor(clamp(s, 0.0, 3.999));
    float f = smoothstep(0.0, 1.0, fract(clamp(s, 0.0, 3.999)));
    if (s >= 4.0) return position;
    if (seg < 1.0) return mix(position, aB, f);
    if (seg < 2.0) return mix(aB, aC, f);
    if (seg < 3.0) return mix(aC, aD, f);
    return mix(aD, position, f);
  }

  void main() {
    vec3 p = at(uProgress);
    // the vortex keeps turning while it is on screen
    float spin = smoothstep(1.4, 2.0, uProgress) * (1.0 - smoothstep(2.0, 2.6, uProgress));
    float a = spin * uTime * (0.6 + aRand * 0.6);
    p.xz = mat2(cos(a), -sin(a), sin(a), cos(a)) * p.xz;
    // drift: barely any while it is a print (ridges must stay legible), more once the funds disperse
    float drift = mix(0.0025, 0.014, smoothstep(0.2, 1.0, uProgress) * (1.0 - smoothstep(3.4, 4.0, uProgress)));
    p += drift * vec3(sin(uTime * 0.7 + aRand * 40.0), cos(uTime * 0.6 + aRand * 31.0), sin(uTime * 0.5 + aRand * 17.0));

    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    vec4 clip = projectionMatrix * mv;
    gl_Position = clip;
    vec2 ndc = clip.xy / clip.w;

    // night: the print is latent, only the forensic light (cursor) develops it
    float d = distance(ndc * vec2(uAspect, 1.0), uMouse * vec2(uAspect, 1.0));
    float lit = uReveal * smoothstep(0.42, 0.0, d);
    float sweep = smoothstep(0.18, 0.0, abs(ndc.x - sin(uTime * 0.35) * 1.2)) * 0.35;
    float nightAlpha = 0.07 + max(lit, sweep);
    float day = clamp(uProgress, 0.0, 1.0);
    vAlpha = mix(nightAlpha, 0.9, day);

    float developed = smoothstep(3.3, 4.0, uProgress);
    vColor = mix(mix(uNight, uMoney, day), uEvidence, developed);

    float dispersed = smoothstep(0.3, 1.0, uProgress) * (1.0 - smoothstep(3.3, 4.0, uProgress));
    float size = uSize * (0.75 + aRand * 0.6) * mix(1.0 + lit * 0.8, 1.0, day) * (1.0 + dispersed * 0.9);
    gl_PointSize = size * uPixel / -mv.z;
  }
`;

const fragment = /* glsl */ `
  varying vec3 vColor; varying float vAlpha;
  void main() {
    vec2 c = gl_PointCoord - 0.5;
    float r = length(c);
    if (r > 0.5) discard;
    gl_FragColor = vec4(vColor, vAlpha * smoothstep(0.5, 0.25, r));
  }
`;

function Points({ state, count }: { state: FieldState; count: number }) {
  const { size, gl, viewport } = useThree();
  const ref = useRef<THREE.Points>(null);
  const geometry = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(fingerprint(count), 3));
    g.setAttribute("aB", new THREE.BufferAttribute(wallets(count), 3));
    g.setAttribute("aC", new THREE.BufferAttribute(vortex(count), 3));
    g.setAttribute("aD", new THREE.BufferAttribute(bridge(count), 3));
    const rand = new Float32Array(count);
    for (let i = 0; i < count; i++) rand[i] = ((i * 2654435761) % 1000) / 1000;
    g.setAttribute("aRand", new THREE.BufferAttribute(rand, 1));
    return g;
  }, [count]);
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: vertex,
        fragmentShader: fragment,
        transparent: true,
        depthWrite: false,
        uniforms: {
          uProgress: { value: 0 }, uTime: { value: 0 }, uMouse: { value: new THREE.Vector2(9, 9) },
          uAspect: { value: 1 }, uSize: { value: 8 }, uPixel: { value: 1 }, uReveal: { value: 1 },
          uNight: { value: new THREE.Color("#ecede6") },
          uMoney: { value: new THREE.Color("#b9801f") },
          uEvidence: { value: new THREE.Color("#8e2f78") },
        },
      }),
    [],
  );

  useFrame(({ clock }) => {
    const u = material.uniforms;
    u.uTime.value = clock.elapsedTime;
    u.uProgress.value += (state.progress - u.uProgress.value) * 0.08;   // ease toward the scroll position
    u.uMouse.value.lerp(state.mouse, 0.15);
    u.uReveal.value = state.reveal;
    u.uAspect.value = size.width / size.height;
    // ≈2 px dots on a 900 px-tall desktop; phones get bigger dots so the print still reads
    u.uPixel.value = gl.getPixelRatio() * (size.height / 900) * (size.width < 700 ? 1.8 : 1);
    if (ref.current) {
      const p = u.uProgress.value;
      // turns while the money is in motion, comes back face-on for the developed print
      ref.current.rotation.y = Math.sin(clock.elapsedTime * 0.15) * 0.12 + Math.sin((p / 4) * Math.PI) * 0.9 + state.mouse.x * 0.05;
      ref.current.rotation.x = state.mouse.y * -0.06;
      // the print sits right of the copy on wide screens, centred on narrow ones
      ref.current.position.x = viewport.aspect > 1.1 ? viewport.width * 0.2 : 0;
    }
  });

  return <points ref={ref} geometry={geometry} material={material} />;
}

export default function LatentField({ state }: { state: FieldState }) {
  const count = typeof window !== "undefined" && window.innerWidth < 700 ? 7000 : 15000;
  return (
    <Canvas
      camera={{ position: [0, 0, 4.4], fov: 42 }}
      dpr={[1, 2]}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      aria-hidden
    >
      <Points state={state} count={count} />
    </Canvas>
  );
}
