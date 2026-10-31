import type { Highs } from "highs";
import { useEffect, useMemo, useState } from "react";
import { Axes, Chart, frame, gapPath, HOUR_TICKS, Legend, nice, pounds } from "../components/Svg";
import { planDay, revenue, type Battery, type Plan } from "../engine/battery";
import {
  complete,
  dateOf,
  day,
  days as dayCount,
  dayOfYear,
  FORECASTS,
  type ForecastName,
  iso,
  label,
  loadPrices,
  money,
  parseDay,
  PRICE_YEARS,
  type PriceYear,
  remember,
  series,
} from "../engine/data";
import { useHighs, useYear } from "../engine/hooks";
import { useLoad } from "../hooks";

const NAMES: ForecastName[] = ["perfect", "fundamentals", "naive"];
const PHRASES: Record<ForecastName, string> = {
  perfect: "perfect foresight",
  fundamentals: "OpenEnergy's forecast",
  naive: "last week's prices",
};
const DURATIONS = [1, 2, 4, 8];

interface Run {
  name: ForecastName;
  forecast: (number | null)[];
  plan: Plan | null;
  revenue: number | null;
}

export function battery(power: number, hours: number, efficiency: number, wear: number): Battery {
  return {
    powerMw: power,
    energyMwh: power * hours,
    etaCharge: efficiency,
    etaDischarge: efficiency,
    wear,
  };
}

export function planRuns(
  highs: Highs | null,
  data: PriceYear | null,
  index: number,
  b: Battery,
  names: ForecastName[],
): { actual: (number | null)[]; runs: Run[]; best: number | null } {
  if (!data) return { actual: [], runs: [], best: null };
  const actual = day(data.price, index);
  const settle = complete(actual) ? actual : null;
  const run = (name: ForecastName): Run => {
    const forecast = day(series(data, name), index);
    if (!highs || !settle || !complete(forecast)) return { name, forecast, plan: null, revenue: null };
    const plan = planDay(highs, forecast, b);
    return { name, forecast, plan, revenue: revenue(plan, settle) };
  };
  const runs = names.map(run);
  const perfect = runs.find((r) => r.name === "perfect") ?? run("perfect");
  return { actual, runs, best: perfect.revenue };
}

function readParams(params: URLSearchParams) {
  const year = Number(params.get("year")) || 2025;
  const date = parseDay(params.get("day"));
  const num = (key: string, fallback: number, lo: number, hi: number) => {
    const value = Number(params.get(key));
    return Number.isFinite(value) && value >= lo && value <= hi && params.has(key) ? value : fallback;
  };
  const plans = (params.get("plan") ?? "perfect,fundamentals,naive")
    .split(",")
    .filter((n): n is ForecastName => NAMES.includes(n as ForecastName));
  return {
    year: PRICE_YEARS.includes(year) ? year : 2025,
    index: date && date.getUTCFullYear() === year ? dayOfYear(date) : 19,
    power: num("mw", 1, 1, 100),
    hours: DURATIONS.includes(num("h", 2, 1, 8)) ? num("h", 2, 1, 8) : 2,
    efficiency: num("eff", 95, 80, 100),
    wear: num("wear", 5, 0, 30),
    plans: plans.length ? plans : NAMES,
  };
}

export function Lab({ params }: { params: URLSearchParams }) {
  const initial = useMemo(() => readParams(params), [params]);
  const [year, setYear] = useState(initial.year);
  const [index, setIndex] = useState(initial.index);
  const [power, setPower] = useState(initial.power);
  const [hours, setHours] = useState(initial.hours);
  const [efficiency, setEfficiency] = useState(initial.efficiency);
  const [wear, setWear] = useState(initial.wear);
  const [chosen, setChosen] = useState<ForecastName[]>(initial.plans);
  const loaded = useLoad(() => loadPrices(year), `prices-${year}`);
  const data = loaded.state === "done" ? loaded.value : null;
  const { highs, failed } = useHighs();
  const b = useMemo(() => battery(power, hours, efficiency / 100, wear), [power, hours, efficiency, wear]);
  const total = data ? dayCount(data) : 365;
  const at = Math.min(index, total - 1);
  const { actual, runs, best } = useMemo(
    () => planRuns(highs, data, at, b, chosen),
    [highs, data, at, b, chosen],
  );
  const forecasts = useMemo(
    () => (data ? Object.fromEntries(NAMES.map((n) => [n, series(data, n)])) : null),
    [data],
  );
  const yearKey = `${year}-${power}-${hours}-${efficiency}-${wear}-${data ? "y" : "n"}`;
  const yearly = useYear(yearKey, data?.price ?? null, forecasts, b);

  useEffect(() => {
    const query = new URLSearchParams({
      year: String(year),
      day: iso(dateOf(year, at)),
      mw: String(power),
      h: String(hours),
      eff: String(efficiency),
      wear: String(wear),
      plan: chosen.join(","),
    });
    remember(`/lab?${query}`);
  }, [year, at, power, hours, efficiency, wear, chosen]);

  const toggle = (name: ForecastName) =>
    setChosen((now) => (now.includes(name) ? now.filter((n) => n !== name) : NAMES.filter((n) => n === name || now.includes(n))));
  const lead = runs.find((r) => r.name === "fundamentals") ?? runs.find((r) => r.name !== "perfect") ?? runs[0];
  const date = dateOf(year, at);

  return (
    <section className="page">
      <p className="kicker">Battery Lab · the optimiser runs in your browser</p>
      <h1>Any day, any battery, any forecast</h1>
      <div className="grid lab">
        <aside className="card controls">
          <h3>Battery</h3>
          <Slider label="Power" value={power} min={1} max={100} unit={`${power} MW`} onChange={setPower} />
          <div className="field">
            <span className="field-label">Duration</span>
            <div className="chips" role="group" aria-label="Duration">
              {DURATIONS.map((h) => (
                <button key={h} type="button" aria-pressed={hours === h} onClick={() => setHours(h)}>
                  {h} h
                </button>
              ))}
            </div>
          </div>
          <Slider
            label="Efficiency, each way"
            value={efficiency}
            min={80}
            max={100}
            unit={`${efficiency}%`}
            onChange={setEfficiency}
          />
          <Slider
            label="Wear cost"
            value={wear}
            min={0}
            max={30}
            unit={`£${wear}/MWh`}
            onChange={setWear}
            help="Charged on every MWh moved in or out: the cost of ageing the cells."
          />
          <h3>Plan with</h3>
          <div className="chips" role="group" aria-label="Forecasts to compare">
            {NAMES.map((name) => (
              <button key={name} type="button" aria-pressed={chosen.includes(name)} onClick={() => toggle(name)}>
                {FORECASTS[name].label}
              </button>
            ))}
          </div>
          <p className="help">
            Each plan is made at noon the day before. Perfect foresight is the most any plan could earn.
          </p>
          <h3>Day</h3>
          <div className="field">
            <div className="row">
              <select aria-label="Year" value={year} onChange={(e) => setYear(Number(e.target.value))}>
                {PRICE_YEARS.map((y) => (
                  <option key={y}>{y}</option>
                ))}
              </select>
              <input
                type="date"
                aria-label="Day"
                value={iso(date)}
                min={`${year}-01-01`}
                max={`${year}-12-31`}
                onChange={(e) => {
                  const picked = parseDay(e.target.value);
                  if (picked && picked.getUTCFullYear() === year) setIndex(dayOfYear(picked));
                }}
              />
            </div>
            <input
              type="range"
              aria-label="Day of the year"
              min={0}
              max={total - 1}
              value={at}
              onChange={(e) => setIndex(Number(e.target.value))}
            />
            <div className="row">
              <button type="button" className="btn ghost" aria-label="Previous day" onClick={() => setIndex(Math.max(0, at - 1))}>
                ←
              </button>
              <button type="button" className="btn ghost" aria-label="Next day" onClick={() => setIndex(Math.min(total - 1, at + 1))}>
                →
              </button>
              <JumpButtons yearly={yearly?.revenue ?? null} onPick={setIndex} />
            </div>
          </div>
        </aside>
        <div className="stack">
          {failed && <p role="alert">This browser cannot run the optimiser (it needs WebAssembly).</p>}
          {loaded.state === "error" && <p role="alert">{loaded.message}</p>}
          <p className="answer" aria-live="polite">
            {!data || !highs ? (
              "Loading prices and the optimiser…"
            ) : !complete(actual) ? (
              <>No prices published for {label(date, true)}.</>
            ) : lead && lead.revenue !== null ? (
              <>
                On <b>{label(date, true)}</b> a {power} MW / {power * hours} MWh battery planning on{" "}
                <b>{PHRASES[lead.name]}</b> earned <b>{money(lead.revenue)}</b>
                {lead.name !== "perfect" && best ? `, ${Math.round((100 * lead.revenue) / best)}% of what perfect foresight allows` : ""}
                .
              </>
            ) : (
              "Pick a forecast to plan with."
            )}
          </p>
          <div className="kpis">
            {runs.map((r) => (
              <div key={r.name} className={`kpi ${r.name}`}>
                <div className="v">{money(r.revenue)}</div>
                <div className="l">{FORECASTS[r.name].label}</div>
              </div>
            ))}
            {complete(actual) && (
              <div className="kpi spread">
                <div className="v">£{(Math.max(...actual) - Math.min(...actual)).toFixed(0)}</div>
                <div className="l">The day's price spread</div>
              </div>
            )}
          </div>
          <div className="card">
            <h3>The day: prices, plans and charge</h3>
            <DayChart actual={actual} runs={runs} b={b} />
          </div>
          <div className="card">
            <h3>The whole year · click a day</h3>
            <YearStrip year={year} yearly={yearly} at={at} onPick={setIndex} />
          </div>
          {data && <p className="source">{data.attribution.join(" ")}</p>}
        </div>
      </div>
    </section>
  );
}

export function Slider(props: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit: string;
  help?: string;
  onChange: (value: number) => void;
}) {
  return (
    <div className="field">
      <label>
        <span className="field-label">
          {props.label} <output>{props.unit}</output>
        </span>
        <input
          type="range"
          min={props.min}
          max={props.max}
          step={props.step ?? 1}
          value={props.value}
          onChange={(e) => props.onChange(Number(e.target.value))}
        />
      </label>
      {props.help && <p className="help">{props.help}</p>}
    </div>
  );
}

function JumpButtons({
  yearly,
  onPick,
}: {
  yearly: Record<string, (number | null)[]> | null;
  onPick: (index: number) => void;
}) {
  const perfect = yearly?.perfect;
  const fundamentals = yearly?.fundamentals;
  if (!perfect || !fundamentals) return null;
  const best = argmax(perfect.map((v) => v ?? -Infinity));
  const missed = argmax(perfect.map((v, i) => (v ?? 0) - (fundamentals[i] ?? Infinity)));
  return (
    <>
      <button type="button" className="btn ghost" onClick={() => onPick(best)} disabled={best < 0}>
        Best day
      </button>
      <button type="button" className="btn ghost" onClick={() => onPick(missed)} disabled={missed < 0}>
        Forecast's worst miss
      </button>
    </>
  );
}

function argmax(values: number[]): number {
  let best = -1;
  values.forEach((v, i) => {
    if (Number.isFinite(v) && (best < 0 || v > values[best])) best = i;
  });
  return best;
}

function DayChart({ actual, runs, b }: { actual: (number | null)[]; runs: Run[]; b: Battery }) {
  const values = [...actual, ...runs.flatMap((r) => r.forecast)].filter(
    (v): v is number => v !== null && Number.isFinite(v),
  );
  if (!values.length) return <div className="chart-empty" />;
  const hi = Math.max(...values) * 1.08;
  const lo = Math.min(0, ...values);
  const top = frame(860, 220, { n: 24, bars: true, lo, hi });
  const bottom = frame(860, 170, { n: 24, bars: true, lo: -b.powerMw * 1.1, hi: b.powerMw * 1.1 });
  const planned = runs.filter((r) => r.plan);
  const slot = (bottom.x(1) - bottom.x(0)) * 0.8;
  const width = slot / Math.max(1, planned.length);
  const fmtPower = (v: number) => (v > 0 ? `buy ${v}` : v < 0 ? `sell ${-v}` : "0");
  return (
    <>
      <Chart width={860} height={390} label="Actual prices, the forecasts and each plan's MW through the day">
        <Axes f={top} yticks={nice(lo, hi)} yfmt={pounds} />
        {runs
          .filter((r) => r.name !== "perfect")
          .map((r) => (
            <path
              key={r.name}
              d={gapPath(r.forecast, (i) => top.x(i + 0.5), top.y)}
              className="line dashed"
              style={{ stroke: `var(${FORECASTS[r.name].colour})` }}
            />
          ))}
        <path d={gapPath(actual, (i) => top.x(i + 0.5), top.y)} className="line thick" style={{ stroke: "var(--ink)" }} />
        <g transform="translate(0,220)">
          <Axes f={bottom} yticks={[-b.powerMw, 0, b.powerMw]} yfmt={fmtPower} xticks={HOUR_TICKS} />
          {planned.map((r, k) =>
            Array.from(r.plan!.charge).map((charge, t) => {
              const mw = charge - r.plan!.discharge[t];
              if (Math.abs(mw) < 1e-6) return null;
              const y0 = bottom.y(0);
              const y1 = bottom.y(mw);
              return (
                <rect
                  key={`${r.name}${t}`}
                  x={bottom.x(t) + (bottom.x(1) - bottom.x(0)) * 0.1 + k * width}
                  y={Math.min(y0, y1)}
                  width={Math.max(1, width - 1)}
                  height={Math.abs(y1 - y0)}
                  style={{ fill: `var(${FORECASTS[r.name].colour})`, opacity: 0.85 }}
                />
              );
            }),
          )}
        </g>
      </Chart>
      <Legend
        items={[
          { label: "Actual price", colour: "var(--ink)" },
          ...runs
            .filter((r) => r.name !== "perfect")
            .map((r) => ({ label: FORECASTS[r.name].label, colour: `var(${FORECASTS[r.name].colour})`, dash: true })),
          { label: "Bars: MW bought (up) and sold (down) by each plan", colour: "var(--muted)" },
        ]}
      />
    </>
  );
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function YearStrip({
  year,
  yearly,
  at,
  onPick,
}: {
  year: number;
  yearly: ReturnType<typeof useYear>;
  at: number;
  onPick: (index: number) => void;
}) {
  if (!yearly) return <p className="help">Solving the year…</p>;
  const perfect = yearly.revenue.perfect ?? [];
  const forecast = yearly.revenue.fundamentals ?? [];
  const n = yearly.total;
  const hi = Math.max(1, ...perfect.map((v) => v ?? 0)) * 1.05;
  const f = frame(860, 150, { n, bars: true, lo: 0, hi, margin: { left: 56 } });
  const width = f.x(1) - f.x(0);
  const ticks: [number, string][] = MONTHS.map((m, i) => [dayOfYear(new Date(Date.UTC(year, i, 15))), m]);
  const sum = (xs: (number | null)[]) => xs.reduce<number>((s, v) => s + (v ?? 0), 0);
  const both = perfect.map((v, i) => (v !== null && forecast[i] !== null ? i : -1)).filter((i) => i >= 0);
  const p = sum(both.map((i) => perfect[i]));
  const share = (name: string) => {
    const values = yearly.revenue[name];
    if (!values || p <= 0) return "";
    return `${money(sum(both.map((i) => values[i])))} (${Math.round((100 * sum(both.map((i) => values[i]))) / p)}%)`;
  };
  return (
    <>
      <Chart
        width={860}
        height={150}
        label={`Revenue by day through ${year}: perfect foresight as bars, the OpenEnergy forecast as a line`}
        className="clickable"
        onPointer={(x, _y, kind) => kind !== "up" && onPick(Math.max(0, Math.min(n - 1, Math.floor((x - f.left) / width))))}
      >
        <Axes f={f} yticks={nice(0, hi, 2)} yfmt={pounds} xticks={ticks} />
        {perfect.map((v, i) =>
          v === null || v <= 0 ? null : (
            <rect key={i} x={f.x(i)} y={f.y(v)} width={width} height={f.y(0) - f.y(v)} style={{ fill: "var(--line-strong)" }} />
          ),
        )}
        <path d={gapPath(forecast.map((v) => (v === null ? null : Math.max(0, v))), (i) => f.x(i + 0.5), f.y)} className="line" style={{ stroke: "var(--blue)" }} />
        <rect x={f.x(at) - 1} y={f.top} width={3} height={f.y(0) - f.top} style={{ fill: "var(--red)" }} />
      </Chart>
      <p className="help" aria-live="polite">
        {yearly.solved < yearly.total
          ? `Solving ${yearly.solved} of ${yearly.total} days…`
          : `${year}: perfect foresight ${money(p)}, OpenEnergy forecast ${share("fundamentals")}, last week's prices ${share("naive")}, on the ${both.length} days all three could plan. ${3 * yearly.total} daily plans solved in ${(yearly.milliseconds / 1000).toFixed(1)} s in this browser.`}
      </p>
    </>
  );
}
