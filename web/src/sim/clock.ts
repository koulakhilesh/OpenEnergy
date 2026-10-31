/** The simulator's clock and its address: pure functions, so they can be tested alone. */
import type { ForecastName } from "../engine/data";
import { dayOfYear, iso, parseDay, PRICE_YEARS } from "../engine/data";

export const SPEEDS = [1, 4, 24];
export const DURATIONS = [1, 2, 4, 8];
const NAMES: ForecastName[] = ["fundamentals", "naive", "perfect"];

export interface Settings {
  year: number;
  /** Hour of the year, from 0. */
  hour: number;
  power: number;
  hours: number;
  efficiency: number;
  wear: number;
  plan: ForecastName;
}

export const DEFAULTS: Settings = {
  year: 2025,
  hour: 19 * 24,
  power: 1,
  hours: 2,
  efficiency: 95,
  wear: 5,
  plan: "fundamentals",
};

/** Read the address; also accepts the Battery Lab's and Grid replay's old queries. */
export function readSettings(params: URLSearchParams): Settings {
  const num = (key: string, fallback: number, lo: number, hi: number) => {
    const value = Number(params.get(key));
    return params.has(key) && Number.isFinite(value) && value >= lo && value <= hi ? value : fallback;
  };
  const date = parseDay(params.get("day") ?? params.get("week"));
  const asked = Number(params.get("year")) || date?.getUTCFullYear() || DEFAULTS.year;
  const year = PRICE_YEARS.includes(asked) ? asked : DEFAULTS.year;
  const day = date && date.getUTCFullYear() === year ? dayOfYear(date) : DEFAULTS.hour / 24;
  const hours = num("h", DEFAULTS.hours, 1, 8);
  const listed = (params.get("plan") ?? "").split(",");
  const plan = NAMES.find((n) => listed.includes(n)) ?? DEFAULTS.plan;
  return {
    year,
    hour: day * 24 + Math.round(num("hour", 0, 0, 23)),
    power: num("mw", DEFAULTS.power, 1, 100),
    hours: DURATIONS.includes(hours) ? hours : DEFAULTS.hours,
    efficiency: num("eff", DEFAULTS.efficiency, 80, 100),
    wear: num("wear", DEFAULTS.wear, 0, 30),
    plan,
  };
}

export function writeSettings(s: Settings): string {
  const date = new Date(Date.UTC(s.year, 0, 1) + Math.floor(s.hour / 24) * 864e5);
  const query = new URLSearchParams({
    day: iso(date),
    hour: String(s.hour % 24),
    mw: String(s.power),
    h: String(s.hours),
    eff: String(s.efficiency),
    wear: String(s.wear),
    plan: s.plan,
  });
  return `/?${query}`;
}

/** The next hour with data, wrapping to the first one at the end of what is published. */
export function advance(hour: number, by: number, playable: number): number {
  if (playable <= 0) return 0;
  return (((hour + by) % playable) + playable) % playable;
}

/** Hours from the start of the year to the end of the last day with a price for every hour. */
export function playableHours(prices: (number | null)[]): number {
  let last = prices.length - 1;
  while (last >= 0 && prices[last] === null) last--;
  return Math.max(0, Math.floor((last + 1) / 24) * 24);
}

export interface Note {
  kind: "negative" | "spike";
  text: string;
}

/** A short note when the hour is worth noticing: a negative price or a spike. */
export function noteFor(price: number | null, day: (number | null)[], hourOfDay: number): Note | null {
  if (price === null) return null;
  if (price < 0) return { kind: "negative", text: `Negative price, −£${Math.abs(price).toFixed(0)}/MWh: a battery is paid to charge.` };
  const known = day.filter((v): v is number => v !== null).sort((a, b) => a - b);
  const median = known.length ? known[Math.floor(known.length / 2)] : price;
  if (price >= Math.max(150, 2 * median)) {
    return {
      kind: "spike",
      text: `Price spike: £${price.toFixed(0)}/MWh at ${String(hourOfDay).padStart(2, "0")}:00, ${(price / median).toFixed(1)}× the day's median.`,
    };
  }
  return null;
}
