import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import * as THREE from "three";
import { gsap, reducedMotion, ScrollTrigger, useSmoothScroll } from "../lib/motion";
import { usd } from "../lib/format";
import Sky, { SKY_TAGS, sky, type SkyState } from "./Sky";
import "./landing.css";

const HEADLINE = ["EVERY HACK", "LEAVES", "PRINTS."];

const STEPS = [
  {
    n: "01", title: "Trace", lead: "Finds every wallet the attacker controls.",
    body: `Starting from one address, Unmask follows the money hop by hop and groups the wallets that share funding, timing and gas. On Euler: ${sky.nodes.filter((n) => n.k === "attacker").length} attacker wallets among ${sky.nodes.length} addresses touched.`,
  },
  {
    n: "02", title: "Locate", lead: "Shows where the money is right now.",
    body: `Held, inside a mixer, at an exchange, or given back. On Euler: ${usd(sky.returned)} back with Euler, ${usd(sky.mixer)} in Tornado Cash, ${usd(sky.exchange)} at Binance.`,
  },
  {
    n: "03", title: "Freeze", lead: "Drafts the freeze requests.",
    body: "Money at an exchange, or held in USDT or USDC, can still be frozen. Unmask writes the letter to Binance, Tether or Circle. A person approves it before anything is sent.",
  },
];

// Unmask's own numbers on each case (data/replays/README.md), next to what was publicly reported
const CASES = [
  { id: "euler-2023", name: "Euler Finance", when: "March 2023", value: 191.6, what: "traced", extra: "$189.4M given back to Euler", record: "~$197M taken, nearly all returned" },
  { id: "harmony-2022", name: "Harmony bridge", when: "June 2022", value: 98.1, what: "into Tornado Cash", extra: "857 deposits of 100 ETH in 6 days", record: "85,700 ETH (~$98M) laundered by 2 July" },
  { id: "beanstalk-2022", name: "Beanstalk", when: "April 2022", value: 74.4, what: "traced", extra: "$74.3M of it into Tornado Cash", record: "~$76M kept from a $182M drain" },
  { id: "kyberswap-2023", name: "KyberSwap", when: "November 2023", value: 33.5, what: "traced on 3 chains", extra: "Circle and Tether freeze letters", record: "~$48M reported" },
];

const EDGES = [
  { title: "Posts and wallets in one case", body: "Forum posts, GitHub pushes and on-chain messages are scored against the wallets, and every link shows its evidence.", art: "fuse" },
  { title: "The attacker's clock", body: "When the wallets move and when the posts appear gives away the time zone the attacker lives in.", art: "clock" },
  { title: "Fake tokens caught", body: "Look-alike tokens and address-poisoning spam are priced at zero, so they never inflate the numbers.", art: "fake" },
  { title: "The next exit, predicted", body: "From the cash-outs already seen, Unmask warns the exchange the money is heading to next.", art: "exit" },
  { title: "Nobody is named without evidence", body: "No posts that match, no suspect. Real hacks with no public trail show exactly that.", art: "none" },
  { title: "Free to run", body: "Built entirely on free public data and free API tiers. Nothing to pay to investigate a hack.", art: "free" },
];
const SOURCES = ["Etherscan", "Alchemy", "GitHub", "rekt.news", "Telegram", "Binance prices", "Groq", "Gemini", "MongoDB Atlas", "Discord", "Tornado Cash labels", "Circle", "Tether"];

function Art({ kind }: { kind: string }) {
  if (kind === "clock")
    return <div className="art-clock" aria-hidden>{Array.from({ length: 24 }, (_, h) => <i key={h} style={{ height: `${h >= 0 && h < 14 ? 20 + 70 * Math.sin((h / 14) * Math.PI) : 6}%` }} />)}</div>;
  if (kind === "fake") return <div className="art-fake" aria-hidden><s>10,787,465 DAI</s><span className="mono">fake:DAI · $0</span></div>;
  if (kind === "free") return <div className="art-free num" aria-hidden>$0</div>;
  if (kind === "exit") return <div className="art-exit mono" aria-hidden><span>Binance</span><b /><span>in ~4 h</span></div>;
  if (kind === "none") return <div className="art-none mono" aria-hidden>suspects: none</div>;
  return <div className="art-fuse" aria-hidden><span className="mono">“flashloans r too ez”</span><b /><span className="mono">0x7a1b…e3f0</span></div>;
}

export default function Landing() {
  useSmoothScroll();
  const root = useRef<HTMLElement>(null);
  const tags = useRef<(HTMLElement | null)[]>([]);
  const state = useRef<SkyState>({ reveal: 0, dive: 0, step: 0, mouse: new THREE.Vector2(), visible: true }).current;
  const [step, setStep] = useState(0);

  useEffect(() => {
    const onMove = (e: PointerEvent) =>
      state.mouse.set((e.clientX / window.innerWidth) * 2 - 1, -(e.clientY / window.innerHeight) * 2 + 1);
    window.addEventListener("pointermove", onMove);
    return () => window.removeEventListener("pointermove", onMove);
  }, [state]);

  useEffect(() => {
    const reduce = reducedMotion();
    const ctx = gsap.context(() => {
      // opening: the wallets land, the headline rises, the counter runs up to the traced total
      const counter = { v: 0 };
      const out = document.querySelector<HTMLElement>(".hero-count .num")!;
      const setCount = () => { out.textContent = usd(counter.v); };
      if (reduce) {
        state.reveal = 1;
        counter.v = sky.traced;
        setCount();
      } else {
        gsap.timeline({ delay: 0.15 })
          .to(state, { reveal: 1, duration: 3.2, ease: "power2.out" }, 0)
          .from(".hero-line > span", { yPercent: 115, stagger: 0.09, duration: 1.1, ease: "power4.out" }, 0.35)
          .from(".hero .reveal", { opacity: 0, y: 16, stagger: 0.1, duration: 0.8 }, 1.0)
          .to(counter, { v: sky.traced, duration: 2.2, ease: "power3.out", onUpdate: setCount }, 0.9);

        // hero → "what it does": the camera moves in and the sky slides aside
        gsap.to(state, { dive: 1, ease: "none", scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: true } });
        gsap.to(".hero-copy, .hero-count", { opacity: 0, y: -40, ease: "none",
          scrollTrigger: { trigger: ".hero", start: "20% top", end: "70% top", scrub: true } });

        // the three steps play while the section is pinned
        ScrollTrigger.create({
          trigger: ".how", start: "top top", end: "+=220%", pin: true, scrub: true,
          onUpdate: (st) => {
            state.step = 1 + st.progress * 2.2;
            setStep(Math.min(2, Math.floor(st.progress * 3)));
          },
          onLeaveBack: () => { state.step = 0; setStep(0); },
        });

        // the sky fades as the light sections slide over it, and stops drawing once gone
        gsap.to(".sky", { opacity: 0, ease: "none", scrollTrigger: {
          trigger: ".proof", start: "top bottom", end: "top 30%", scrub: true,
          onUpdate: (st) => { state.visible = st.progress < 1; },
        } });

        gsap.utils.toArray<HTMLElement>(".rise").forEach((el) =>
          gsap.from(el, { opacity: 0, y: 40, duration: 0.9, ease: "power3.out", scrollTrigger: { trigger: el, start: "top 88%" } }));
      }

      // the nav turns to ink while the light sections are under it
      const nav = () => document.querySelector(".nav-night");
      ScrollTrigger.create({
        trigger: ".proof", start: "top 64px", endTrigger: ".edge", end: "bottom 64px",
        onToggle: (st) => nav()?.setAttribute("data-day", String(st.isActive)),
      });

      // the real-hack numbers count up as each card arrives
      gsap.utils.toArray<HTMLElement>(".case-card .num[data-to]").forEach((el) => {
        const to = Number(el.dataset.to), o = { v: reduce ? to : 0 };
        const paint = () => { el.textContent = `$${o.v.toFixed(1)}M`; };
        paint();
        if (!reduce) gsap.to(o, { v: to, duration: 1.6, ease: "power2.out", onUpdate: paint, scrollTrigger: { trigger: el, start: "top 90%" } });
      });
    }, root);
    return () => {
      ctx.revert();
      document.querySelector(".nav-night")?.removeAttribute("data-day");
    };
  }, [state]);

  // a light 3D tilt on the case cards, following the pointer
  const tilt = (e: React.PointerEvent<HTMLElement>) => {
    if (reducedMotion() || e.pointerType !== "mouse") return;
    const r = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
    e.currentTarget.style.transform = `perspective(900px) rotateY(${x * 8}deg) rotateX(${-y * 8}deg) translateY(-4px)`;
  };
  const untilt = (e: React.PointerEvent<HTMLElement>) => { e.currentTarget.style.transform = ""; };

  return (
    <main className="landing" ref={root}>
      <div className="sky" aria-hidden>
        <Sky state={state} tags={tags} />
        {SKY_TAGS.map((t, i) => (
          <span key={t.addr} ref={(el) => { tags.current[i] = el; }} className={`sky-tag mono tag-${t.kind}`}>
            {t.text}<em>{t.addr}</em>
          </span>
        ))}
      </div>

      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-copy">
          <p className="kicker mono reveal">Blockchain forensics + open-source intelligence</p>
          <h1 id="hero-title" className="hero-title" aria-label="Every hack leaves prints.">
            {HEADLINE.map((line, i) => (
              <span key={line} className="hero-line" aria-hidden><span className={i === 2 ? "ink" : ""}>{line}</span></span>
            ))}
          </h1>
          <p className="hero-lede reveal">
            Unmask follows stolen crypto across wallets and chains, shows where it is right now, and drafts the freeze
            requests before it's cashed out.
          </p>
          <div className="hero-cta reveal">
            <Link className="pill pill-glow" to="/case?hack=euler-2023">Trace a real hack <span aria-hidden>→</span></Link>
            <Link className="pill pill-line" to="/case?trace=1">Paste an address</Link>
          </div>
        </div>
        <div className="hero-count reveal" aria-live="off">
          <span className="mono">Euler 2023 · real trace</span>
          <span className="num">{usd(sky.traced)}</span>
          <span className="mono back">{usd(sky.returned)} given back</span>
        </div>
        <span className="scroll-cue mono reveal" aria-hidden>Scroll</span>
      </section>

      <section className="how" aria-labelledby="how-title">
        <h2 id="how-title" className="visually-hidden">What Unmask does</h2>
        <ol className="how-steps">
          {STEPS.map((s, i) => (
            <li key={s.n} className={i === step ? "on" : ""} aria-current={i === step ? "step" : undefined}>
              <span className="mono step-n">{s.n} · {s.title}</span>
              <h3>{s.lead}</h3>
              <p>{s.body}</p>
            </li>
          ))}
        </ol>
        <div className="how-rail" aria-hidden>{STEPS.map((s, i) => <i key={s.n} className={i <= step ? "on" : ""} />)}</div>
        <div className={`letter ${step === 2 ? "on" : ""}`} aria-hidden>
          <span className="mono">Freeze request · draft</span>
          <b>To: Binance compliance</b>
          <p>Deposit address 0x28c6…1d60 received {usd(sky.exchange)} traced from the Euler Finance exploit (13 March 2023). We ask you to freeze the account pending review.</p>
          <span className="stamp mono">Awaiting approval</span>
        </div>
      </section>

      <section className="proof" aria-labelledby="proof-title">
        <div className="wrap">
          <p className="mono kicker-dark rise">Checked against the public record</p>
          <h2 id="proof-title" className="section-title rise">Four real hacks, traced live and checked against what was reported.</h2>
          <div className="cases">
            {CASES.map((c) => (
              <Link key={c.id} to={`/case?hack=${c.id}`} className="case-card rise" onPointerMove={tilt} onPointerLeave={untilt}>
                <span className="mono when">{c.when}</span>
                <h3>{c.name}</h3>
                <span className="num" data-to={c.value}>${c.value.toFixed(1)}M</span>
                <span className="what">{c.what}</span>
                <span className="extra">{c.extra}</span>
                <span className="record"><span className="mono">Public record</span>{c.record}</span>
                <span className="open">Open this case <span aria-hidden>→</span></span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="edge" aria-labelledby="edge-title">
        <div className="wrap">
          <p className="mono kicker-dark rise">What most tracers miss</p>
          <h2 id="edge-title" className="section-title rise">Not just a transaction graph.</h2>
          <div className="edges">
            {EDGES.map((e) => (
              <article key={e.title} className="edge-card rise">
                <Art kind={e.art} />
                <h3>{e.title}</h3>
                <p>{e.body}</p>
              </article>
            ))}
          </div>
        </div>
        <div className="marquee" aria-label={`Data sources: ${SOURCES.join(", ")}`}>
          <div className="marquee-track mono" aria-hidden>
            {[...SOURCES, ...SOURCES].map((s, i) => <span key={i}>{s}</span>)}
          </div>
        </div>
      </section>

      <section className="final" aria-labelledby="final-title">
        <h2 id="final-title" className="final-title rise">Follow the money<br /><span className="ink">yourself.</span></h2>
        <div className="final-cta rise">
          <Link className="pill pill-glow" to="/case">Open the case file <span aria-hidden>→</span></Link>
          <Link className="pill pill-line" to="/how-it-works">Watch how it works · 3 min</Link>
        </div>
      </section>

      <footer className="foot">
        <span className="mono">Unmask · free to run · built on public data</span>
        <span className="foot-links">
          <Link to="/case">Case file</Link>
          <Link to="/report">Dossier</Link>
          <Link to="/how-it-works">How it works</Link>
          <a href="https://github.com/SaTyAbHr2005/Unmask" target="_blank" rel="noreferrer">GitHub</a>
        </span>
      </footer>
    </main>
  );
}
