export const usd = (v: number, compact = true) =>
  compact
    ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 }).format(v)
    : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(v);

export const pct = (v: number) => `${Math.round(v * 100)}%`;

export const short = (a: string) => (a.length > 14 ? `${a.slice(0, 6)}…${a.slice(-4)}` : a);

export const hours = (s: number | null | undefined) => {
  if (s == null) return "—";
  const h = s / 3600;
  return h < 1 ? `${Math.round(s / 60)} min` : `${h.toFixed(1)} h`;
};

export const clock = (ts: number) =>
  new Date(ts * 1000).toISOString().slice(11, 16);

export const date = (ts: number) =>
  new Date(ts * 1000).toISOString().slice(0, 16).replace("T", " ") + " UTC";

// Personal details from OSINT (emails, IPs) stay masked until an analyst records a reason to reveal them.
export const maskPII = (text: string) =>
  text
    .replace(/([\w.+-])[\w.+-]*@([\w-]+)((?:\.[\w-]+)+)/g, (_m, a, _d, tld) => `${a}•••@•••${tld}`)
    .replace(/\b(\d{1,3})\.(\d{1,3})\.\d{1,3}\.\d{1,3}\b/g, "$1.$2.•.•");

/** Token amounts: dust stays visible instead of rounding to 0. */
export const amount = (v: number) =>
  v > 0 && v < 0.001 ? "<0.001" : v.toLocaleString("en-US", { maximumFractionDigits: 3 });
