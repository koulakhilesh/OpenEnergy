import { useEffect, useMemo, useRef, useState } from "react";
import { Axes, Chart, frame, gapPath, HOUR_TICKS, nice, pounds } from "../components/Svg";
import { planDay, revenue } from "../engine/battery";
import { complete, day, loadPrices, money } from "../engine/data";
import { useHighs } from "../engine/hooks";
import { battery } from "./Lab";

const B = battery(1, 2, 0.95, 5);
const LO = -50;
const HI = 300;
const FLAT = new Array(24).fill(80);
const DUCK = Array.from({ length: 24 }, (_, t) =>
  Math.round(90 - 85 * Math.exp(-((t - 12) ** 2) / 10) + 70 * Math.exp(-((t - 18) ** 2) / 3)),
);

/** For the docs: drag the prices and watch the optimal plan change. */
export function Arbitrage() {
  const { highs, failed } = useHighs();
  const [prices, setPrices] = useState<number[]>(DUCK);
  const drag = useRef(-1);
  const plan = useMemo(() => (highs ? planDay(highs, prices, B) : null), [highs, prices]);
  const f = frame(700, 260, { n: 24, bars: true, lo: LO, hi: HI });
  const earned = plan ? revenue(plan, prices) : 0;
  const moved = plan ? plan.charge.reduce((s, v) => s + v, 0) + plan.discharge.reduce((s, v) => s + v, 0) : 0;

  useEffect(() => {
    document.documentElement.dataset.embed = "true";
  }, []);

  const realDay = async () => {
    const data = await loadPrices(2025);
    for (let tries = 0; tries < 20; tries++) {
      const values = day(data.price, 7 + Math.floor(Math.random() * 350));
      if (complete(values)) {
        setPrices(values.map((v) => Math.round(Math.max(LO, Math.min(HI, v)))));
        return;
      }
    }
  };

  const set = (hour: number, value: number) =>
    setPrices((now) => now.map((v, t) => (t === hour ? Math.round(Math.max(LO, Math.min(HI, value))) : v)));

  return (
    <div className="widget">
      <div className="wtitle">
        <span>Try it · drag the prices</span>
        <span aria-live="polite">
          {plan ? `plan earns ${money(earned - B.wear * moved)} after wear · blue buys, red sells` : failed ? "needs WebAssembly" : "loading…"}
        </span>
      </div>
      <Chart
        width={700}
        height={260}
        label="Prices you can drag, with the battery's best plan as bars"
        className="draggable"
        onPointer={(x, y, kind) => {
          if (kind === "down") drag.current = Math.max(0, Math.min(23, Math.floor((x - f.left) / (f.x(1) - f.x(0)))));
          if (kind === "up") drag.current = -1;
          else if (drag.current >= 0) set(drag.current, LO + (1 - (y - f.top) / (f.height - f.top - f.bottom)) * (HI - LO));
        }}
      >
        <Axes f={f} yticks={nice(LO, HI, 5)} yfmt={pounds} xticks={HOUR_TICKS} />
        {plan &&
          Array.from(plan.charge).map((c, t) => {
            const mw = c - plan.discharge[t];
            if (Math.abs(mw) < 1e-6) return null;
            const h = 40 * Math.abs(mw);
            return (
              <rect
                key={t}
                x={f.x(t + 0.2)}
                y={f.y(LO) - h}
                width={f.x(0.6) - f.x(0)}
                height={h}
                style={{ fill: mw > 0 ? "var(--blue)" : "var(--red)", opacity: 0.75 }}
              />
            );
          })}
        <path d={gapPath(prices, (i) => f.x(i + 0.5), f.y)} className="line thick" style={{ stroke: "var(--ink)" }} />
        {prices.map((v, t) => (
          <circle
            key={t}
            cx={f.x(t + 0.5)}
            cy={f.y(v)}
            r={8}
            tabIndex={0}
            role="slider"
            aria-label={`${String(t).padStart(2, "0")}:00 price`}
            aria-valuenow={v}
            aria-valuemin={LO}
            aria-valuemax={HI}
            className="handle"
            onKeyDown={(e) => {
              if (e.key === "ArrowUp" || e.key === "ArrowDown") {
                set(t, v + (e.key === "ArrowUp" ? 5 : -5));
                e.preventDefault();
              }
            }}
          />
        ))}
      </Chart>
      <div className="row">
        <button type="button" className="btn ghost" onClick={() => setPrices(FLAT)}>
          Flatten
        </button>
        <button type="button" className="btn ghost" onClick={() => setPrices(DUCK)}>
          Solar duck
        </button>
        <button type="button" className="btn ghost" onClick={realDay}>
          A real day
        </button>
        <a className="btn ghost" href="/lab" target="_top">
          Open the Battery Lab
        </a>
      </div>
    </div>
  );
}
