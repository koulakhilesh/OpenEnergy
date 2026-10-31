import highsLoader from "highs";
import { describe, expect, it } from "vitest";
import { backtestDays, planDay } from "./battery";
import parity from "./engine-parity.json";

// One month of 2025 planned by the Python backtest (scripts/build_app_data.py) and here.
const battery = parity.battery;
const sum = (xs: (number | null)[]) => xs.reduce<number>((s, v) => s + (v ?? 0), 0);

describe("browser engine", async () => {
  const highs = await highsLoader();

  it("earns what the Python backtest earns, day by day", () => {
    for (const [name, forecast] of Object.entries(parity.forecast)) {
      const days = backtestDays(highs, parity.price, forecast, battery);
      const python = parity.revenue[name as keyof typeof parity.revenue];
      expect(days).toHaveLength(python.length);
      // Where forecast prices tie, two plans are equally good on the forecast and can
      // settle a little differently (one January day of last week's prices, by 0.05%).
      days.forEach((v, i) => expect(Math.abs((v ?? 0) - python[i])).toBeLessThan(1e-3 * sum(python)));
      expect(Math.abs(sum(days) / sum(python) - 1)).toBeLessThan(0.001);
    }
  });

  it("ends the day where it started and never charges and discharges at once", () => {
    const prices = [-20, -10, 5, 40, 120, 30, -5, 200];
    const plan = planDay(highs, prices, battery);
    expect(plan.energy[0]).toBeCloseTo(1, 9);
    expect(plan.energy[prices.length]).toBeCloseTo(1, 9);
    plan.charge.forEach((c, t) => expect(c * plan.discharge[t]).toBe(0));
    expect(Math.max(...plan.discharge)).toBeLessThanOrEqual(battery.powerMw);
  });

  it("skips days without a full forecast", () => {
    const forecast = parity.forecast.perfect.slice(0, 48).map((v, i) => (i === 30 ? null : v));
    const days = backtestDays(highs, parity.price.slice(0, 48), forecast, battery);
    expect(days[0]).not.toBeNull();
    expect(days[1]).toBeNull();
  });
});
