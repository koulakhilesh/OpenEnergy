import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

const OPTIONS = {
  version: "5.0.0",
  history_years: [2024, 2025],
  response_from: 2022,
  pathways: ["Falling Behind"],
  scenario_years: [2030, 2035],
  precomputed_hours: [1, 2, 4],
  hours_range: [0.5, 8],
  power_range: [0.1, 1000],
  forecasts: { naive_last_week: "last week's prices", perfect_foresight: "perfect foresight" },
  services: { none: "none", dc: "Dynamic Containment" },
  help: { power: "Revenue scales with it.", pathway: "Not a forecast." },
  docs_url: "https://koulakhilesh.github.io/OpenEnergy/",
};

function serve(routes: Record<string, { status: number; body: unknown }>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const route = routes[String(url).split("?")[0]] ?? { status: 404, body: {} };
      return new Response(JSON.stringify(route.body), { status: route.status });
    }),
  );
}

const PRICES = {
  year: 2025,
  start: "2025-01-01T00:00:00Z",
  price: Array.from({ length: 365 * 24 }, (_, i) => 50 + 30 * Math.sin((i % 24) / 3)),
  fundamentals: Array.from({ length: 365 * 24 }, (_, i) => 50 + 25 * Math.sin((i % 24) / 3)),
  before: new Array(168).fill(50),
  attribution: ["GB day-ahead prices: Ember, CC BY 4.0."],
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("opens the simulator without needing the API", async () => {
    serve({ "/data/prices-2025.json": { status: 200, body: PRICES } });
    render(<App path="/" search="" />);
    expect(screen.getByRole("heading", { name: /20 January 2025 · 00:00/ })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Simulator" }).getAttribute("aria-current")).toBe("page");
    expect(await screen.findByText(/Ember, CC BY 4\.0/)).toBeTruthy();
  });

  it("keeps the Battery Lab's address working", () => {
    serve({ "/data/prices-2025.json": { status: 200, body: PRICES } });
    render(<App path="/lab" search="?year=2025&day=2025-01-21" />);
    expect(screen.getByRole("heading", { name: /21 January 2025/ })).toBeTruthy();
  });

  it("marks Research for the analyst pages", async () => {
    serve({ "/api/options": { status: 200, body: OPTIONS } });
    render(<App path="/run" search="" />);
    expect(await screen.findByRole("heading", { name: "Value a battery" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Research" }).getAttribute("aria-current")).toBe("page");
  });

  it("offers the API's years and pathways on the year form", async () => {
    serve({ "/api/options": { status: 200, body: OPTIONS } });
    render(<App path="/run" search="" />);
    expect(await screen.findByRole("heading", { name: "Value a battery" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "Falling Behind" })).toBeTruthy();
    expect(screen.getByText(/OpenEnergy 5\.0\.0/)).toBeTruthy();
  });

  it("shows the API's message when a run cannot go ahead", async () => {
    serve({
      "/api/options": { status: 200, body: OPTIONS },
      "/api/result": { status: 400, body: { error: "Frequency response needs a year from 2022." } },
    });
    render(<App path="/result" search="?year=2019&services=dc" />);
    expect((await screen.findByRole("alert")).textContent).toBe(
      "Frequency response needs a year from 2022.",
    );
  });

  it("does not show unexpected error text", async () => {
    serve({
      "/api/options": { status: 200, body: OPTIONS },
      "/api/scenarios": { status: 500, body: { detail: "Traceback /secret/path" } },
    });
    render(<App path="/scenarios" search="" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).not.toContain("secret");
  });
});
