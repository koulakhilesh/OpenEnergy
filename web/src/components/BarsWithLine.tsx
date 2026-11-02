import { Axes, Chart, frame, nice } from "./Svg";

const HOURS: [number, string][] = [
  [0.5, "00"],
  [6.5, "06"],
  [12.5, "12"],
  [18.5, "18"],
  [23.5, "23"],
];

/** 24 hourly bars (MW, blue up and red down) with a price line on its own scale (£/MWh). */
export function BarsWithLine({ bars, line, label }: { bars: number[]; line: number[]; label: string }) {
  const hiMw = Math.max(1, ...bars.map(Math.abs)) * 1.1;
  const f = frame(420, 220, { n: 24, bars: true, lo: -hiMw, hi: hiMw, margin: { left: 56, right: 44 } });
  const lo = Math.min(0, ...line);
  const hi = Math.max(1, ...line) * 1.1;
  const y = (v: number) => f.top + (1 - (v - lo) / (hi - lo)) * (f.height - f.top - f.bottom);
  return (
    <Chart width={420} height={220} label={label}>
      <Axes f={f} yticks={nice(-hiMw, hiMw, 4)} yfmt={(v) => `${v} MW`} xticks={HOURS} />
      {bars.map((v, h) => (
        <rect
          key={h}
          x={f.x(h) + 1}
          y={Math.min(f.y(0), f.y(v))}
          width={f.x(1) - f.x(0) - 2}
          height={Math.abs(f.y(v) - f.y(0))}
          style={{ fill: v >= 0 ? "var(--blue)" : "var(--red)", opacity: 0.8 }}
        />
      ))}
      <path
        d={line.map((v, h) => `${h ? "L" : "M"}${f.x(h + 0.5).toFixed(1)},${y(v).toFixed(1)}`).join("")}
        className="line thick"
        style={{ stroke: "var(--ink)" }}
      />
      <text x={f.width - 4} y={y(hi / 1.1) + 4} textAnchor="end" className="band-label">
        £{Math.round(hi / 1.1)}
      </text>
    </Chart>
  );
}
