import { useCallback, useMemo } from "react";
import type { Data } from "plotly.js";
import { api, type Item } from "../api/client";
import { Controls } from "../components/Controls";
import { Plot } from "../components/Plot";
import { ResultsTable } from "../components/ResultsTable";
import { Tip, useOptions } from "../components/Tip";
import { powerFrom, requestParams } from "../format";
import { useLoad } from "../hooks";

export function Explore({ params }: { params: URLSearchParams }) {
  const options = useOptions();
  const power = powerFrom(params);
  const query = new URLSearchParams({
    hours: params.get("hours") ?? "2",
    forecast: params.get("forecast") ?? "naive_last_week",
    services: params.get("services") ?? "none",
  });
  const loaded = useLoad(() => api.explore(query), query.toString());
  const first = options.history_years[0];
  const last = options.history_years[options.history_years.length - 1];
  return (
    <>
      <h1>Battery value at a glance</h1>
      <Controls action="/explore" params={params} power={power} services />
      {loaded.state === "loading" && <p aria-live="polite">Loading…</p>}
      {loaded.state === "error" && <p role="alert">{loaded.message}</p>}
      {loaded.state === "done" && (
        <Charts
          history={loaded.value.history}
          pathways={loaded.value.pathways}
          power={power}
          naive={query.get("forecast") === "naive_last_week"}
          services={query.get("services") ?? "none"}
          heading={`GB, ${first} to ${last}`}
        />
      )}
    </>
  );
}

interface ChartsProps {
  history: Item[];
  pathways: Item[];
  power: number;
  naive: boolean;
  services: string;
  heading: string;
}

function Charts({ history, pathways, power, naive, services, heading }: ChartsProps) {
  const open = useCallback((url: unknown) => {
    if (typeof url === "string" && url.startsWith("/result?")) window.location.href = url;
  }, []);
  const years = useMemo(() => {
    const bars = (name: string, field: "revenue_per_mw_year" | "perfect_per_mw_year"): Data => ({
      type: "bar",
      name,
      x: history.map((x) => x.request.where),
      y: history.map((x) => x.summary[field] * power),
      customdata: history.map((x) => `/result?${requestParams(x.request, power)}`),
      hovertemplate: `%{x}: £%{y:,.0f} a year<extra>${name}</extra>`,
    });
    return naive
      ? [bars("this plan", "revenue_per_mw_year"), bars("perfect foresight", "perfect_per_mw_year")]
      : [bars("this plan", "revenue_per_mw_year")];
  }, [history, power, naive]);
  const forward = useMemo(() => {
    const targets = [...new Set(pathways.map((x) => x.request.year))].sort();
    return targets.map((target): Data => {
      const items = pathways.filter((x) => x.request.year === target);
      return {
        type: "bar",
        name: String(target),
        x: items.map((x) => x.request.pathway ?? ""),
        y: items.map((x) => x.summary.revenue_per_mw_year * power),
        customdata: items.map((x) => `/result?${requestParams(x.request, power)}`),
        hovertemplate: `%{x}: £%{y:,.0f} a year<extra>${target}</extra>`,
      };
    });
  }, [pathways, power]);
  const layout = useMemo(() => ({ barmode: "group" as const }), []);
  const yTitle = `Revenue for ${power} MW (GBP a year)`;
  return (
    <>
      <h2>{heading}</h2>
      {history.length === 0 ? (
        <p>No precomputed results for this choice.</p>
      ) : (
        <Plot
          data={years}
          title="GB day-ahead prices by year (click a bar to open it)"
          yTitle={yTitle}
          layout={layout}
          onClick={open}
        />
      )}
      <ResultsTable items={history} power={power} />
      <h2>
        FES pathways <Tip name="pathway" />
      </h2>
      {services !== "none" && (
        <p>Frequency response is available on historic years only, so pathways show trading alone.</p>
      )}
      <Plot
        data={forward}
        title="FES pathways, modelled prices (click a bar to open it)"
        yTitle={yTitle}
        layout={layout}
        onClick={open}
      />
      <ResultsTable items={pathways} power={power} />
    </>
  );
}
