import { useSyncExternalStore } from "react";

// Whether this analyst has recorded a reason to see unmasked emails/IPs (this browser tab only).
const KEY = "unmask.revealed";
const listeners = new Set<() => void>();

const read = () => {
  try { return sessionStorage.getItem(KEY) === "1"; } catch { return false; }
};

export function setRevealed(v: boolean) {
  try { v ? sessionStorage.setItem(KEY, "1") : sessionStorage.removeItem(KEY); } catch { /* storage blocked */ }
  listeners.forEach((l) => l());
}

export function useRevealed() {
  return useSyncExternalStore(
    (l) => { listeners.add(l); return () => listeners.delete(l); },
    read,
    () => false,
  );
}
