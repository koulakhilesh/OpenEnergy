import { useEffect, useMemo, useState } from "react";
import { Axes, Chart, frame, gapPath, HOUR_TICKS, Legend, nice, pounds } from "../components/Svg";
import { planDay, revenue } from "../engine/battery";
import { complete, dateOf, day, days, iso, label, loadPrices, money } from "../engine/data";
import { useHighs } from "../engine/hooks";
import { useLoad } from "../hooks";
import { battery } from "./Lab";

const YEAR = 2025;
const B = battery(1, 2, 0.95, 5);
const reduced = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** The landing page: a real day traded hour by hour, then the ways in. */
export function Home() {
  const loaded = useLoad(() => loadPrices(YEAR), `prices-${YEAR}`);
  const data = loaded.state === "done" ? loaded.value : null;
  const { highs } = useHighs();
  const [index, setIndex] = useState(20);
  const [hour, setHour] = useState(0);
  const [playing, setPlaying] = useState(!reduced());

  const today = useMemo(() => {
    if (!data || !highs) return null;
    const actual = day(data.price, index);
    const forecast = day(data.fundamentals, index);
    if (!complete(actual) || !complete(forecast)) return null;
    return { actual, forecast, plan: planDay(highs, forecast, B) };
  }, [data, highs, index]);

  useEffect(() => {
    if (!playing || !data) return;
    const timer = setInterval(() => {
      setHour((h) => {
        if (h < 23) return h + 1;
        setIndex((i) => (i + 1) % days(data));
        return 0;
      });
    }, 700);
    return () => clearInterval(timer);
  }, [playing, data]);

  const earned = today
    ? revenue(
        {
          ...today.plan,
          charge: today.plan.charge.slice(0, hour + 1),
          discharge: today.plan.discharge.slice(0, hour + 1),
        },
        today.actual,
      )
    : 0;
  const stored = today ? today.plan.energy[hour + 1] / B.energyMwh : 0.5;
  const hi = today ? Math.max(...today.actual, ...today.forecast) * 1.1 : 100;
  const lo = today ? Math.min(0, ...today.actual) : 0;
  const f = frame(520, 260, { n: 24, bars: true, lo, hi });
  const date = dateOf(YEAR, index);

  return (
    <section className="page">
      <div className="hero">
        <div>
          <p className="kicker">OpenEnergy · open models of Britain's power market</p>
          <h1>Watch a battery trade a real day on Britain's grid.</h1>
          <p className="lede">
            This is <b>{label(date, true)}</b>. A 1 MW battery buys when power is cheap and sells when it
            is dear. It plans the day before on OpenEnergy's forecast and is paid the prices that actually
            cleared.
          </p>
          <div className="row">
            <a className="btn red" href={`/lab?year=${YEAR}&day=${iso(date)}`}>
              Try your own battery
            </a>
            <button
              type="button"
              className="btn ghost"
              aria-pressed={playing}
              onClick={() => setPlaying(!playing)}
            >
              {playing ? "Pause" : "Play"}
            </button>
            <button
              type="button"
              className="btn ghost"
              onClick={() => {
                setIndex(7 + Math.floor(Math.random() * 350));
                setHour(0);
              }}
            >
              Another day
            </button>
          </div>
        </div>
        <div className="card live">
          <div>
            <Chart width={520} height={260} label="The day's prices, with the battery's plan as bars">
              <Axes f={f} yticks={nice(lo, hi)} yfmt={pounds} xticks={HOUR_TICKS} />
              {today &&
                Array.from(today.plan.charge).map((c, t) => {
                  const mw = c - today.plan.discharge[t];
                  if (Math.abs(mw) < 1e-6) return null;
                  const h = Math.abs(mw) * (hi - lo) * 0.25;
                  return (
                    <rect
                      key={t}
                      x={f.x(t + 0.15)}
                      y={f.y(lo + h)}
                      width={f.x(0.7) - f.x(0)}
                      height={f.y(lo) - f.y(lo + h)}
                      style={{
                        fill: mw > 0 ? "var(--blue)" : "var(--red)",
                        opacity: t <= hour ? 0.9 : 0.25,
                      }}
                    />
                  );
                })}
              {today && (
                <>
                  <path
                    d={gapPath(today.forecast, (i) => f.x(i + 0.5), f.y)}
                    className="line dashed"
                    style={{ stroke: "var(--muted)" }}
                  />
                  <path
                    d={gapPath(today.actual, (i) => f.x(i + 0.5), f.y)}
                    className="line thick"
                    style={{ stroke: "var(--ink)" }}
                  />
                  <line
                    x1={f.x(hour + 0.5)}
                    x2={f.x(hour + 0.5)}
                    y1={f.top}
                    y2={f.y(lo)}
                    style={{ stroke: "var(--red)", strokeWidth: 2 }}
                  />
                  <circle
                    cx={f.x(hour + 0.5)}
                    cy={f.y(today.actual[hour])}
                    r={6}
                    style={{ fill: "var(--red)" }}
                  />
                </>
              )}
            </Chart>
            <Legend
              items={[
                { label: "Price (£/MWh)", colour: "var(--ink)" },
                { label: "Forecast", colour: "var(--muted)", dash: true },
                { label: "Buying", colour: "var(--blue)" },
                { label: "Selling", colour: "var(--red)" },
              ]}
            />
          </div>
          <div className="meter">
            <div className="batt" aria-hidden="true">
              <div className="fill" style={{ height: `calc(${Math.round(stored * 100)}% - 12px)` }} />
            </div>
            <div className="counter" aria-live="polite">
              {money(earned)}
            </div>
            <div className="tick">
              {String(hour).padStart(2, "0")}:00 UTC
              {today ? ` · £${today.actual[hour].toFixed(0)}/MWh` : ""}
            </div>
          </div>
        </div>
      </div>
      <div className="tiles">
        <Tile
          href="/lab"
          title="Battery Lab"
          text="Any day since 2019, any battery, three forecasts. The optimiser runs in your browser."
          icon="lab"
        />
        <Tile
          href="/replay"
          title="Grid replay"
          text="Scrub a week of wind, gas, imports and prices, hour by hour."
          icon="replay"
        />
        <Tile
          href="/2035"
          title="2035"
          text="How much storage can Britain use before batteries stop paying?"
          icon="future"
        />
        <Tile
          href="/play"
          title="Beat the battery"
          text="Plan tomorrow yourself from the forecast. Can you beat the optimiser?"
          icon="play"
        />
      </div>
      <h2 className="section">Whole years and pathways</h2>
      <div className="tiles small">
        <Tile
          href="/run"
          title="Value a battery"
          text="A year of trading, with frequency response, on history or a FES pathway."
        />
        <Tile href="/explore" title="Explore" text="Every year and pathway at a glance." />
        <Tile
          href="/compare?item=gb-2019&item=gb-2022&item=gb-2025"
          title="Compare"
          text="Years side by side, day by day."
        />
        <Tile
          href="/scenarios"
          title="FES pathways"
          text="The modelled 2030 and 2035 systems against NESO's own numbers."
        />
      </div>
      {data && <p className="source">{data.attribution.join(" ")}</p>}
    </section>
  );
}

function Tile({ href, title, text, icon }: { href: string; title: string; text: string; icon?: string }) {
  return (
    <a className="tile" href={href}>
      {icon && <Icon name={icon} />}
      <b>{title}</b>
      <span>{text}</span>
    </a>
  );
}

function Icon({ name }: { name: string }) {
  const shapes: Record<string, React.ReactNode> = {
    lab: (
      <>
        <rect x="3" y="8" width="24" height="20" fill="none" stroke="currentColor" strokeWidth="3" />
        <rect x="27" y="14" width="4" height="8" fill="currentColor" />
        <rect x="7" y="12" width="10" height="12" style={{ fill: "var(--blue)" }} />
      </>
    ),
    replay: (
      <>
        <path d="M3 28 L10 18 L16 22 L24 8 L31 14" fill="none" strokeWidth="3" style={{ stroke: "var(--red)" }} />
        <path d="M3 31 H31" stroke="currentColor" strokeWidth="2" />
      </>
    ),
    future: (
      <>
        <circle cx="17" cy="17" r="13" fill="none" stroke="currentColor" strokeWidth="3" />
        <path d="M17 8 V17 L24 21" fill="none" strokeWidth="3" style={{ stroke: "var(--yellow)" }} />
      </>
    ),
    play: (
      <>
        <rect x="3" y="10" width="6" height="14" style={{ fill: "var(--blue)" }} />
        <rect x="11" y="6" width="6" height="22" style={{ fill: "var(--red)" }} />
        <rect x="19" y="14" width="6" height="10" style={{ fill: "var(--yellow)" }} />
        <rect x="27" y="4" width="4" height="26" fill="currentColor" />
      </>
    ),
  };
  return (
    <svg className="ico" viewBox="0 0 34 34" aria-hidden="true">
      {shapes[name]}
    </svg>
  );
}
