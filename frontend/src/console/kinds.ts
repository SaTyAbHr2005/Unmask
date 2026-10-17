import type { Kind } from "../api";

export const KIND_COLOR: Record<Kind, string> = {
  attacker: "#8e2f78",
  exchange: "#3e7a6a",
  mixer: "#34322f",
  bridge: "#6b6862",
  dex: "#b9801f",
  victim: "#c2362b",
  decoy: "#b8b9b1",
  wallet: "#8a8780",
};

export const KIND_NAME: Record<Kind, string> = {
  attacker: "Attacker wallet",
  exchange: "Exchange (exit)",
  mixer: "Mixer",
  bridge: "Bridge",
  dex: "Token swap",
  victim: "Victim protocol",
  decoy: "Decoy (planted)",
  wallet: "Other wallet",
};
