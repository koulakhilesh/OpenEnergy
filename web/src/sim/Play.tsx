import { useEffect, useMemo, useRef, useState } from "react";
import { Axes, Chart, frame, gapPath, HOUR_TICKS, Legend, nice, pounds } from "../components/Svg";
import { planDay, type Battery, type Plan } from "../engine/battery";
import { complete, dateOf, day, dayOfYear, iso, label, loadPrices, money, parseDay, remember } from "../engine/data";
import { useHighs } from "../engine/hooks";
import { useLoad } from "../hooks";
import { Sources } from "./Sources";

// A lossless 1 MW / 2 MWh battery keeps the arithmetic simple: each hour moves 1 MWh.
// Like the engine, it starts half full and must end the day half full.
const GAME: Battery = { powerMw: 1, energyMwh: 2, etaCharge: 1, etaDischarge: 1, wear: 5 };
const YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025];

/** Today's challenge: the same day for everyone, from London's date. */
export function challenge(now = new Date()): Date {
  const london = new Date(now.toLocaleString("en-US", { timeZone: "Europe/London" }));
  const seed = Math.floor(Date.UTC(london.getFullYear(), london.getMonth(), london.getDate()) / 864e5);
  const year = YEARS[seed % YEARS.length];
  return dateOf(year, 7 + ((seed * 97) % 350));
}

export const stored = (acts: number[]) => acts.reduce<number[]>((e, a) => [...e, e[e.length - 1] + a], [1]);
const fits = (acts: number[]) => stored(acts).every((e) => e >= 0 && e <= GAME.energyMwh);

/** Cash at actual prices after wear, running total hour by hour. */
export function cashBy(acts: ArrayLike<number>, prices: number[]): number[] {
  let total = 0;
  return prices.map((p, t) => (total += -p * acts[t] - GAME.wear * Math.abs(acts[t])));
}

const net = (plan: Plan) => Array.from(plan.charge, (c, t) => c - plan.discharge[t]);
const WORDS: Record<number, string> = { 1: "charge", [-1]: "sell", 0: "rest" };

export function Play({ params }: { params: URLSearchParams }) {
  const [date, setDate] = useState(() => {
    const asked = parseDay(params.get("d"));
    return asked && YEARS.includes(asked.getUTCFullYear()) ? asked : challenge();
  });
  const year = date.getUTCFullYear();
  const index = dayOfYear(date);
  const loaded = useLoad(() => loadPrices(year), `prices-${year}`);
  const { highs } = useHighs();
  const [acts, setActs] = useState<number[]>(new Array(24).fill(0));
  const [revealed, setRevealed] = useState(-1);
  const [showBot, setShowBot] = useState(false);
  const [message, setMessage] = useState("");
  const paint = useRef<number | null>(null);

  useEffect(() => {
    setActs(new Array(24).fill(0));
    setRevealed(-1);
    setShowBot(false);
    setMessage("");
    remember(`/play?d=${iso(date)}`);
  }, [date]);

  const data = loaded.state === "done" ? loaded.value : null;
  const forecast = useMemo(() => (data ? day(data.fundamentals, index) : []), [data, index]);
  const actual = useMemo(() => (data ? day(data.price, index) : []), [data, index]);
  const ready = complete(forecast) && complete(actual);
  const energy = stored(acts);
  const running = revealed >= 0 && revealed < 23;
  const done = revealed >= 23;

  const plans = useMemo(() => {
    if (!highs || !complete(forecast) || !complete(actual)) return null;
    return { optimiser: net(planDay(highs, forecast, GAME)), perfect: net(planDay(highs, actual, GAME)) };
  }, [highs, forecast, actual]);

  useEffect(() => {
    if (!running) return;
    const timer = setTimeout(() => setRevealed((r) => r + 1), 110);
    return () => clearTimeout(timer);
  }, [running, revealed]);

  const set = (t: number, value: number) => {
    if (acts[t] === value) return;
    const trial = acts.slice();
    trial[t] = value;
    if (fits(trial)) setActs(trial);
  };
  // A tap cycles rest -> charge -> sell, skipping what would overfill or empty the battery.
  const tap = (t: number) => {
    const current = acts[t];
    const order = current === 0 ? [1, -1, 0] : current === 1 ? [-1, 0] : [0];
    for (const next of order) {
      const trial = acts.slice();
      trial[t] = next;
      if (fits(trial)) {
        setActs(trial);
        setMessage("");
        return next;
      }
    }
    setMessage("The battery is full or empty there.");
    return current;
  };
  const cellAt = (x: number, y: number) => {
    const found = document.elementFromPoint?.(x, y)?.closest<HTMLElement>("[data-hour]");
    return found ? Number(found.dataset.hour) : null;
  };

  const run = () => {
    if (energy[24] !== 1) {
      setMessage("End the day half full (1 MWh), as it started.");
      return;
    }
    setMessage("");
    setRevealed(0);
  };

  const settled = actual as number[];
  const you = ready ? cashBy(acts, settled) : [];
  const bot = ready && plans ? cashBy(plans.optimiser, settled) : [];
  const best = ready && plans ? cashBy(plans.perfect, settled) : [];
  const at = Math.min(Math.max(revealed, 0), 23);
  const shownActual = actual.map((v, t) => (t <= revealed ? v : null));
  const values = [...forecast, ...(revealed >= 0 ? actual : [])].filter((v): v is number => v !== null);
  const hi = values.length ? Math.max(...values) * 1.1 : 100;
  const lo = values.length ? Math.min(0, ...values) : 0;
  const f = frame(960, 240, { n: 24, bars: true, lo, hi });
  const s = frame(960, 70, { n: 25, lo: 0, hi: 2 });
  const verdict = !done
    ? ""
    : you[23] > bot[23] + 0.5
      ? "You beat the optimiser."
      : you[23] > 0.9 * bot[23]
        ? "Close to the optimiser."
        : "The optimiser wins this one.";

  return (
    <section className="lens">
      <div className="lens-head">
        <div>
          <p className="kicker">Play · beat the battery · a new day every day</p>
          <h1>Plan {label(date, true)}</h1>
          <p className="lede">
            It is noon the day before. You see OpenEnergy's forecast, as the optimiser does. Tap or drag across the
            hours to charge or sell. The battery starts half full and must end half full.
          </p>
        </div>
        {revealed >= 0 && plans && (
          <div className="scoreboard" aria-live="polite">
            <div className="kpi you">
              <div className="v">{money(you[at])}</div>
              <div className="l">You</div>
            </div>
            <div className="kpi fundamentals">
              <div className="v">{money(bot[at])}</div>
              <div className="l">Optimiser, same forecast</div>
            </div>
            <div className="kpi">
              <div className="v">{money(best[at])}</div>
              <div className="l">Perfect foresight</div>
            </div>
          </div>
        )}
      </div>
      {!ready ? (
        <p>{loaded.state === "error" ? loaded.message : "Loading the day…"}</p>
      ) : (
        <div className="card">
          <Chart width={960} height={240} label="Forecast prices for the day, and actual prices as the day runs">
            <Axes f={f} yticks={nice(lo, hi, 5)} yfmt={pounds} xticks={HOUR_TICKS} />
            {acts.map((a, t) =>
              a === 0 ? null : (
                <rect
                  key={t}
                  x={f.x(t) + 2}
                  y={f.top}
                  width={f.x(1) - f.x(0) - 4}
                  height={f.y(lo) - f.top}
                  style={{ fill: a > 0 ? "var(--blue)" : "var(--red)", opacity: 0.14 }}
                />
              ),
            )}
            <path d={gapPath(forecast, (i) => f.x(i + 0.5), f.y)} className="line thick dashed" style={{ stroke: "var(--blue)" }} />
            {revealed >= 0 && (
              <path d={gapPath(shownActual, (i) => f.x(i + 0.5), f.y)} className="line thick" style={{ stroke: "var(--ink)" }} />
            )}
            {running && (
              <line x1={f.x(revealed + 1)} x2={f.x(revealed + 1)} y1={f.top} y2={f.y(lo)} style={{ stroke: "var(--red)", strokeWidth: 2 }} />
            )}
          </Chart>
          <Legend
            items={[
              { label: "Forecast", colour: "var(--blue)", dash: true },
              ...(revealed >= 0 ? [{ label: "What prices really were", colour: "var(--ink)" }] : []),
              { label: "Charge", colour: "var(--blue)" },
              { label: "Sell", colour: "var(--red)" },
              ...(showBot ? [{ label: "Outline: the optimiser's plan", colour: "var(--line-strong)" }] : []),
            ]}
          />
          <div
            className="cells"
            role="group"
            aria-label="Your plan, hour by hour"
            onPointerDown={(e) => {
              const t = cellAt(e.clientX, e.clientY);
              if (t === null || revealed >= 0) return;
              (e.target as HTMLElement).releasePointerCapture?.(e.pointerId);
              paint.current = tap(t);
            }}
            onPointerMove={(e) => {
              if (paint.current === null || e.buttons === 0) return;
              const t = cellAt(e.clientX, e.clientY);
              if (t !== null) set(t, paint.current);
            }}
            onPointerUp={() => (paint.current = null)}
            onPointerLeave={() => (paint.current = null)}
          >
            {acts.map((a, t) => {
              const o = plans?.optimiser[t] ?? 0;
              const hint = showBot && Math.abs(o) > 1e-6 ? (o > 0 ? "bot-charge" : "bot-sell") : "";
              return (
                <button
                  key={t}
                  type="button"
                  data-hour={t}
                  className={`${a > 0 ? "charge" : a < 0 ? "discharge" : ""} ${hint}`}
                  aria-label={`${String(t).padStart(2, "0")}:00 ${WORDS[a]}`}
                  disabled={revealed >= 0}
                  // Pointer taps are handled on the group (so a drag paints); keyboard clicks have no detail.
                  onClick={(e) => e.detail === 0 && tap(t)}
                >
                  {String(t).padStart(2, "0")}
                  <br />
                  {a > 0 ? "buy" : a < 0 ? "sell" : "·"}
                </button>
              );
            })}
          </div>
          <Chart width={960} height={70} label="Energy stored through your plan">
            <Axes f={s} yticks={[0, 1, 2]} yfmt={(v) => `${v} MWh`} />
            <path
              d={`M${energy.map((e, t) => `${s.x(t).toFixed(1)},${s.y(e).toFixed(1)}`).join("L")}L${s.x(24)},${s.y(0)}L${s.x(0)},${s.y(0)}Z`}
              style={{ fill: "var(--green)", opacity: 0.55 }}
            />
          </Chart>
          <div className="row">
            <button type="button" className="btn red" onClick={run} disabled={revealed >= 0}>
              Run the day ▶
            </button>
            <button type="button" className="btn ghost" onClick={() => setActs(new Array(24).fill(0))} disabled={revealed >= 0}>
              Clear
            </button>
            <button type="button" className="btn ghost" aria-pressed={showBot} onClick={() => setShowBot(!showBot)} disabled={!plans}>
              {showBot ? "Hide" : "Show"} the optimiser's plan
            </button>
            <button
              type="button"
              className="btn ghost"
              onClick={() => {
                const y = YEARS[Math.floor(Math.random() * YEARS.length)];
                setDate(dateOf(y, 7 + Math.floor(Math.random() * 350)));
              }}
            >
              Another day
            </button>
            {done && (
              <button type="button" className="btn ghost" onClick={() => setRevealed(-1)}>
                Change my plan
              </button>
            )}
            <span className="help" role="status">
              {message || verdict}
            </span>
          </div>
          {done && (
            <p className="help">
              <button
                type="button"
                className="link"
                onClick={() =>
                  navigator.clipboard?.writeText(
                    `OpenEnergy · Beat the battery, ${iso(date)}: me ${money(you[23])}, optimiser ${money(bot[23])}. ${window.location.origin}/play?d=${iso(date)}`,
                  )
                }
              >
                Copy a link to this day
              </button>
            </p>
          )}
        </div>
      )}
      <Sources texts={data?.attribution ?? []} />
    </section>
  );
}
