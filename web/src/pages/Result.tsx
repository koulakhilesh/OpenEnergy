import { useMemo } from "react";
import type { Data } from "plotly.js";
import { api, type ResultOut } from "../api/client";
import { Plot } from "../components/Plot";
import { Tip, useOptions } from "../components/Tip";
import { money, percent, powerFrom, requestParams } from "../format";
import { useElapsed, useLoad } from "../hooks";

export function ResultPage({ params }: { params: URLSearchParams }) {
  const power = powerFrom(params);
  const query = new URLSearchParams(params);
  query.set("power_mw", String(power));
  const loaded = useLoad(() => api.result(query), query.toString());
  const seconds = useElapsed(loaded.state === "loading");
  if (loaded.state === "loading") {
    return (
      <>
        <h1>Battery value</h1>
        <p aria-live="polite">
          Running the backtest and its perfect-foresight benchmark: {seconds} s (1, 2 and 4 hour
          batteries answer at once; others usually take 15 to 45 s).
        </p>
      </>
    );
  }
  if (loaded.state === "error") {
    return (
      <>
        <h1>Cannot run</h1>
        <p role="alert">{loaded.message}</p>
        <p>
          <a href="/">Choose again</a>
        </p>
      </>
    );
  }
  return (
    <>
      <h1>
        {power} MW, {loaded.value.label}
      </h1>
      <ResultBody result={loaded.value} power={power} />
    </>
  );
}

export function ResultBody({ result, power }: { result: ResultOut; power: number }) {
  const options = useOptions();
  const s = result.summary;
  const r = result.request;
  const charts = useMemo(() => revenueCharts(result, power), [result, power]);
  const params = requestParams(r, power).toString();
  const shared = new URLSearchParams({
    hours: String(r.hours),
    forecast: r.forecast,
    power_mw: String(power),
  });
  const numbers: [string, string, string | null][] = [
    ["Revenue per MW-year", money(s.revenue_per_mw_year), null],
    ["Perfect foresight per MW-year", money(s.perfect_per_mw_year), "perfect"],
    ["Share of perfect foresight", percent(s.capture_ratio), "share"],
    ["Cycles per day", s.cycles_per_day.toFixed(2), "cycles"],
    ["Average spread captured", `£${s.captured_spread.toFixed(2)}/MWh`, "spread"],
    ["Days simulated", String(s.days), null],
  ];
  return (
    <>
      <p className="answer">{result.text.answer}</p>
      <div className="cards">
        {numbers.map(([name, value, help]) => (
          <div className="card" key={name}>
            <div className="value">{value}</div>
            <div>
              {name} {help && <Tip name={help} />}
            </div>
          </div>
        ))}
      </div>
      <Plot
        data={charts.cumulative}
        title="Cumulative revenue"
        xTitle="Date"
        yTitle="Revenue (GBP)"
      />
      <Plot data={charts.monthly} title="Revenue by month" xTitle="Month" yTitle="Revenue (GBP)" />
      <details open>
        <summary>What this assumes</summary>
        <ul>
          {result.text.assumptions.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </details>
      <p className="actions">
        {options.precomputed_hours.includes(r.hours) && (
          <>
            <a href={`/explore?${new URLSearchParams([...shared, ["services", r.services]])}`}>
              Every year and pathway
            </a>
            <a href={`/compare?${new URLSearchParams([...shared, ["item", r.prices]])}`}>
              Compare with others
            </a>
          </>
        )}
        <a href={`/download/daily.csv?${params}`}>Daily revenue (CSV)</a>
        <a href={`/download/scenario.yaml?${params}`}>Scenario to run yourself (YAML)</a>
        <a href={`/battery?${params}`}>Full hourly report (runs now, 15 to 45 s)</a>
      </p>
      <p className="source">{result.text.sources}</p>
    </>
  );
}

function revenueCharts(result: ResultOut, power: number): { cumulative: Data[]; monthly: Data[] } {
  const { date, revenue, benchmark_revenue } = result.daily;
  const cumulative = (values: number[]) => {
    let total = 0;
    return values.map((value) => (total += value * power));
  };
  const months = new Map<string, number>();
  date.forEach((day, i) => {
    const month = day.slice(0, 7);
    months.set(month, (months.get(month) ?? 0) + revenue[i] * power);
  });
  return {
    cumulative: [
      { x: date, y: cumulative(revenue), type: "scatter", mode: "lines", name: "this plan" },
      {
        x: date,
        y: cumulative(benchmark_revenue),
        type: "scatter",
        mode: "lines",
        name: "perfect foresight",
      },
    ],
    monthly: [{ x: [...months.keys()], y: [...months.values()], type: "bar", name: "revenue" }],
  };
}
