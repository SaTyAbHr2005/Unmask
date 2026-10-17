import type { MoneyNow } from "../api";
import { hours, pct, short, usd } from "../lib/format";

export default function MoneyLedger({ money }: { money: MoneyNow }) {
  const issuer = money.frozen_possible_usd - money.at_exchanges_usd;
  const unfreezable = Math.max(money.unspent_usd - issuer, 0);
  const t = money.timing;
  const located = money.at_exchanges_usd + money.unspent_usd;
  return (
    <aside className="ledger" aria-labelledby="t-ledger">
      <h2 id="t-ledger" className="visually-hidden">Where the money is now</h2>
      <p className="ledger-stolen"><span className="num">{usd(money.total_usd)}</span> {money.timing.theft_ts ? "stolen" : "traced through the attacker's wallets"}</p>
      <p className="ledger-freeze"><span className="num">{usd(money.frozen_possible_usd)}</span> can still be frozen</p>
      <div className="seg" role="img" aria-label={`${usd(money.at_exchanges_usd)} at exchanges, ${usd(issuer)} freezable by the stablecoin issuer, ${usd(unfreezable)} not freezable`}>
        <span className="fz-ex" style={{ flexGrow: money.at_exchanges_usd }} />
        <span className="fz-usdt" style={{ flexGrow: Math.max(issuer, 0) }} />
        <span className="fz-eth" style={{ flexGrow: unfreezable }} />
      </div>
      <dl className="ledger-rows">
        <div><dt>At exchanges</dt><dd className="num">{usd(money.at_exchanges_usd)}</dd></div>
        <div><dt>Freezable by the issuer</dt><dd className="num">{usd(Math.max(issuer, 0))}</dd></div>
        <div><dt>Nobody can freeze</dt><dd className="num">{usd(unfreezable)}</dd></div>
        <div><dt>Still inside the mixer</dt><dd className="num">{usd(money.in_mixers_usd)}</dd></div>
        <div className="muted-row"><dt>Located</dt><dd className="num">{money.total_usd ? pct(located / money.total_usd) : "—"}</dd></div>
      </dl>

      <h3>The freeze window</h3>
      <dl className="ledger-rows window">
        <div><dt>Warning before the theft</dt><dd className="num">{hours(t.prewarn_lead_s)}</dd></div>
        <div><dt>Theft to first cash-out</dt><dd className="num">{hours(t.time_to_first_cashout_s)}</dd></div>
        <div><dt>Next wave expected in</dt><dd className="num">{hours(t.next_predicted_exit_s)}</dd></div>
      </dl>

      <h3>Exits</h3>
      <ul className="exits">
        {money.exits.slice(0, 6).map((e) => (
          <li key={`${e.address}${e.arrived}`}>
            <span className="exit-bar"><i style={{ width: pct(e.share) }} /></span>
            <span><b>{e.exchange}</b> <span className="mono muted">{short(e.address)}</span></span>
            <span className="num">{usd(e.usd)}</span>
            <span className={e.arrived ? "tag tag-in" : "tag tag-next"}>{e.arrived ? "arrived" : `in ~${hours(e.eta_s)}`}</span>
          </li>
        ))}
      </ul>
    </aside>
  );
}
