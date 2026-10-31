/** A small SVG chart kit: scales, axes and paths styled by the site's colour tokens. */
import type { ReactNode } from "react";

export interface Frame {
  x: (i: number) => number;
  y: (v: number) => number;
  width: number;
  height: number;
  left: number;
  right: number;
  top: number;
  bottom: number;
  lo: number;
  hi: number;
}

interface FrameOptions {
  /** Points along x (for bars, the number of slots). */
  n: number;
  lo: number;
  hi: number;
  bars?: boolean;
  margin?: Partial<Record<"left" | "right" | "top" | "bottom", number>>;
  /** Value for the first x slot (default 0). */
  x0?: number;
}

export function frame(width: number, height: number, o: FrameOptions): Frame {
  const left = o.margin?.left ?? 48;
  const right = o.margin?.right ?? 12;
  const top = o.margin?.top ?? 10;
  const bottom = o.margin?.bottom ?? 24;
  const span = o.bars ? o.n : Math.max(1, o.n - 1);
  const x0 = o.x0 ?? 0;
  const range = o.hi - o.lo || 1;
  return {
    x: (i) => left + ((i - x0) / span) * (width - left - right),
    y: (v) => top + (1 - (v - o.lo) / range) * (height - top - bottom),
    width,
    height,
    left,
    right,
    top,
    bottom,
    lo: o.lo,
    hi: o.hi,
  };
}

/** About ``count`` round tick values covering lo..hi. */
export function nice(lo: number, hi: number, count = 4): number[] {
  const span = hi - lo || 1;
  const base = Math.pow(10, Math.floor(Math.log10(span / count)));
  const step = [1, 2, 2.5, 5, 10].map((k) => k * base).find((k) => span / k <= count) ?? base * 10;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(6));
  return out;
}

export const path = (points: [number, number][]) =>
  points.map(([a, b], i) => `${i ? "L" : "M"}${a.toFixed(1)},${b.toFixed(1)}`).join("");

/** Lines through finite values, broken at gaps. */
export function gapPath(values: (number | null)[], x: (i: number) => number, y: (v: number) => number) {
  let d = "";
  let pen = false;
  values.forEach((v, i) => {
    if (v === null || !Number.isFinite(v)) {
      pen = false;
      return;
    }
    d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
    pen = true;
  });
  return d;
}

export function Axes({
  f,
  yticks,
  yfmt = String,
  xticks = [],
}: {
  f: Frame;
  yticks: number[];
  yfmt?: (v: number) => string;
  xticks?: [number, string][];
}) {
  return (
    <g className="axis" aria-hidden="true">
      {yticks.map((v) => (
        <g key={`y${v}`}>
          <line x1={f.left} x2={f.width - f.right} y1={f.y(v)} y2={f.y(v)} />
          <text x={f.left - 6} y={f.y(v) + 4} textAnchor="end">
            {yfmt(v)}
          </text>
        </g>
      ))}
      {xticks.map(([i, text]) => (
        <text key={`x${i}`} x={f.x(i)} y={f.height - 6} textAnchor="middle">
          {text}
        </text>
      ))}
    </g>
  );
}

export function Chart({
  width,
  height,
  label,
  children,
  onPointer,
  className,
}: {
  width: number;
  height: number;
  label: string;
  children: ReactNode;
  /** Called with the pointer's x in chart units on click or drag. */
  onPointer?: (x: number, y: number, kind: "down" | "move" | "up") => void;
  className?: string;
}) {
  const handle = (kind: "down" | "move" | "up") => (event: React.PointerEvent<SVGSVGElement>) => {
    if (!onPointer) return;
    if (kind === "move" && event.buttons === 0) return;
    const box = event.currentTarget.getBoundingClientRect();
    if (kind === "down") event.currentTarget.setPointerCapture?.(event.pointerId);
    onPointer(
      ((event.clientX - box.left) / box.width) * width,
      ((event.clientY - box.top) / box.height) * height,
      kind,
    );
  };
  return (
    <svg
      className={`chart ${className ?? ""}`}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={label}
      onPointerDown={handle("down")}
      onPointerMove={handle("move")}
      onPointerUp={handle("up")}
    >
      {children}
    </svg>
  );
}

export const HOUR_TICKS: [number, string][] = [
  [0.5, "00"],
  [6.5, "06"],
  [12.5, "12"],
  [18.5, "18"],
  [23.5, "23"],
];

export const pounds = (v: number) => `£${v}`;

export function Legend({ items }: { items: { label: string; colour: string; dash?: boolean }[] }) {
  return (
    <div className="legend">
      {items.map((item) => (
        <span key={item.label} className={item.dash ? "dash" : ""} style={{ "--c": item.colour } as React.CSSProperties}>
          {item.label}
        </span>
      ))}
    </div>
  );
}
