import { useState } from "react";
import DecryptedText from "../components/DecryptedText";
import type { Link } from "../api";
import { maskPII, pct } from "../lib/format";
import { useRevealed } from "../lib/privacy";

const LABEL_TEXT: Record<Link["label"], string> = {
  high: "High confidence", medium: "Medium confidence", low: "Low confidence",
  confirmed: "Confirmed by an analyst", rejected: "Rejected by an analyst",
};

const SIGNAL_NAME: Record<string, string> = {
  address_mention: "Posted a cluster address",
  onchain_message: "Named in an on-chain message",
  time_delta: "Posts precede transactions",
  bytecode: "Posted the exploit's code",
  rhythm: "Same time zone",
};

export default function Suspects({ links, onDecide, onPolish, polished }: {
  links: Link[];
  onDecide: (id: string, action: "confirm" | "reject") => void;
  onPolish: () => void;
  polished: boolean;
}) {
  const [open, setOpen] = useState<string | null>(links[0]?.link_id ?? null);
  const revealed = useRevealed();
  const top = links.filter((l) => l.score >= 0.02 || l.status !== "suspected").slice(0, 6);
  return (
    <section className="panel suspects" aria-labelledby="t-suspects">
      <header className="panel-head">
        <h2 id="t-suspects">Suspects</h2>
        <p>Every name starts as suspected. Only you can confirm one.</p>
        <button className="btn" onClick={onPolish} disabled={polished}>
          {polished ? "Plain-language summaries added" : "Add plain-language summaries"}
        </button>
      </header>
      <ol className="suspect-list">
        {top.map((l, i) => {
          const isOpen = open === l.link_id;
          const name = l.identity.split(":").slice(1).join(":");
          return (
            <li key={l.link_id} className={`suspect lab-${l.label}`}>
              <button className="suspect-row" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : l.link_id)}>
                <span className="suspect-name mono">
                  {i === 0 && l.label === "high"
                    ? <DecryptedText text={name} animateOn="view" sequential speed={60} characters="0123456789abcdef" encryptedClassName="noise" />
                    : name}
                </span>
                <span className="suspect-where">{l.identity.split(":")[0]}</span>
                <span className="score"><i style={{ width: pct(l.score) }} /></span>
                <span className="num score-num">{pct(l.score)}</span>
                <span className="chip">{LABEL_TEXT[l.label]}</span>
              </button>
              {isOpen && (
                <div className="suspect-body">
                  <p>{revealed ? l.explanation : maskPII(l.explanation)}</p>
                  <ul className="signals">
                    {[...l.signals].sort((a, b) => b.lr - a.lr).map((s) => (
                      <li key={s.name}>
                        <span className="num lr">×{s.lr}</span>
                        <span>{SIGNAL_NAME[s.name] ?? s.name}</span>
                      </li>
                    ))}
                  </ul>
                  <div className="decide">
                    <button className="btn btn-primary" disabled={l.status === "confirmed"} onClick={() => onDecide(l.link_id, "confirm")}>Confirm link</button>
                    <button className="btn" disabled={l.status === "rejected"} onClick={() => onDecide(l.link_id, "reject")}>Reject link</button>
                    <span className="muted">Recorded in the audit chain under your name.</span>
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
