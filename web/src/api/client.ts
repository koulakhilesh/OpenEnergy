import type { components } from "./schema";

export type Options = components["schemas"]["Options"];
export type RequestOut = components["schemas"]["RequestOut"];
export type Summary = components["schemas"]["Summary"];
export type ResultOut = components["schemas"]["ResultOut"];
export type Item = components["schemas"]["Item"];
export type Explore = components["schemas"]["Explore"];
export type Compare = components["schemas"]["Compare"];
export type Scenarios = components["schemas"]["Scenarios"];

/** A message from the API that is safe to show, or a fixed fallback. */
export class ApiError extends Error {}

const FAILED = "The request could not be completed. Please try again.";

export async function get<T>(path: string, params?: URLSearchParams): Promise<T> {
  const url = params && params.size > 0 ? `${path}?${params}` : path;
  let response: Response;
  try {
    response = await fetch(url, { headers: { Accept: "application/json" } });
  } catch {
    throw new ApiError(FAILED);
  }
  if (response.ok) return (await response.json()) as T;
  const body = (await response.json().catch(() => null)) as { error?: unknown } | null;
  throw new ApiError(typeof body?.error === "string" ? body.error : FAILED);
}

export const api = {
  options: () => get<Options>("/api/options"),
  result: (params: URLSearchParams) => get<ResultOut>("/api/result", params),
  explore: (params: URLSearchParams) => get<Explore>("/api/explore", params),
  compare: (params: URLSearchParams) => get<Compare>("/api/compare", params),
  scenarios: () => get<Scenarios>("/api/scenarios"),
};
