import { useEffect, useMemo, useState } from "react";
import { Axes, Chart, frame, gapPath, HOUR_TICKS, Legend, nice, pounds } from "../components/Svg";
import { planDay, revenue, type Battery } from "../engine/battery";
import { complete, dateOf, day, dayOfYear, iso, label, loadPrices, money, parseDay, remember } from "../engine/data";
import { useHighs } from "../engine/hooks";
import { useLoad } from "../hooks";

// A lossless 1 MW / 2 MWh battery keeps the arithmetic simple: each tap moves 1 MWh.
const GAME: Battery = { powerMw: 1, energyMwh: 2, etaCharge: 1, etaDischarge: 1, wear: 5 };
const YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025];

/** Today's challenge: the same day for everyone, from London's date. */
export function challenge(now = new Date()): Date {
  const london = new Date(now.toLocaleString("en-US", { timeZone: "Europe/London" }));
  const seed = Math.floor(Date.UTC(london.getFullYear(), london.getMonth(), london.getDate()) / 864e5);
  const year = YEARS[seed % YEARS.length];
  return dateOf(year, 7 + ((seed * 97) % 350));
}

const stored = (acts: number[]) => acts.reduce<number[]>((e, a) => [...e, e[e.length - 1] + a], [1]);

export function score(acts: number[], prices: number[]): number {
  return acts.reduce((s, a, t) => s - prices[t] * a - GAME.wear * Math.abs(a), 0);
}

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
  const [done, setDone] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    setActs(new Array(24).fill(0));
    setDone(false);
    setMessage("");
    remember(`/play?d=${iso(date)}`);
  }, [date]);

  const data = loaded.state === "done" ? loaded.value : null;
  const forecast = data ? day(data.fundamentals, index) : [];
  const actual = data ? day(data.price, index) : [];
  const ready = complete(forecast) && complete(actual);
  const energy = stored(acts);

  const result = useMemo(() => {
    if (!done || !highs || !complete(forecast) || !complete(actual)) return null;
    const optimiser = planDay(highs, forecast, GAME);
    const perfect = planDay(highs, actual, GAME);
    const net = (p: typeof optimiser) => {
      let moved = 0;
      for (let t = 0; t < 24; t++) moved += p.charge[t] + p.discharge[t];
      return revenue(p, actual) - GAME.wear * moved;
    };
    return { you: score(acts, actual), optimiser: net(optimiser), perfect: net(perfect) };
  }, [done, highs, forecast, actual, acts]);

  const tap = (t: number) => {
    const current = acts[t];
    const order = current === 0 ? [1, -1, 0] : current === 1 ? [-1, 0] : [0];
    for (const next of order) {
      const trial = acts.slice();
      trial[t] = next;
      if (stored(trial).every((e) => e >= 0 && e <= GAME.energyMwh)) {
        setActs(trial);
        setMessage("");
        return;
      }
    }
    setMessage("The battery is full or empty there.");
  };

  const lockIn = () => {
    if (energy[24] !== 1) {
      setMessage("End the day half full (1 MWh), as it started.");
      return;
    }
    setDone(true);
  };

  const shown = done ? [...forecast, ...actual] : forecast;
  const values = shown.filter((v): v is number => v !== null);
  const hi = values.length ? Math.max(...values) * 1.1 : 100;
  const lo = values.length ? Math.min(0, ...values) : 0;
  const f = frame(860, 220, { n: 24, bars: true, lo, hi });
  const s = frame(860, 80, { n: 25, lo: 0, hi: 2 });
  const verdict =
    result &&
    (result.you > result.optimiser + 0.5
      ? "You beat the optimiser."
      : result.you > 0.9 * result.optimiser
        ? "Close to the optimiser."
        : "The optimiser wins this one.");

  return (
    <section className="page">
      <p className="kicker">Beat the battery · a new day every day</p>
      <h1>Plan tomorrow. Then see what really happened.</h1>
      <p className="lede">
        You see OpenEnergy's forecast the day before, as the optimiser does. Tap each hour to charge, sell or
        rest. Your 1 MW / 2 MWh battery starts half full and must end the day half full.
      </p>
      <div className="card">
        <div className="row spread">
          <b>{label(date, true)}</b>
          <span className="help">Tap cycles: rest → charge → sell. Wear costs £5 per MWh moved.</span>
        </div>
        {!ready ? (
          <p>{loaded.state === "error" ? loaded.message : "Loading the day…"}</p>
        ) : (
          <>
            <Chart width={860} height={220} label="Forecast prices for the day, and actual prices once you lock in">
              <Axes f={f} yticks={nice(lo, hi, 5)} yfmt={pounds} xticks={HOUR_TICKS} />
              <path d={gapPath(forecast, (i) => f.x(i + 0.5), f.y)} className="line thick dashed" style={{ stroke: "var(--blue)" }} />
              {done && <path d={gapPath(actual, (i) => f.x(i + 0.5), f.y)} className="line thick" style={{ stroke: "var(--ink)" }} />}
            </Chart>
            <Legend
              items={[
                { label: "Forecast", colour: "var(--blue)", dash: true },
                ...(done ? [{ label: "What prices really were", colour: "var(--ink)" }] : []),
              ]}
            />
            <div className="cells" role="group" aria-label="Your plan, hour by hour">
              {acts.map((a, t) => (
                <button
                  key={t}
                  type="button"
                  className={a > 0 ? "charge" : a < 0 ? "discharge" : ""}
                  aria-label={`${String(t).padStart(2, "0")}:00 ${a > 0 ? "charge" : a < 0 ? "sell" : "rest"}`}
                  disabled={done}
                  onClick={() => tap(t)}
                >
                  {String(t).padStart(2, "0")}
                  <br />
                  {a > 0 ? "buy" : a < 0 ? "sell" : "·"}
                </button>
              ))}
            </div>
            <Chart width={860} height={80} label="Energy stored through your plan">
              <Axes f={s} yticks={[0, 2]} yfmt={(v) => `${v} MWh`} />
              <path
                d={`M${energy.map((e, t) => `${s.x(t).toFixed(1)},${s.y(e).toFixed(1)}`).join("L")}L${s.x(24)},${s.y(0)}L${s.x(0)},${s.y(0)}Z`}
                style={{ fill: "var(--yellow)", opacity: 0.6 }}
              />
            </Chart>
            <div className="row">
              <button type="button" className="btn red" onClick={lockIn} disabled={done}>
                Lock in my plan
              </button>
              <button type="button" className="btn ghost" onClick={() => setActs(new Array(24).fill(0))} disabled={done}>
                Clear
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
              <span className="help" role="status">
                {message}
              </span>
            </div>
          </>
        )}
      </div>
      {result && (
        <div className="scoreboard">
          <div className="kpi you">
            <div className="v">{money(result.you)}</div>
            <div className="l">You</div>
          </div>
          <div className="kpi fundamentals">
            <div className="v">{money(result.optimiser)}</div>
            <div className="l">Optimiser, same forecast</div>
          </div>
          <div className="kpi">
            <div className="v">{money(result.perfect)}</div>
            <div className="l">Perfect foresight</div>
          </div>
          <div className="kpi naive">
            <div className="v small">{verdict}</div>
            <div className="l">
              <button
                type="button"
                className="link"
                onClick={() =>
                  navigator.clipboard?.writeText(
                    `OpenEnergy · Beat the battery, ${iso(date)}: me ${money(result.you)}, optimiser ${money(result.optimiser)}. ${window.location.origin}/play?d=${iso(date)}`,
                  )
                }
              >
                Copy a link to this day
              </button>
            </div>
          </div>
        </div>
      )}
      {data && <p className="source">{data.attribution.join(" ")}</p>}
    </section>
  );
}
