/// <reference lib="webworker" />
/**
 * Backtests a whole year in the background, a month at a time, so the page stays
 * responsive: each message is one month of daily revenue after wear for every forecast asked for.
 */
import highsLoader from "highs";
import wasmUrl from "highs/runtime?url";
import { backtestDays, type Battery } from "./battery";

export interface YearRequest {
  id: number;
  actual: (number | null)[];
  forecasts: Record<string, (number | null)[]>;
  battery: Battery;
}

export interface YearProgress {
  id: number;
  first: number;
  revenue: Record<string, (number | null)[]>;
  done: boolean;
}

const highs = highsLoader({ locateFile: () => wasmUrl });
let latest = 0;

self.onmessage = async (event: MessageEvent<YearRequest>) => {
  const { id, actual, forecasts, battery } = event.data;
  latest = id;
  const solver = await highs;
  const total = Math.floor(actual.length / 24);
  // Days with a missing actual price cannot be settled.
  const settled = actual.map((v) => v ?? Number.NaN);
  for (let first = 0; first < total; first += 31) {
    if (latest !== id) return; // a newer request replaced this one
    const last = Math.min(total, first + 31);
    const revenue: Record<string, (number | null)[]> = {};
    for (const [name, forecast] of Object.entries(forecasts)) {
      revenue[name] = backtestDays(solver, settled, forecast, battery, first, last, true).map((v) =>
        v === null || Number.isNaN(v) ? null : v,
      );
    }
    (self as unknown as Worker).postMessage({ id, first, revenue, done: last === total });
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
};
