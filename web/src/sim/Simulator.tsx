import { useEffect, useMemo, useRef, useState } from "react";
import { Slider } from "../components/Slider";
import { Axes, Chart, frame, gapPath, HOUR_TICKS, nice, pounds } from "../components/Svg";
import {
  complete,
  dateOf,
  day,
  FORECASTS,
  type ForecastName,
  iso,
  label,
  loadMix,
  loadPrices,
  MIX_YEARS,
  money,
  parseDay,
  PRICE_YEARS,
  dayOfYear,
  remember,
  series,
} from "../engine/data";
import { useHighs, useYear } from "../engine/hooks";
import { useLoad } from "../hooks";
import { advance, DURATIONS, type Note, noteFor, playableHours, readSettings, type Settings, SPEEDS, writeSettings } from "./clock";
import { demandOf, Flow, FUELS } from "./Flow";
import { battery, planRuns, revenueTo, type Run } from "./plans";
import { Sources } from "./Sources";
import { YearStrip } from "./YearStrip";

const NAMES: ForecastName[] = ["perfect", "fundamentals", "naive"];
const PHRASES: Record<ForecastName, string> = {
  perfect: "perfect foresight",
  fundamentals: "OpenEnergy's forecast",
  naive: "last week's prices",
};
const reducedMotion = () =>
  typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
const two = (n: number) => String(n).padStart(2, "0");

/** The simulator: Britain's grid hour by hour, with a battery trading on a forecast. */
export function Simulator({ params, embedded }: { params: URLSearchParams; embedded: boolean }) {
  const [s, setS] = useState<Settings>(() => readSettings(params));
  const fresh = !params.has("day") && !params.has("hour") && !params.has("week");
  const [playing, setPlaying] = useState(() => fresh && !embedded && !reducedMotion());
  const [speed, setSpeed] = useState(4);
  const [drawer, setDrawer] = useState(() => !embedded && (typeof window === "undefined" || window.innerWidth > 1100));
  const [note, setNote] = useState<Note | null>(null);
  const noted = useRef(-1);
  const noteTimer = useRef<number | undefined>(undefined);

  const prices = useLoad(() => loadPrices(s.year), `prices-${s.year}`);
  const mixes = useLoad(
    () => (MIX_YEARS.includes(s.year) ? loadMix(s.year) : Promise.reject(new Error("no mix"))),
    `mix-${s.year}`,
  );
  const data = prices.state === "done" ? prices.value : null;
  const mixData = mixes.state === "done" ? mixes.value : null;
  const { highs, failed } = useHighs();
  const b = useMemo(() => battery(s.power, s.hours, s.efficiency / 100, s.wear), [s.power, s.hours, s.efficiency, s.wear]);
  const playable = data ? playableHours(data.price) : 0;
  const hour = playable ? Math.min(s.hour, playable - 1) : s.hour;
  const dayIndex = Math.floor(hour / 24);
  const h = hour % 24;
  const date = dateOf(s.year, dayIndex);

  const { actual, runs } = useMemo(() => planRuns(highs, data, dayIndex, b, NAMES), [highs, data, dayIndex, b]);
  const run = runs.find((r) => r.name === s.plan);
  const perfect = runs.find((r) => r.name === "perfect");
  const forecasts = useMemo(() => (data ? Object.fromEntries(NAMES.map((n) => [n, series(data, n)])) : null), [data]);
  const yearly = useYear(`${s.year}-${s.power}-${s.hours}-${s.efficiency}-${s.wear}-${data ? "y" : "n"}`, data?.price ?? null, forecasts, b);

  const fuels = useMemo(
    () => FUELS.filter(([key]) => key !== "coal" || (mixData?.mix.coal ?? []).some((v) => (v ?? 0) >= 100)),
    [mixData],
  );
  const mix = useMemo(() => {
    if (!mixData) return null;
    const now = Object.fromEntries(FUELS.map(([key]) => [key, mixData.mix[key]?.[hour] ?? null]));
    return Object.values(now).some((v) => v !== null) ? now : null;
  }, [mixData, hour]);

  const update = (change: Partial<Settings>) => setS((now) => ({ ...now, ...change }));
  const seek = (to: number) => update({ hour: advance(to, 0, playable || 8760) });

  // The clock: one hour per tick.
  useEffect(() => {
    if (!playing || !playable) return;
    const timer = setInterval(() => setS((now) => ({ ...now, hour: advance(now.hour, 1, playable) })), 1000 / speed);
    return () => clearInterval(timer);
  }, [playing, speed, playable]);

  // Notes on spikes and negative prices while playing, at most one a day.
  useEffect(() => {
    if (!playing || !data || noted.current === dayIndex) return;
    const found = noteFor(data.price[hour], day(data.price, dayIndex), h);
    if (!found) return;
    noted.current = dayIndex;
    setNote(found);
    window.clearTimeout(noteTimer.current);
    noteTimer.current = window.setTimeout(() => setNote(null), 2500);
  }, [playing, data, hour, dayIndex, h]);
  useEffect(() => () => window.clearTimeout(noteTimer.current), []);

  // The address changes only when paused (browsers limit how often it may change).
  useEffect(() => {
    if (!playing) remember(writeSettings({ ...s, hour }));
  }, [playing, s, hour]);

  useEffect(() => {
    const keys = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (["INPUT", "SELECT", "TEXTAREA", "BUTTON", "A", "SUMMARY"].includes(target.tagName)) return;
      if (event.code === "Space") {
        event.preventDefault();
        setPlaying((p) => !p);
      } else if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
        event.preventDefault();
        const by = (event.key === "ArrowRight" ? 1 : -1) * (event.shiftKey ? 24 : 1);
        setS((now) => ({ ...now, hour: advance(now.hour, by, playable || 8760) }));
      }
    };
    window.addEventListener("keydown", keys);
    return () => window.removeEventListener("keydown", keys);
  }, [playable]);

  const plan = run?.plan ?? null;
  const settle = complete(actual) ? actual : null;
  const gridMw = plan ? plan.charge[h] - plan.discharge[h] : 0;
  const stored = plan ? plan.energy[h + 1] / b.energyMwh : 0.5;
  const price = data?.price[hour] ?? null;
  const total = mix ? demandOf(mix) : 0;
  const carbon = mixData?.carbon[hour] ?? null;
  const action = gridMw > 1e-6 ? "charging" : gridMw < -1e-6 ? "discharging" : "idle";

  return (
    <div className={`sim ${drawer ? "" : "closed"} ${embedded ? "embedded" : ""}`}>
      <section className="stage" aria-label="Simulator">
        <div className="hud">
          <div>
            <h1 className="clock">
              {label(date, true)} · {two(h)}:00
            </h1>
            <p className="help">UTC · GB day-ahead market · hour by hour</p>
          </div>
          <div className="hud-kpis">
            <Kpi value={price === null ? "–" : money(price)} label="£/MWh now" />
            <Kpi value={mix ? (total / 1000).toFixed(1) : "–"} label="GW demand" />
            <Kpi value={carbon === null ? "–" : String(Math.round(carbon))} label="gCO₂/kWh" />
            <Kpi value={mix && total ? `${Math.round((100 * (mix.wind ?? 0)) / total)}%` : "–"} label="wind share" />
          </div>
          <button type="button" className="btn ghost small" aria-expanded={drawer} aria-controls="sim-drawer" onClick={() => setDrawer(!drawer)}>
            Battery ⚙
          </button>
        </div>
        <div className="stage-main">
          <Flow fuels={fuels} mix={mix} price={price} battery={gridMw} stored={stored} hourLabel={`${label(date, true)} ${two(h)}:00`} />
          <aside className="stage-side">
            <div className="card tank-card">
              <div className="row spread">
                <h3>Your battery</h3>
                <span className={`pill ${action}`}>{action}</span>
              </div>
              <div className="tank" role="meter" aria-label="Stored energy" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(stored * 100)}>
                <div className="tank-fill" style={{ width: `${stored * 100}%` }} />
                <span>{Math.round(stored * 100)}%</span>
              </div>
              <dl className="facts">
                <dt>Earned so far today</dt>
                <dd>{plan && settle ? money(revenueTo(plan, settle, h, b.wear)) : "–"}</dd>
                <dt>{FORECASTS[s.plan].label}, whole day</dt>
                <dd>{money(run?.revenue)}</dd>
                {s.plan !== "perfect" && (
                  <>
                    <dt>Perfect foresight, whole day</dt>
                    <dd>{money(perfect?.revenue)}</dd>
                  </>
                )}
              </dl>
              <p className="answer small" aria-live="polite">
                {failed
                  ? "This browser cannot run the optimiser (it needs WebAssembly)."
                  : !data || !highs
                    ? "Loading prices and the optimiser…"
                    : !settle
                      ? `No prices published for ${label(date, true)}.`
                      : run?.revenue != null
                        ? `On ${label(date, true)} a ${s.power} MW / ${s.power * s.hours} MWh battery planning on ${PHRASES[s.plan]} earned ${money(run.revenue)} after wear${
                            s.plan !== "perfect" && perfect?.revenue ? `, ${Math.round((100 * run.revenue) / perfect.revenue)}% of what perfect foresight allows` : ""
                          }.`
                        : "No forecast for this day."}
              </p>
            </div>
            <div className="card">
              <h3>Today's prices and plan</h3>
              <DayChart actual={actual} run={run} hour={h} powerMw={b.powerMw} onPick={(t) => seek(dayIndex * 24 + t)} />
            </div>
          </aside>
        </div>
        <p className={`note ${note ? "on" : ""} ${note?.kind ?? ""}`} role="status" aria-live="polite">
          {note?.text ?? ""}
        </p>
      </section>

      <aside className="drawer" id="sim-drawer" aria-label="Battery and day" hidden={!drawer}>
        <h3>Battery</h3>
        <Slider label="Power" value={s.power} min={1} max={100} unit={`${s.power} MW`} onChange={(v) => update({ power: v })} />
        <div className="field">
          <span className="field-label">Duration</span>
          <div className="chips" role="group" aria-label="Duration">
            {DURATIONS.map((d) => (
              <button key={d} type="button" aria-pressed={s.hours === d} onClick={() => update({ hours: d })}>
                {d} h
              </button>
            ))}
          </div>
        </div>
        <Slider label="Efficiency, each way" value={s.efficiency} min={80} max={100} unit={`${s.efficiency}%`} onChange={(v) => update({ efficiency: v })} />
        <Slider
          label="Wear cost"
          value={s.wear}
          min={0}
          max={30}
          unit={`£${s.wear}/MWh`}
          onChange={(v) => update({ wear: v })}
          help="Charged on every MWh moved in or out: the cost of ageing the cells."
        />
        <h3>Plan with</h3>
        <div className="chips" role="group" aria-label="Forecast the battery plans with">
          {(["fundamentals", "naive", "perfect"] as ForecastName[]).map((name) => (
            <button key={name} type="button" aria-pressed={s.plan === name} onClick={() => update({ plan: name })}>
              {FORECASTS[name].label}
            </button>
          ))}
        </div>
        <p className="help">
          Each plan is made at noon the day before and paid the prices that cleared.{" "}
          <a href="https://koulakhilesh.github.io/OpenEnergy/concepts/">How it works</a>
        </p>
        <TodayTable runs={runs} />
        <h3>Day</h3>
        <div className="row">
          <select aria-label="Year" value={s.year} onChange={(e) => update({ year: Number(e.target.value), hour: hour % (365 * 24) })}>
            {PRICE_YEARS.map((y) => (
              <option key={y}>{y}</option>
            ))}
          </select>
          <input
            type="date"
            aria-label="Day"
            value={iso(date)}
            min={`${s.year}-01-01`}
            max={`${s.year}-12-31`}
            onChange={(e) => {
              const picked = parseDay(e.target.value);
              if (picked && picked.getUTCFullYear() === s.year) seek(dayOfYear(picked) * 24 + h);
            }}
          />
        </div>
        <YearSummary year={s.year} yearly={yearly} onPick={(d) => seek(d * 24 + h)} />
        <Sources texts={[...(data?.attribution ?? []), ...(mixData?.attribution ?? [])]} />
      </aside>

      <footer className="timeline" aria-label="Timeline">
        <div className="transport">
          <button type="button" className="play" aria-label={playing ? "Pause" : "Play"} onClick={() => setPlaying(!playing)}>
            {playing ? "❚❚" : "▶"}
          </button>
          <button type="button" className="btn ghost small" aria-label="Back one hour" onClick={() => seek(hour - 1)}>
            ⟨
          </button>
          <button type="button" className="btn ghost small" aria-label="Forward one hour" onClick={() => seek(hour + 1)}>
            ⟩
          </button>
          <div className="chips small" role="group" aria-label="Speed">
            {SPEEDS.map((v) => (
              <button key={v} type="button" aria-pressed={speed === v} onClick={() => setSpeed(v)}>
                {v}×
              </button>
            ))}
          </div>
          <span className="keys">space play · ←/→ hour · shift day</span>
        </div>
        <div className="tracks">
          <span className="help">{s.year} · daily price spread · click a day</span>
          {data ? <YearStrip year={s.year} prices={data.price} at={dayIndex} onPick={(d) => seek(d * 24 + h)} /> : <div className="year-strip" />}
          <span className="help">Hour</span>
          <input
            type="range"
            aria-label="Hour of the year"
            min={0}
            max={Math.max(0, (playable || 8760) - 1)}
            value={hour}
            onChange={(e) => seek(Number(e.target.value))}
          />
        </div>
      </footer>
    </div>
  );
}

function Kpi({ value, label: text }: { value: string; label: string }) {
  return (
    <div className="hud-kpi">
      <span className="v">{value}</span>
      <span className="l">{text}</span>
    </div>
  );
}

function TodayTable({ runs }: { runs: Run[] }) {
  const best = runs.find((r) => r.name === "perfect")?.revenue;
  return (
    <dl className="facts" aria-label="Today's revenue by forecast">
      {runs.map((r) => (
        <div key={r.name} className="fact-row">
          <dt>{FORECASTS[r.name].label}</dt>
          <dd>
            {money(r.revenue)}
            {r.name !== "perfect" && best && r.revenue !== null ? ` · ${Math.round((100 * r.revenue) / best)}%` : ""}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function DayChart({
  actual,
  run,
  hour,
  powerMw,
  onPick,
}: {
  actual: (number | null)[];
  run: Run | undefined;
  hour: number;
  powerMw: number;
  onPick: (hour: number) => void;
}) {
  const forecast = run && run.name !== "perfect" ? run.forecast : [];
  const values = [...actual, ...forecast].filter((v): v is number => v !== null && Number.isFinite(v));
  if (!values.length) return <div className="chart-empty" />;
  const hi = Math.max(...values) * 1.08 || 1;
  const lo = Math.min(0, ...values);
  const f = frame(340, 150, { n: 24, bars: true, lo, hi, margin: { left: 44, bottom: 8 } });
  const band = frame(340, 70, { n: 24, bars: true, lo: -powerMw * 1.1, hi: powerMw * 1.1, margin: { left: 44, top: 4 } });
  const plan = run?.plan;
  return (
    <Chart
      width={340}
      height={220}
      label="Today's actual prices, the forecast and the battery's plan; click an hour to go there"
      className="clickable"
      onPointer={(x, _y, kind) => kind !== "up" && onPick(Math.max(0, Math.min(23, Math.floor((x - f.left) / ((f.width - f.left - f.right) / 24)))))}
    >
      <Axes f={f} yticks={nice(lo, hi, 3)} yfmt={pounds} />
      {forecast.length > 0 && <path d={gapPath(forecast, (i) => f.x(i + 0.5), f.y)} className="line dashed" style={{ stroke: "var(--blue)" }} />}
      <path d={gapPath(actual, (i) => f.x(i + 0.5), f.y)} className="line thick" style={{ stroke: "var(--ink)" }} />
      <g transform="translate(0,150)">
        <Axes f={band} yticks={[0]} yfmt={() => ""} xticks={HOUR_TICKS} />
        {plan &&
          Array.from(plan.charge).map((c, t) => {
            const mw = c - plan.discharge[t];
            if (Math.abs(mw) < 1e-6) return null;
            const y0 = band.y(0);
            const y1 = band.y(-mw);
            return (
              <rect
                key={t}
                x={band.x(t) + 1}
                y={Math.min(y0, y1)}
                width={band.x(1) - band.x(0) - 2}
                height={Math.abs(y1 - y0)}
                style={{ fill: mw > 0 ? "var(--blue)" : "var(--red)", opacity: t <= hour ? 0.95 : 0.35 }}
              />
            );
          })}
        <text x={4} y={band.y(powerMw * 0.6)} className="band-label">
          sell
        </text>
        <text x={4} y={band.y(-powerMw * 0.9)} className="band-label">
          buy
        </text>
      </g>
      <line x1={f.x(hour + 0.5)} x2={f.x(hour + 0.5)} y1={f.top} y2={206} style={{ stroke: "var(--red)", strokeWidth: 1.5 }} />
      {actual[hour] !== null && <circle cx={f.x(hour + 0.5)} cy={f.y(actual[hour]!)} r={4} style={{ fill: "var(--red)" }} />}
    </Chart>
  );
}

function YearSummary({
  year,
  yearly,
  onPick,
}: {
  year: number;
  yearly: ReturnType<typeof useYear>;
  onPick: (day: number) => void;
}) {
  if (!yearly) return null;
  const perfect = yearly.revenue.perfect ?? [];
  const forecast = yearly.revenue.fundamentals ?? [];
  const both = perfect.map((v, i) => (v !== null && forecast[i] !== null ? i : -1)).filter((i) => i >= 0);
  const sum = (xs: (number | null)[]) => both.reduce((t, i) => t + (xs[i] ?? 0), 0);
  const p = sum(perfect);
  const share = (name: string) => {
    const values = yearly.revenue[name];
    if (!values || p <= 0) return "–";
    return `${money(sum(values))} (${Math.round((100 * sum(values)) / p)}%)`;
  };
  const best = argmax(perfect.map((v) => v ?? -Infinity));
  const missed = argmax(perfect.map((v, i) => (v ?? 0) - (forecast[i] ?? Infinity)));
  return (
    <div className="year-summary">
      <h3>The whole of {year}</h3>
      {yearly.solved < yearly.total ? (
        <p className="help" aria-live="polite">
          Solving {yearly.solved} of {yearly.total} days…
        </p>
      ) : (
        <>
          <dl className="facts">
            <dt>Perfect foresight</dt>
            <dd>{money(p)}</dd>
            <dt>OpenEnergy forecast</dt>
            <dd>{share("fundamentals")}</dd>
            <dt>Last week's prices</dt>
            <dd>{share("naive")}</dd>
          </dl>
          <p className="help">
            On the {both.length} days all three could plan, after wear. {3 * yearly.total} daily plans solved in{" "}
            {(yearly.milliseconds / 1000).toFixed(1)} s in this browser.
          </p>
          <div className="row">
            <button type="button" className="btn ghost small" disabled={best < 0} onClick={() => onPick(best)}>
              Best day
            </button>
            <button type="button" className="btn ghost small" disabled={missed < 0} onClick={() => onPick(missed)}>
              Forecast's worst miss
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function argmax(values: number[]): number {
  let best = -1;
  values.forEach((v, i) => {
    if (Number.isFinite(v) && (best < 0 || v > values[best])) best = i;
  });
  return best;
}
