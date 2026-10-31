/**
 * The battery optimiser in the browser: the same daily mixed-integer programme as
 * `openenergy.dispatch.arbitrage.optimise_dispatch` (energy arbitrage, no frequency
 * response, no fade), solved by HiGHS compiled to WebAssembly.
 *
 * Maximise sum_t (price_t - wear) d_t dt - (price_t + wear) c_t dt subject to
 * e_{t+1} = e_t + eta_c c_t dt - d_t dt / eta_d, energy within the SOC limits, the day
 * ending exactly where it started, and an on-charge flag u_t so the battery never
 * charges and discharges in the same hour.
 */
import type { Highs, ModelData } from "highs";

export interface Battery {
  powerMw: number;
  energyMwh: number;
  etaCharge: number;
  etaDischarge: number;
  /** GBP per MWh moved in or out (`dispatch.degradation_cost`). */
  wear: number;
  socMin?: number;
  socMax?: number;
  initialSoc?: number;
}

export interface Plan {
  charge: Float64Array;
  discharge: Float64Array;
  /** Stored energy at each hour boundary (n + 1 values). */
  energy: Float64Array;
}

const TOLERANCE = 1e-6;
const OPTIMAL = 7;

/** Build the model for one horizon; columns are c, d, e (n + 1), then u. */
export function dispatchModel(
  highs: Highs,
  prices: ArrayLike<number>,
  battery: Battery,
  dt = 1,
): ModelData {
  const n = prices.length;
  const power = battery.powerMw;
  const lower = (battery.socMin ?? 0) * battery.energyMwh;
  const upper = (battery.socMax ?? 1) * battery.energyMwh;
  const start = (battery.initialSoc ?? 0.5) * battery.energyMwh;
  const [c, d, e, u] = [0, n, 2 * n, 3 * n + 1];
  const numCols = u + n;
  const cost = new Float64Array(numCols);
  const colLower = new Float64Array(numCols);
  const colUpper = new Float64Array(numCols).fill(power);
  for (let t = 0; t < n; t++) {
    cost[c + t] = -(prices[t] + battery.wear) * dt;
    cost[d + t] = (prices[t] - battery.wear) * dt;
    colUpper[u + t] = 1;
  }
  for (let t = 0; t <= n; t++) {
    colLower[e + t] = lower;
    colUpper[e + t] = upper;
  }
  colLower[e] = colUpper[e] = start;
  // Exactly, not at least: ending fuller would raise every later day's target.
  colLower[e + n] = colUpper[e + n] = start;
  const starts = [0];
  const indices: number[] = [];
  const values: number[] = [];
  const rowLower: number[] = [];
  const rowUpper: number[] = [];
  const row = (cols: number[], coefs: number[], lo: number, hi: number) => {
    indices.push(...cols);
    values.push(...coefs);
    starts.push(indices.length);
    rowLower.push(lo);
    rowUpper.push(hi);
  };
  const inf = highs.infinity;
  for (let t = 0; t < n; t++) {
    row(
      [e + t + 1, e + t, c + t, d + t],
      [1, -1, -battery.etaCharge * dt, dt / battery.etaDischarge],
      0,
      0,
    );
    row([c + t, u + t], [1, -power], -inf, 0);
    row([d + t, u + t], [1, power], -inf, power);
  }
  const integrality = new Int32Array(numCols);
  integrality.fill(1, u);
  return {
    numCols,
    numRows: rowLower.length,
    sense: highs.constants.objectiveSense.maximize,
    colCost: cost,
    colLower,
    colUpper,
    rowLower,
    rowUpper,
    matrix: { format: "csr", numRows: rowLower.length, numCols, starts, indices, values },
    integrality: integrality as unknown as ModelData["integrality"],
  };
}

/** The optimal plan for one day of (forecast) prices. */
export function planDay(
  highs: Highs,
  prices: ArrayLike<number>,
  battery: Battery,
  dt = 1,
): Plan {
  const n = prices.length;
  const model = dispatchModel(highs, prices, battery, dt);
  const solution = highs.withModel(model, (m) => {
    m.options.set({ output_flag: false, mip_rel_gap: 1e-6 });
    m.run();
    if (m.getModelStatus() !== OPTIMAL) throw new Error("no optimal battery plan");
    return Float64Array.from(m.getSolution().colValue);
  });
  const clean = (from: number) =>
    solution.slice(from, from + n).map((v) => (v < TOLERANCE ? 0 : Math.min(v, battery.powerMw)));
  return { charge: clean(0), discharge: clean(n), energy: solution.slice(2 * n, 3 * n + 1) };
}

/** Revenue at actual prices (GBP), before wear, as the backtest reports it. */
export function revenue(plan: Plan, actual: ArrayLike<number>, dt = 1): number {
  let total = 0;
  for (let t = 0; t < plan.charge.length; t++) {
    total += actual[t] * (plan.discharge[t] - plan.charge[t]) * dt;
  }
  return total;
}

/**
 * Revenue less wear on every MWh moved: the quantity the plan maximises, so no plan beats
 * perfect foresight on it (revenue before wear can).
 */
export function afterWear(plan: Plan, actual: ArrayLike<number>, wear: number, dt = 1): number {
  let moved = 0;
  for (let t = 0; t < plan.charge.length; t++) moved += (plan.charge[t] + plan.discharge[t]) * dt;
  return revenue(plan, actual, dt) - wear * moved;
}

/** Revenue each day from planning on `forecast` and settling at `actual` (hourly, whole days). */
export function backtestDays(
  highs: Highs,
  actual: ArrayLike<number>,
  forecast: ArrayLike<number | null>,
  battery: Battery,
  first = 0,
  last?: number,
  net = false,
): (number | null)[] {
  const days = Math.floor(actual.length / 24);
  const out: (number | null)[] = [];
  for (let day = first; day < (last ?? days); day++) {
    const f = Array.prototype.slice.call(forecast, day * 24, day * 24 + 24) as (number | null)[];
    if (f.length < 24 || f.some((v) => v === null || !Number.isFinite(v))) {
      out.push(null);
      continue;
    }
    const plan = planDay(highs, f as number[], battery);
    const settle = Array.prototype.slice.call(actual, day * 24, day * 24 + 24) as number[];
    out.push(net ? afterWear(plan, settle, battery.wear) : revenue(plan, settle));
  }
  return out;
}
