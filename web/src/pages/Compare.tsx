import { useMemo } from "react";
import type { Data } from "plotly.js";
import { api, type ResultOut } from "../api/client";
import { Controls } from "../components/Controls";
import { Plot } from "../components/Plot";
import { ResultsTable } from "../components/ResultsTable";
import { powerFrom } from "../format";
import { useLoad } from "../hooks";

const SLOTS = 3;

export function Compare({ params }: { params: URLSearchParams }) {
  const power = powerFrom(params);
  const items = params.getAll("item").slice(0, SLOTS);
  const query = new URLSearchParams({
    hours: params.get("hours") ?? "2",
    forecast: params.get("forecast") ?? "naive_last_week",
    power_mw: String(power),
  });
  items.filter(Boolean).forEach((item) => query.append("item", item));
  const loaded = useLoad(() => api.compare(query), query.toString());
  const selects =
    loaded.state === "done"
      ? Array.from({ length: SLOTS }, (_, n) => (
          <label key={n}>
            Prices {n + 1}{" "}
            <select name="item" defaultValue={items[n] ?? ""}>
              <option value="">none</option>
              {loaded.value.options.map((option) => (
                <option key={option.prices} value={option.prices}>
                  {option.where}
                </option>
              ))}
            </select>{" "}
          </label>
        ))
      : null;
  return (
    <>
      <h1>Compare</h1>
      <Controls action="/compare" params={params} power={power}>
        {selects}
      </Controls>
      {loaded.state === "loading" && <p aria-live="polite">Loading…</p>}
      {loaded.state === "error" && <p role="alert">{loaded.message}</p>}
      {loaded.state === "done" && <Side results={loaded.value.results} power={power} />}
      <p>The address of this page is the comparison: copy it to share.</p>
    </>
  );
}

function Side({ results, power }: { results: ResultOut[]; power: number }) {
  const lines = useMemo(
    (): Data[] =>
      results.map((result) => {
        let total = 0;
        return {
          type: "scatter",
          mode: "lines",
          name: result.request.where,
          x: result.daily.revenue.map((_, i) => i + 1),
          y: result.daily.revenue.map((value) => (total += value * power)),
        };
      }),
    [results, power],
  );
  if (results.length === 0) return <p>Choose up to three to compare.</p>;
  return (
    <>
      <ResultsTable items={results} power={power} />
      <Plot
        data={lines}
        title="Revenue through the year (this plan)"
        xTitle="Day simulated"
        yTitle="Revenue (GBP)"
      />
      {results.map((result) => (
        <p className="answer" key={result.key}>
          {result.text.answer}
        </p>
      ))}
    </>
  );
}
