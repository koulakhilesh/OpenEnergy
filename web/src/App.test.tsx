import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { LIVE_URL } from "./sim/Live";

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

  it("compares the real battery fleet with the optimiser", async () => {
    const year = {
      year: 2025,
      units: 40,
      mw_years: 1500,
      discharge_hours: 400,
      round_trip: 0.85,
      real_metered_day_ahead_per_mw_year: 4000,
      real_pn_day_ahead_per_mw_year: 18000,
      real_imbalance_per_mw_year: -7000,
      real_estimated_total_per_mw_year: 20000,
      repd_battery_mw: 3000,
      real_bm_net_per_mw_year: 9000,
      model_1h_naive_per_mw_year: 30000,
      model_1h_fundamentals_per_mw_year: 33000,
      model_1h_perfect_per_mw_year: 38000,
      model_2h_perfect_per_mw_year: 60000,
    };
    const unit = { unit: "E_AB-1", name: "A Battery", zone: "scotland", mw: 50, year: 2025, days: 300, dischargeHours: 420, dayAheadPerMwYear: 21000, bmPerMwYear: 8000, totalPerMwYear: 19000 };
    serve({
      "/data/fleet-units.json": { status: 200, body: { units: [unit], years: [year], attribution: ["Elexon BMRS."] } },
      "/data/fleet-2025.json": { status: 200, body: { year: 2025, start: "", net: new Array(48).fill(10), units: new Array(48).fill(3), attribution: [] } },
      "/data/prices-2025.json": { status: 200, body: PRICES },
    });
    render(<App path="/fleet" search="" />);
    expect((await screen.findByText(/battery units ran/)).textContent).toContain("£20,000");
    expect(screen.getByRole("cell", { name: "A Battery" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Real batteries" }).getAttribute("aria-current")).toBe("page");
  });

  it("shows tomorrow's forecast and its track record", async () => {
    const forecast = Array.from({ length: 24 }, (_, h) => 60 + (h === 18 ? 60 : h === 3 ? -30 : 0));
    serve({
      [LIVE_URL]: {
        status: 200,
        body: {
          day: "2026-11-03",
          issued: "2026-11-02T09:40:00Z",
          pricesKnownUntil: "2026-10-31T00:00:00Z",
          start: "2026-11-03T00:00:00Z",
          forecast,
          planMw: forecast.map((v) => (v > 100 ? 1 : v < 40 ? -1 : 0)),
          stretch: 1.5,
          track: [
            { day: "2026-10-30", mae: 12.3, earned: 80, perfect: 100, catchUp: false },
            { day: "2026-10-31", mae: 20.1, earned: 50, perfect: 100, catchUp: true },
          ],
          summary: { days: 1, mae: 12.3, capture: 0.8 },
          sinceStart: { days: 3, mae: 15, capture: 0.75, from: "2026-10-28" },
          note: "Fundamentals forecast.",
          attribution: ["Ember, CC BY 4.0."],
        },
      },
    });
    render(<App path="/live" search="" />);
    const answer = await screen.findByText(/forecasts GB day-ahead prices/);
    expect(answer.textContent).toContain("Tue 3 November");
    expect(answer.textContent).toContain("£120");
    const record = screen.getByText(/perfect foresight\./).textContent;
    expect(record).toContain("Over the last day with");
    expect(record).toContain("80%");
    expect(record).toContain("Since it started on Wed 28 October (3 days)");
    expect(record).toContain("75%");
    expect(screen.getByRole("cell", { name: /31 October \(caught up\)/ })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Tomorrow" }).getAttribute("aria-current")).toBe("page");
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
