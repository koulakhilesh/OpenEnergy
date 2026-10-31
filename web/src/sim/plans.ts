import type { Highs } from "highs";
import { afterWear, planDay, type Battery, type Plan } from "../engine/battery";
import { complete, day, type ForecastName, type PriceYear, series } from "../engine/data";

export interface Run {
  name: ForecastName;
  forecast: (number | null)[];
  plan: Plan | null;
  /** Revenue at actual prices less wear: what the plan maximises, so perfect foresight is the most. */
  revenue: number | null;
}

export function battery(power: number, hours: number, efficiency: number, wear: number): Battery {
  return {
    powerMw: power,
    energyMwh: power * hours,
    etaCharge: efficiency,
    etaDischarge: efficiency,
    wear,
  };
}

/** Each forecast's plan for one day, settled at that day's actual prices. */
export function planRuns(
  highs: Highs | null,
  data: PriceYear | null,
  index: number,
  b: Battery,
  names: ForecastName[],
): { actual: (number | null)[]; runs: Run[] } {
  if (!data) return { actual: [], runs: [] };
  const actual = day(data.price, index);
  const settle = complete(actual) ? actual : null;
  const runs = names.map((name): Run => {
    const forecast = day(series(data, name), index);
    if (!highs || !settle || !complete(forecast)) return { name, forecast, plan: null, revenue: null };
    const plan = planDay(highs, forecast, b);
    return { name, forecast, plan, revenue: afterWear(plan, settle, b.wear) };
  });
  return { actual, runs };
}

/** Revenue less wear from the start of the day to the end of ``hour``. */
export function revenueTo(plan: Plan, actual: number[], hour: number, wear: number): number {
  let total = 0;
  for (let t = 0; t <= hour; t++) {
    total += actual[t] * (plan.discharge[t] - plan.charge[t]) - wear * (plan.charge[t] + plan.discharge[t]);
  }
  return total;
}
