import { useEffect, useMemo, useState } from "react";
import { Axes, Chart, frame, gapPath, Legend, nice, pounds } from "../components/Svg";
import { dateOf, dayOfYear, iso, label, loadMix, loadPrices, MIX_YEARS, parseDay, remember } from "../engine/data";
import { useLoad } from "../hooks";

const FUELS: [string, string, string][] = [
  ["nuclear", "Nuclear", "#7a5195"],
  ["biomass", "Biomass", "#5c8a3a"],
  ["hydro", "Hydro", "#3aa0c8"],
  ["wind", "Wind", "#1961e0"],
  ["solar", "Solar", "#ffc21a"],
  ["imports", "Imports", "#1b9e8a"],
  ["storage", "Storage", "#e8871e"],
  ["gas", "Gas", "#f24333"],
  ["coal", "Coal", "#3b3530"],
  ["other", "Other", "#a39b8f"],
];
const HOURS = 168;
const SPEEDS = [1, 4, 12];

type Week = { start: number; mix: Record<string, number[]>; price: (number | null)[]; carbon: (number | null)[] };

/** Which week of the year (start day) maximises ``score``. */
function pick(total: number, score: (day: number) => number): number {
  let best = 0;
  let value = -Infinity;
  for (let d = 0; d + 7 <= total; d++) {
    const s = score(d);
    if (s > value) {
      value = s;
      best = d;
    }
  }
  return best;
}

const mean = (xs: (number | null)[]) => {
  const v = xs.filter((x): x is number => x !== null);
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : NaN;
};

export function Replay({ params }: { params: URLSearchParams }) {
  const first = parseDay(params.get("week")) ?? new Date(Date.UTC(2025, 0, 18));
  const [year, setYear] = useState(MIX_YEARS.includes(first.getUTCFullYear()) ? first.getUTCFullYear() : 2025);
  const [start, setStart] = useState(dayOfYear(first));
  const [t, setT] = useState(0);
  const [speed, setSpeed] = useState(1);
  const [playing, setPlaying] = useState(false);
  const mix = useLoad(() => loadMix(year), `mix-${year}`);
  const prices = useLoad(() => loadPrices(year), `prices-${year}`);
  const total = mix.state === "done" ? Math.floor(mix.value.carbon.length / 24) : 365;
  const at = Math.min(start, total - 7);

  const week: Week | null = useMemo(() => {
    if (mix.state !== "done" || prices.state !== "done") return null;
    const from = at * 24;
    const slice = <T,>(xs: T[]) => xs.slice(from, from + HOURS);
    return {
      start: at,
      mix: Object.fromEntries(FUELS.map(([k]) => [k, slice(mix.value.mix[k]).map((v) => v ?? 0)])),
      price: slice(prices.value.price),
      carbon: slice(mix.value.carbon),
    };
  }, [mix, prices, at]);

  useEffect(() => {
    remember(`/replay?week=${iso(dateOf(year, at))}`);
  }, [year, at]);

  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(() => setT((now) => (now + 1) % HOURS), 400 / speed);
    return () => clearInterval(timer);
  }, [playing, speed]);

  const presets = useMemo(() => {
    if (mix.state !== "done" || prices.state !== "done") return [];
    const m = mix.value.mix;
    const p = prices.value.price;
    const range = (xs: (number | null)[], d: number) => xs.slice(d * 24, d * 24 + HOURS);
    return [
      { name: "Dearest week", day: pick(total, (d) => mean(range(p, d))) },
      { name: "Windiest week", day: pick(total, (d) => mean(range(m.wind, d))) },
      { name: "Stillest week", day: pick(total, (d) => -mean(range(m.wind, d))) },
      { name: "Cleanest week", day: pick(total, (d) => -mean(range(mix.value.carbon, d))) },
    ];
  }, [mix, prices, total]);

  return (
    <section className="page">
      <p className="kicker">Grid replay · what Britain ran on, hour by hour</p>
      <h1>A week on the grid</h1>
      <p className="lede">
        Press play or drag the slider. Wind and solar come and go; gas, imports and storage fill the gap,
        and the price follows whatever runs last.
      </p>
      <div className="row controls-row">
        <select aria-label="Year" value={year} onChange={(e) => setYear(Number(e.target.value))}>
          {MIX_YEARS.map((y) => (
            <option key={y}>{y}</option>
          ))}
        </select>
        <input
          type="date"
          aria-label="First day of the week"
          value={iso(dateOf(year, at))}
          min={`${year}-01-01`}
          max={iso(dateOf(year, total - 7))}
          onChange={(e) => {
            const d = parseDay(e.target.value);
            if (d && d.getUTCFullYear() === year) setStart(dayOfYear(d));
          }}
        />
        <div className="chips" role="group" aria-label="Find a week">
          {presets.map((p) => (
            <button key={p.name} type="button" aria-pressed={p.day === at} onClick={() => setStart(p.day)}>
              {p.name}
            </button>
          ))}
        </div>
      </div>
      {mix.state === "error" && <p role="alert">{mix.message}</p>}
      {!week ? (
        <p>Loading the week…</p>
      ) : (
        <div className="grid split">
          <div className="card">
            <div className="player">
              <button type="button" className="btn" onClick={() => setPlaying(!playing)}>
                {playing ? "Pause" : "Play"}
              </button>
              <input
                type="range"
                min={0}
                max={HOURS - 1}
                value={t}
                aria-label="Hour of the week"
                onChange={(e) => setT(Number(e.target.value))}
              />
              <div className="chips" role="group" aria-label="Speed">
                {SPEEDS.map((s) => (
                  <button key={s} type="button" aria-pressed={speed === s} onClick={() => setSpeed(s)}>
                    {s}×
                  </button>
                ))}
              </div>
            </div>
            <MixChart week={week} year={year} t={t} onPick={setT} />
            <Legend items={FUELS.map(([, name, colour]) => ({ label: name, colour }))} />
            <PriceChart week={week} t={t} />
            <Legend
              items={[
                { label: "Price £/MWh", colour: "var(--ink)" },
                { label: "Carbon intensity gCO₂/kWh (scaled)", colour: "var(--muted)", dash: true },
              ]}
            />
          </div>
          <Now week={week} year={year} t={t} />
        </div>
      )}
      {mix.state === "done" && prices.state === "done" && (
        <p className="source">{[...mix.value.attribution, prices.value.attribution[0]].join(" ")}</p>
      )}
    </section>
  );
}

function totals(week: Week): number[] {
  return Array.from({ length: HOURS }, (_, i) => FUELS.reduce((s, [k]) => s + week.mix[k][i], 0));
}

function MixChart({ week, year, t, onPick }: { week: Week; year: number; t: number; onPick: (t: number) => void }) {
  const sums = totals(week);
  const hi = Math.max(...sums) * 1.05;
  const f = frame(860, 300, { n: HOURS, lo: 0, hi });
  const ticks: [number, string][] = Array.from({ length: 7 }, (_, i) => [
    i * 24 + 12,
    dateOf(year, week.start + i).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", timeZone: "UTC" }),
  ]);
  let base = new Array<number>(HOURS).fill(0);
  const layers = FUELS.map(([k, , colour]) => {
    const top = base.map((b, i) => b + week.mix[k][i]);
    const points = top.map((v, i) => `${f.x(i).toFixed(1)},${f.y(v).toFixed(1)}`);
    const under = base.map((v, i) => `${f.x(i).toFixed(1)},${f.y(v).toFixed(1)}`).reverse();
    base = top;
    return <path key={k} d={`M${points.join("L")}L${under.join("L")}Z`} style={{ fill: colour, opacity: 0.9 }} />;
  });
  return (
    <Chart
      width={860}
      height={300}
      label="Generation by fuel through the week"
      className="clickable"
      onPointer={(x) => onPick(Math.max(0, Math.min(HOURS - 1, Math.round(((x - f.left) / (f.width - f.left - f.right)) * (HOURS - 1)))))}
    >
      <Axes f={f} yticks={nice(0, hi / 1000, 4).map((v) => v * 1000)} yfmt={(v) => `${v / 1000} GW`} xticks={ticks} />
      {layers}
      <rect x={f.x(t + 1)} y={f.top} width={Math.max(0, f.x(HOURS - 1) - f.x(t + 1))} height={f.y(0) - f.top} style={{ fill: "var(--bg)", opacity: 0.4 }} />
      <line x1={f.x(t)} x2={f.x(t)} y1={f.top} y2={f.y(0)} style={{ stroke: "var(--ink)", strokeWidth: 2 }} />
    </Chart>
  );
}

function PriceChart({ week, t }: { week: Week; t: number }) {
  const values = week.price.filter((v): v is number => v !== null);
  const hi = Math.max(10, ...values) * 1.1;
  const lo = Math.min(0, ...values);
  const f = frame(860, 150, { n: HOURS, lo, hi });
  const carbonMax = Math.max(1, ...week.carbon.filter((v): v is number => v !== null));
  const now = week.price[t];
  return (
    <Chart width={860} height={150} label="Price and carbon intensity through the week">
      <Axes f={f} yticks={nice(lo, hi, 3)} yfmt={pounds} />
      <path
        d={gapPath(week.carbon.map((v) => (v === null ? null : lo + (v / carbonMax) * (hi - lo) * 0.9)), f.x, f.y)}
        className="line dashed"
        style={{ stroke: "var(--muted)" }}
      />
      <path d={gapPath(week.price, f.x, f.y)} className="line" style={{ stroke: "var(--ink)", opacity: 0.25 }} />
      <path d={gapPath(week.price.slice(0, t + 1), f.x, f.y)} className="line thick" style={{ stroke: "var(--ink)" }} />
      {now !== null && <circle cx={f.x(t)} cy={f.y(now)} r={5} style={{ fill: "var(--red)" }} />}
    </Chart>
  );
}

function Now({ week, year, t }: { week: Week; year: number; t: number }) {
  const sums = totals(week);
  const total = sums[t];
  const when = new Date(dateOf(year, week.start).getTime() + t * 36e5);
  const price = week.price[t];
  const share = (k: string) => Math.round((100 * week.mix[k][t]) / total);
  const finite = week.price.map((v) => (v === null ? -Infinity : v));
  const peak = finite.indexOf(Math.max(...finite));
  const windShare = week.mix.wind.map((w, i) => w / sums[i]);
  const calmest = windShare.indexOf(Math.min(...windShare));
  return (
    <aside className="card now-panel" aria-live="polite">
      <h3>
        {label(when)}, {String(when.getUTCHours()).padStart(2, "0")}:00 UTC
      </h3>
      <p className="answer small">
        {price !== null ? (
          <>
            Price <b>£{price.toFixed(0)}</b>/MWh.{" "}
          </>
        ) : null}
        Wind gives <b>{share("wind")}%</b>, gas <b>{share("gas")}%</b> of {(total / 1000).toFixed(1)} GW
        {week.carbon[t] !== null ? `, at ${week.carbon[t]} gCO₂/kWh` : ""}.
      </p>
      <dl>
        {FUELS.filter(([k]) => week.mix[k][t] > 50)
          .sort((a, b) => week.mix[b[0]][t] - week.mix[a[0]][t])
          .map(([k, name, colour]) => (
            <div key={k}>
              <dt>
                <span>{name}</span>
                <span>{(week.mix[k][t] / 1000).toFixed(1)} GW</span>
              </dt>
              <dd>
                <div className="bar" style={{ "--c": colour, width: `${(100 * week.mix[k][t]) / total}%` } as React.CSSProperties} />
              </dd>
            </div>
          ))}
      </dl>
      <div className="event">
        {Math.abs(t - peak) <= 3
          ? `The week's highest price, £${finite[peak].toFixed(0)}/MWh, with wind at ${Math.round(100 * windShare[peak])}% of generation.`
          : Math.abs(t - calmest) <= 3
            ? `The week's calmest hour: wind gives ${Math.round(100 * windShare[calmest])}% of generation.`
            : "Drag across the chart or press play; this panel follows the cursor."}
      </div>
    </aside>
  );
}
