import type { Highs } from "highs";
import { useEffect, useRef, useState } from "react";
import type { Battery } from "./battery";
import type { YearProgress, YearRequest } from "./year.worker";

/** HiGHS once loaded (null until then, or if WebAssembly is unavailable). */
export function useHighs(): { highs: Highs | null; failed: boolean } {
  const [state, setState] = useState<{ highs: Highs | null; failed: boolean }>({
    highs: null,
    failed: false,
  });
  useEffect(() => {
    let live = true;
    import("./highs")
      .then(({ loadHighs }) => loadHighs())
      .then(
        (highs) => live && setState({ highs, failed: false }),
        () => live && setState({ highs: null, failed: true }),
      );
    return () => {
      live = false;
    };
  }, []);
  return state;
}

export interface YearRevenue {
  revenue: Record<string, (number | null)[]>;
  /** Days solved so far, and the total. */
  solved: number;
  total: number;
  milliseconds: number;
}

/** Daily revenue for a whole year per forecast, solved in a worker and filled in month by month. */
export function useYear(
  key: string,
  actual: (number | null)[] | null,
  forecasts: Record<string, (number | null)[]> | null,
  battery: Battery,
): YearRevenue | null {
  const worker = useRef<Worker | null>(null);
  const counter = useRef(0);
  const [result, setResult] = useState<YearRevenue | null>(null);
  useEffect(() => {
    if (typeof Worker === "undefined") return;
    worker.current = new Worker(new URL("./year.worker.ts", import.meta.url), { type: "module" });
    return () => worker.current?.terminate();
  }, []);
  useEffect(() => {
    const current = worker.current;
    if (!current || !actual || !forecasts) return;
    const id = ++counter.current;
    const total = Math.floor(actual.length / 24);
    const started = performance.now();
    const revenue: Record<string, (number | null)[]> = Object.fromEntries(
      Object.keys(forecasts).map((name) => [name, new Array(total).fill(null)]),
    );
    setResult({ revenue, solved: 0, total, milliseconds: 0 });
    current.onmessage = (event: MessageEvent<YearProgress>) => {
      const message = event.data;
      if (message.id !== id) return;
      for (const [name, values] of Object.entries(message.revenue)) {
        revenue[name].splice(message.first, values.length, ...values);
      }
      const solved = message.first + Object.values(message.revenue)[0].length;
      setResult({
        revenue: { ...revenue },
        solved,
        total,
        milliseconds: performance.now() - started,
      });
    };
    const request: YearRequest = { id, actual, forecasts, battery };
    current.postMessage(request);
  }, [key]); // ``key`` stands for the inputs
  return result;
}
