import type { RequestOut } from "./api/client";

/** Pounds to three significant figures, e.g. £29,000 or £6,300 (as the API's sentences). */
export function money(value: number): string {
  if (value === 0 || !Number.isFinite(value)) return "£0";
  const magnitude = Math.floor(Math.log10(Math.abs(value)));
  const step = 10 ** (magnitude - 2);
  const rounded = Math.round(value / step) * step;
  return `£${Math.round(rounded).toLocaleString("en-GB")}`;
}

export const percent = (value: number) => `${Math.round(value * 100)}%`;

/** Query parameters that reproduce a request for ``power`` MW. */
export function requestParams(request: RequestOut, power: number): URLSearchParams {
  const params = new URLSearchParams({
    source: request.source,
    hours: String(request.hours),
    forecast: request.forecast,
    services: request.services,
    power_mw: String(power),
  });
  if (request.source === "history") params.set("year", String(request.year));
  else {
    params.set("pathway", request.pathway ?? "");
    params.set("target", String(request.year));
  }
  return params;
}

/** A positive power in MW from the URL, else 1. */
export function powerFrom(params: URLSearchParams): number {
  const power = Number(params.get("power_mw") ?? "1");
  return Number.isFinite(power) && power > 0 ? power : 1;
}

export const FORECASTS: Record<string, string> = {
  naive_last_week: "last week's prices",
  perfect_foresight: "perfect foresight",
};
