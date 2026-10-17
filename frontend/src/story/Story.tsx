import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import * as THREE from "three";
import DecryptedText from "../components/DecryptedText";
import { gsap, reducedMotion, ScrollTrigger, useSmoothScroll } from "../lib/motion";
import LatentField, { type FieldState } from "./LatentField";
import "./story.css";

// Numbers from Unmask's simulated attack (seed 7), produced by the same engine the case file runs.
const POSTS = [
  { t: "02:09", who: "ghostfox", text: "ur oracle is cooked fr fr" },
  { t: "05:41", who: "ghostfox", text: "flashloans r too ez lol" },
  { t: "09:12", who: "fox_ghost", text: "ngl this pool is free money lol" },
  { t: "13:30", who: "ghostfox", text: "imagine not using a timelock lol" },
];
const TXS = [
  { t: "02:13", from: "0x7a1b…e3f0", what: "41.7 ETH to a fresh wallet" },
  { t: "05:44", from: "0x93c2…10ab", what: "88.2 ETH into the mixer" },
  { t: "09:16", from: "0x5d0e…77c1", what: "102.6 ETH over the bridge" },
  { t: "13:33", from: "0x0e41…9b2d", what: "1,736.5 ETH to an exchange" },
];
const CLUES = [
  { lr: 30, text: "Posted a wallet address that belongs to the attacker's cluster." },
  { lr: 30, text: "A transaction from the cluster carries the message “contact ghostfox on forum for bounty”." },
  { lr: 20, text: "32 of 33 posts land minutes before the wallets move. By chance, about 2 times in 1,000." },
  { lr: 10, text: "Exploit code pushed to GitHub matches the deployed contract, function for function." },
  { lr: 3, text: "Wallets and posts keep the same waking hours: UTC+9." },
];
const STAGES = [0, 1, 2, 3, 3, 4, 4];   // field shape per chapter: print, split, mixer, bridge, (bridge), developed, developed

export default function Story() {
  useSmoothScroll();
  const root = useRef<HTMLElement>(null);
  const state = useRef<FieldState>({ progress: 0, mouse: new THREE.Vector2(9, 9), reveal: 1 }).current;
  const [touch] = useState(() => typeof window !== "undefined" && window.matchMedia("(hover: none)").matches);

  useEffect(() => {
    if (touch) state.mouse.set(0, 0.05);   // no cursor on phones: the light rests on the print
    const onMove = (e: PointerEvent) =>
      state.mouse.set((e.clientX / window.innerWidth) * 2 - 1, -(e.clientY / window.innerHeight) * 2 + 1);
    window.addEventListener("pointermove", onMove);
    return () => window.removeEventListener("pointermove", onMove);
  }, [state, touch]);

  useEffect(() => {
    const el = root.current!;
    const reduce = reducedMotion();
    const ctx = gsap.context(() => {
      // one orchestrated opening: the clock ticks over, then the line arrives (skipped for reduced motion)
      if (!reduce) {
        gsap.timeline({ delay: 0.3 })
          .from(".clock-digit", { yPercent: 110, stagger: 0.07, duration: 0.9, ease: "power4.out" })
          .from(".ch-night .lede", { opacity: 0, y: 14, duration: 0.8 }, "-=0.3")
          .from(".ch-night .hint", { opacity: 0, duration: 1.2 }, "+=0.4");
      }

      // each chapter morphs the field as it rises into view, then holds while you read
      gsap.utils.toArray<HTMLElement>(".ch").forEach((ch, i) => {
        if (i === 0) return;
        ScrollTrigger.create({
          trigger: ch, start: "top 85%", end: "top 30%", scrub: reduce ? false : 0.6,
          onUpdate: (self) => { state.progress = STAGES[i - 1] + (STAGES[i] - STAGES[i - 1]) * self.progress; },
          onLeaveBack: () => { state.progress = STAGES[i - 1]; },
        });
      });
      ScrollTrigger.create({
        trigger: ".ch-night", start: "top top", end: "bottom top",
        onUpdate: (self) => { state.reveal = 1 - self.progress; },
      });

      // the wallet counter: one theft becomes 300 wallets
      const counter = { n: 1 };
      gsap.to(counter, {
        n: 300, ease: "none", snap: { n: 1 },
        scrollTrigger: { trigger: ".ch-split", start: "top 70%", end: "top 15%", scrub: true },
        onUpdate: () => {
          const out = el.querySelector(".wallet-count");
          if (out) out.textContent = `${counter.n} ${counter.n === 1 ? "wallet" : "wallets"}`;
        },
      });

      // two rooms: the threads that line up the clock draw themselves
      gsap.utils.toArray<SVGPathElement>(".thread").forEach((p, i) => {
        const len = p.getTotalLength();
        gsap.fromTo(p, { strokeDasharray: len, strokeDashoffset: len }, {
          strokeDashoffset: 0, ease: "none",
          scrollTrigger: { trigger: ".rooms", start: `top ${70 - i * 6}%`, end: `top ${35 - i * 6}%`, scrub: true },
        });
      });

      // development: night turns to day as the evidence comes up
      gsap.to(el, {
        "--bg": "#ecede6", "--ink": "#34322f", "--ink-2": "#6b6862", "--field": 1, ease: "none",
        scrollTrigger: {
          trigger: ".ch-develop", start: "top 85%", end: "top 25%", scrub: true,
          onUpdate: (self) => document.querySelector(".nav-night")?.setAttribute("data-day", String(self.progress > 0.5)),
        },
      });
      gsap.to(el, {
        "--field": 0.28, ease: "none",
        scrollTrigger: { trigger: ".ch-teams", start: "top 70%", end: "top 30%", scrub: true },
      });
      gsap.fromTo(el, { "--field": 0.28 }, {
        "--field": 1, immediateRender: false, ease: "none",
        scrollTrigger: { trigger: ".ch-develop", start: "top 85%", end: "top 40%", scrub: true },
      });
      gsap.to(el, {
        "--field": 0.12, ease: "none",
        scrollTrigger: { trigger: ".ch-freeze", start: "top 80%", end: "top 30%", scrub: true },
      });

      if (reduce) return;
      // the clue strengths fill in once, when the list arrives
      gsap.from(".clue-bar i", {
        scaleX: 0, transformOrigin: "left", stagger: 0.12, duration: 0.9, ease: "power3.out",
        scrollTrigger: { trigger: ".clues", start: "top 75%" },
      });
      gsap.from(".freeze-bar span", {
        scaleX: 0, transformOrigin: "left", stagger: 0.15, duration: 1, ease: "power3.out",
        scrollTrigger: { trigger: ".freeze-bar", start: "top 80%" },
      });
    }, el);
    return () => {
      ctx.revert();
      document.querySelector(".nav-night")?.removeAttribute("data-day");
    };
  }, [state]);

  return (
    <main className="story" ref={root}>
      <div className="field" aria-hidden>
        <LatentField state={state} />
      </div>

      <section className="ch ch-night" aria-labelledby="t-night">
        <h1 id="t-night" className="clock num" aria-label="02:14 AM">
          {"02:14".split("").map((d, i) => (
            <span key={i} className="clock-mask"><span className="clock-digit">{d}</span></span>
          ))}
        </h1>
        <p className="lede">
          A Tuesday, 2:14 AM. An alert wakes the engineers of a DeFi protocol: $42 million has just left their contracts.
        </p>
        <p className="hint">{touch ? "Something was here." : "Move your cursor through the dark. Something was here."}</p>
      </section>

      <section className="ch ch-split" aria-labelledby="t-split">
        <h2 id="t-split" className="amount num">$42,000,000</h2>
        <p className="wallet-count num" aria-live="off">1 wallet</p>
        <p>
          By 2:17 it sits in 300 fresh wallets. A script split it into uneven pieces, so no single transfer looks like a theft,
          and gave each wallet a little ETH to pay its fees.
        </p>
      </section>

      <section className="ch ch-mixer" aria-labelledby="t-mixer">
        <h2 id="t-mixer">Into the mixer.</h2>
        <p>
          A mixer pools the pieces with everyone else's coins and pays them out to brand-new addresses. The paper trail
          breaks here. The trail of fee money does not: someone still had to pay for each new wallet's gas.
        </p>
      </section>

      <section className="ch ch-bridge" aria-labelledby="t-bridge">
        <h2 id="t-bridge">Over the bridge.</h2>
        <p>
          Other pieces leave Ethereum and reappear on Arbitrum a few minutes later, minus a small fee. Most tools follow one
          chain at a time. Unmask matches the amount that went in with the amount that came out.
        </p>
      </section>

      <section className="ch ch-teams" aria-labelledby="t-teams">
        <h2 id="t-teams">Two rooms, two languages.</h2>
        <div className="rooms">
          <div className="room">
            <h3>What people posted</h3>
            <ul>
              {POSTS.map((p) => (
                <li key={p.t}><span className="num">{p.t}</span><b>{p.who}</b><q>{p.text}</q></li>
              ))}
            </ul>
          </div>
          <svg className="threads" viewBox="0 0 100 400" preserveAspectRatio="none" aria-hidden>
            {[50, 150, 250, 350].map((y, i) => (
              <path key={i} className="thread" d={`M0 ${y} C 50 ${y}, 50 ${y + 8}, 100 ${y + 8}`} />
            ))}
          </svg>
          <div className="room room-ledger">
            <h3>What the wallets did</h3>
            <ul>
              {TXS.map((t) => (
                <li key={t.t}><span className="num">{t.t}</span><b className="mono">{t.from}</b><span>{t.what}</span></li>
              ))}
            </ul>
          </div>
        </div>
        <p>
          Investigators read forums. Analysts read ledgers. Nobody lines up the clock. Unmask does, for every account it
          finds: one of them keeps posting a few minutes before the stolen money moves.
        </p>
      </section>

      <section className="ch ch-develop" aria-labelledby="t-develop">
        <h2 id="t-develop">Every ghost leaves a print.</h2>
        <p className="identity">
          <DecryptedText
            text="ghostfox"
            animateOn="view"
            sequential
            revealDirection="start"
            speed={70}
            className="identity-clear"
            encryptedClassName="identity-noise"
            characters="0123456789abcdef"
          />
        </p>
        <p className="confidence">
          Suspected, with 86% confidence, from five independent clues. One clue alone can never push a name past 34%.
        </p>
        <ul className="clues">
          {CLUES.map((c) => (
            <li key={c.text}>
              <span className="clue-bar" aria-label={`${c.lr} times more likely if the link is real`}>
                <i style={{ width: `${(Math.log(c.lr) / Math.log(30)) * 100}%` }} />
              </span>
              <span className="num clue-lr">×{c.lr}</span>
              <span>{c.text}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="ch ch-freeze" aria-labelledby="t-freeze">
        <h2 id="t-freeze"><span className="amount num">$31.8M</span> can still be frozen.</h2>
        <div className="freeze-bar" role="img" aria-label="Of $41.9M located: $21.2M at exchanges, $10.5M in USDT, $10.1M in raw ETH">
          <span className="fz-ex" style={{ flexGrow: 21.2 }} />
          <span className="fz-usdt" style={{ flexGrow: 10.5 }} />
          <span className="fz-eth" style={{ flexGrow: 10.1 }} />
        </div>
        <dl className="freeze-legend">
          <div><dt className="num">$21.2M</dt><dd>sits at two exchanges, which can freeze the accounts</dd></div>
          <div><dt className="num">$10.5M</dt><dd>is in USDT, which Tether can freeze</dd></div>
          <div><dt className="num">$10.1M</dt><dd>is raw ETH that nobody can freeze, only watch</dd></div>
        </dl>
        <dl className="timing">
          <div><dt className="num">5.5 h</dt><dd>before the theft, the pre-attack warning fired</dd></div>
          <div><dt className="num">20.1 h</dt><dd>passed between the theft and the first cash-out</dd></div>
          <div><dt className="num">~11 h</dt><dd>until the next wave is expected at an exchange</dd></div>
        </dl>
        <div className="cta">
          <Link className="btn btn-primary" to="/case">Open the case file</Link>
          <p className="fine">
            Every number on this page comes from Unmask's simulated attack, with synthetic identities. The case file runs the
            same engine live.
          </p>
        </div>
      </section>
    </main>
  );
}
