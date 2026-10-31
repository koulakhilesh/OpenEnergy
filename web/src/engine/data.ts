/** The static data the in-browser pages read (written by scripts/build_app_data.py). */

export interface PriceYear {
  year: number;
  start: string;
  /** GB day-ahead price, GBP/MWh, every UTC hour of the year (null where missing). */
  price: (number | null)[];
  /** OpenEnergy's fundamentals forecast for the same hours. */
  fundamentals: (number | null)[];
  /** The 168 hours before the year, so last week's prices exist from 1 January. */
  before: (number | null)[];
  attribution: string[];
}

export interface MixYear {
  year: number;
  start: string;
  mix: Record<string, (number | null)[]>;
  carbon: (number | null)[];
  attribution: string[];
}

export interface SaturationRow {
  pathway: string;
  year: number;
  battery_scale: number;
  fleet_battery_mw: number;
  firm_added_mw: number;
  lole_hours: number;
  unserved_gwh: number;
  price_mean: number;
  daily_spread: number;
  scarcity_hours: number;
  scarcity_days: number;
  curtailment_twh: number;
  emissions_mt: number;
  revenue_per_mw_year: number;
  scarcity_revenue: number;
  equivalent_firm: number | null;
  /** Full cycles a year: the whole fleet's, and one more battery's. */
  fleet_cycles: number;
  battery_cycles: number;
}

export interface Saturation {
  summary: SaturationRow[];
  years: (SaturationRow & { weather_year: number })[];
  source: string;
}

export const PRICE_YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026];
export const MIX_YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026];
export type ForecastName = "perfect" | "fundamentals" | "naive";
export const FORECASTS: Record<ForecastName, { label: string; colour: string }> = {
  perfect: { label: "Perfect foresight", colour: "--ink" },
  fundamentals: { label: "OpenEnergy forecast", colour: "--blue" },
  naive: { label: "Last week's prices", colour: "--red" },
};

const cache = new Map<string, Promise<unknown>>();

function load<T>(name: string): Promise<T> {
  if (!cache.has(name)) {
    const request = fetch(`/data/${name}`).then((response) => {
      if (!response.ok) throw new Error(`could not load ${name}`);
      return response.json();
    });
    request.catch(() => cache.delete(name));
    cache.set(name, request);
  }
  return cache.get(name) as Promise<T>;
}

export const loadPrices = (year: number) => load<PriceYear>(`prices-${year}.json`);
export const loadMix = (year: number) => load<MixYear>(`mix-${year}.json`);
export const loadSaturation = () => load<Saturation>("saturation.json");

/** Last week's prices for every hour of the year: what the naive plan uses. */
export function naive(data: PriceYear): (number | null)[] {
  const all = data.before.concat(data.price);
  return data.price.map((_, i) => all[i]);
}

export function series(data: PriceYear, name: ForecastName): (number | null)[] {
  if (name === "perfect") return data.price;
  if (name === "fundamentals") return data.fundamentals;
  return naive(data);
}

export const days = (data: { price: unknown[] } | { carbon: unknown[] }) =>
  Math.floor(("price" in data ? data.price : data.carbon).length / 24);

export function day<T>(values: T[], index: number): T[] {
  return values.slice(index * 24, index * 24 + 24);
}

export const complete = (values: (number | null)[]): values is number[] =>
  values.length > 0 && values.every((v) => v !== null && Number.isFinite(v));

export function dateOf(year: number, index: number): Date {
  return new Date(Date.UTC(year, 0, 1 + index));
}

export function dayOfYear(date: Date): number {
  return Math.round((date.getTime() - Date.UTC(date.getUTCFullYear(), 0, 1)) / 864e5);
}

export function label(date: Date, withYear = false): string {
  return date.toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "long",
    ...(withYear ? { year: "numeric" } : {}),
    timeZone: "UTC",
  });
}

export function iso(date: Date): string {
  return date.toISOString().slice(0, 10);
}

/** "2025-01-20" to a UTC date, or null. */
export function parseDay(text: string | null): Date | null {
  if (!text || !/^\d{4}-\d{2}-\d{2}$/.test(text)) return null;
  const date = new Date(`${text}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** Put the page's choices in its address (not when embedded in the docs). */
export function remember(url: string): void {
  if (document.documentElement.dataset.embed !== "true") window.history.replaceState(null, "", url);
}

export function money(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "–";
  const rounded = Math.round(value);
  return (rounded < 0 ? "−£" : "£") + Math.abs(rounded).toLocaleString("en-GB");
}
