import { useCallback, useEffect, useState } from "react";
import { api, type Alert, type Graph, type Link, type Metrics, type MoneyNow, type Report } from "../api";

export type Engine = "idle" | "loading" | "searching" | "reasoning";

export interface CaseData {
  money: MoneyNow;
  links: Link[];
  alerts: Alert[];
  graph: Graph;
  report: Report;
}

/** Everything the console shows, plus the three engine actions. `engine` drives the status orb. */
export function useCase() {
  const [data, setData] = useState<CaseData | null>(null);
  const [engine, setEngine] = useState<Engine>("idle");
  const [error, setError] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [note, setNote] = useState<string>("");

  const refresh = useCallback(async () => {
    const [money, links, alerts, graph, report] = await Promise.all([
      api.moneyNow(), api.links(), api.alerts(), api.graph(420), api.report(),
    ]);
    setData(money.total_usd > 0 || links.length ? { money, links, alerts, graph, report } : null);
    setMetrics(report.metrics);
  }, []);

  const guard = useCallback(async (state: Engine, work: () => Promise<void>) => {
    setEngine(state);
    setError(null);
    try {
      await work();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setEngine("idle");
    }
  }, []);

  useEffect(() => {
    guard("loading", refresh);
  }, [guard, refresh]);

  return {
    data, engine, error, metrics, note, refresh,
    loadSimulation: (seed: number) =>
      guard("loading", async () => {
        const r = await api.simulate(seed);
        setNote(`Loaded ${r.transfers.toLocaleString()} transfers and ${r.posts} posts. Running the analysis.`);
        setEngine("reasoning");
        await api.run();
        await refresh();
        setNote("");
      }),
    collectOsint: () =>
      guard("searching", async () => {
        const r = await api.collectOsint();
        setNote(`Collected ${r.rss} news posts, ${r.github} GitHub posts and ${r.telegram} Telegram messages (${r.entities} clues). Re-running.`);
        setEngine("reasoning");
        await api.run();
        await refresh();
      }),
    rerun: () =>
      guard("reasoning", async () => {
        await api.run();
        await refresh();
      }),
    act: (work: () => Promise<unknown>) => guard("loading", async () => { await work(); await refresh(); }),
  };
}
