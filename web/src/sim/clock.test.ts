import { describe, expect, it } from "vitest";
import { advance, noteFor, playableHours, readSettings, writeSettings } from "./clock";

describe("simulator address", () => {
  it("opens on 20 January 2025 by default", () => {
    const s = readSettings(new URLSearchParams(""));
    expect(s.year).toBe(2025);
    expect(s.hour).toBe(19 * 24);
    expect(s.plan).toBe("fundamentals");
  });

  it("round-trips its own address", () => {
    const s = readSettings(new URLSearchParams("day=2024-03-12&hour=17&mw=10&h=4&eff=90&wear=8&plan=naive"));
    expect(s).toMatchObject({ year: 2024, hour: 71 * 24 + 17, power: 10, hours: 4, efficiency: 90, wear: 8, plan: "naive" });
    expect(readSettings(new URLSearchParams(writeSettings(s).slice(2)))).toEqual(s);
  });

  it("reads the Battery Lab's and Grid replay's old queries", () => {
    const lab = readSettings(new URLSearchParams("year=2025&day=2025-01-21&mw=1&h=2&plan=perfect,fundamentals,naive"));
    expect(lab.hour).toBe(20 * 24);
    expect(lab.plan).toBe("fundamentals");
    expect(readSettings(new URLSearchParams("week=2023-06-10")).year).toBe(2023);
  });

  it("ignores values out of range", () => {
    const s = readSettings(new URLSearchParams("year=1990&mw=5000&h=3&eff=10"));
    expect(s).toMatchObject({ year: 2025, power: 1, hours: 2, efficiency: 95 });
  });
});

describe("clock", () => {
  it("wraps within the hours that have prices", () => {
    expect(advance(47, 1, 48)).toBe(0);
    expect(advance(0, -1, 48)).toBe(47);
    expect(advance(10, 24, 48)).toBe(34);
  });

  it("stops at the last whole day with a price", () => {
    const prices = [...new Array(50).fill(40), null, null];
    expect(playableHours(prices)).toBe(48);
  });

  it("notes negative prices and spikes, not ordinary hours", () => {
    const day = Array.from({ length: 24 }, (_, i) => (i === 17 ? 400 : 60));
    expect(noteFor(-5, day, 3)?.kind).toBe("negative");
    expect(noteFor(400, day, 17)?.text).toContain("17:00");
    expect(noteFor(60, day, 9)).toBeNull();
  });
});
