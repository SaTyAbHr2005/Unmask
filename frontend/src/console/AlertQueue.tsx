import { useState } from "react";
import type { Alert } from "../api";

const KIND_TEXT: Record<Alert["kind"], string> = {
  prewarn: "Attack being prepared",
  exit: "Cash-out",
  freeze: "Freeze possible",
  decoy: "Decoy",
};

const STATUS_TEXT: Record<Alert["status"], string> = {
  pending: "Waiting for you", approved: "Approved, no channel set up", sent: "Sent", dismissed: "Dismissed",
};

export default function AlertQueue({ alerts, onApprove, onDismiss }: {
  alerts: Alert[];
  onApprove: (id: string) => void;
  onDismiss: (id: string) => void;
}) {
  const [confirming, setConfirming] = useState<string | null>(null);
  const order = { pending: 0, approved: 1, sent: 2, dismissed: 3 } as const;
  const sorted = [...alerts].sort((a, b) => order[a.status] - order[b.status]);
  const waiting = alerts.filter((a) => a.status === "pending").length;
  return (
    <section className="panel alerts" aria-labelledby="t-alerts">
      <header className="panel-head">
        <h2 id="t-alerts">Alerts</h2>
        <p>{waiting ? `${waiting} waiting. Nothing is sent until you approve it.` : "Nothing waiting."}</p>
      </header>
      <ul className="alert-list">
        {sorted.map((a) => (
          <li key={a.alert_id} className={`alert alert-${a.kind} st-${a.status}`}>
            <p className="alert-kind">{KIND_TEXT[a.kind]} <span className="muted">{a.target.length > 20 ? `${a.target.slice(0, 10)}…` : a.target}</span></p>
            <p className="alert-msg">{a.message}</p>
            {a.status === "pending" ? (
              confirming === a.alert_id ? (
                <div className="alert-actions confirm" role="group" aria-label="Confirm sending">
                  <span>Send this to the alert channel?</span>
                  <button className="btn btn-seal" onClick={() => { setConfirming(null); onApprove(a.alert_id); }}>Send now</button>
                  <button className="btn" onClick={() => setConfirming(null)}>Keep waiting</button>
                </div>
              ) : (
                <div className="alert-actions">
                  <button className="btn btn-primary" onClick={() => setConfirming(a.alert_id)}>Approve and send</button>
                  <button className="btn" onClick={() => onDismiss(a.alert_id)}>Dismiss</button>
                </div>
              )
            ) : <p className="alert-status">{STATUS_TEXT[a.status]}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}
