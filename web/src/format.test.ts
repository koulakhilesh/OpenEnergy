import { describe, expect, it } from "vitest";
import type { RequestOut } from "./api/client";
import { money, percent, powerFrom, requestParams } from "./format";

describe("money", () => {
  it("rounds to three significant figures like the API's sentences", () => {
    expect(money(29039.2)).toBe("£29,000");
    expect(money(290392)).toBe("£290,000");
    expect(money(6312)).toBe("£6,310");
    expect(money(0)).toBe("£0");
    expect(money(Number.NaN)).toBe("£0");
  });
});

describe("requests", () => {
  const history: RequestOut = {
    source: "history",
    year: 2024,
    pathway: null,
    hours: 2,
    forecast: "naive_last_week",
    services: "dc",
    key: "gb-2024-2h-naive_last_week-dc",
    prices: "gb-2024-dc",
    where: "GB 2024 + DC",
    label: "2 h battery, GB 2024",
  };

  it("builds query parameters that reproduce a result", () => {
    const params = requestParams(history, 10);
    expect(params.get("year")).toBe("2024");
    expect(params.get("services")).toBe("dc");
    expect(params.get("power_mw")).toBe("10");
    const pathway = requestParams(
      { ...history, source: "scenario", year: 2030, pathway: "Falling Behind", services: "none" },
      1,
    );
    expect(pathway.get("target")).toBe("2030");
    expect(pathway.get("pathway")).toBe("Falling Behind");
    expect(pathway.has("year")).toBe(false);
  });

  it("reads a positive power from the URL", () => {
    expect(powerFrom(new URLSearchParams("power_mw=5"))).toBe(5);
    expect(powerFrom(new URLSearchParams("power_mw=-1"))).toBe(1);
    expect(powerFrom(new URLSearchParams("power_mw=abc"))).toBe(1);
    expect(powerFrom(new URLSearchParams(""))).toBe(1);
    expect(percent(0.739)).toBe("74%");
  });
});
