import { useEffect, useMemo, useRef } from "react";

const STOPS = [
  [29, 43, 74],
  [91, 144, 245],
  [255, 194, 26],
  [242, 67, 51],
];

/** Each day's price spread (max minus min), or null where a price is missing. */
export function dailySpreads(prices: (number | null)[]): (number | null)[] {
  const out: (number | null)[] = [];
  for (let d = 0; d + 24 <= prices.length; d += 24) {
    const day = prices.slice(d, d + 24);
    out.push(day.every((v) => v !== null) ? Math.max(...(day as number[])) - Math.min(...(day as number[])) : null);
  }
  return out;
}

function colour(spread: number): string {
  const k = Math.min(1, spread / 300) * (STOPS.length - 1);
  const i = Math.min(STOPS.length - 2, Math.floor(k));
  const f = k - i;
  const [r, g, b] = STOPS[i].map((v, j) => Math.round(v + (STOPS[i + 1][j] - v) * f));
  return `rgb(${r} ${g} ${b})`;
}

/** The year as a strip of days coloured by price spread; click to jump to a day. */
export function YearStrip({
  year,
  prices,
  at,
  onPick,
}: {
  year: number;
  prices: (number | null)[];
  at: number;
  onPick: (day: number) => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const spreads = useMemo(() => dailySpreads(prices), [prices]);
  useEffect(() => {
    const node = canvas.current;
    if (!node) return;
    const draw = () => {
      const width = node.clientWidth;
      const height = node.clientHeight;
      if (!width || !node.getContext) return;
      const ratio = window.devicePixelRatio || 1;
      node.width = width * ratio;
      node.height = height * ratio;
      const c = node.getContext("2d");
      if (!c) return;
      c.setTransform(ratio, 0, 0, ratio, 0, 0);
      const w = width / spreads.length;
      spreads.forEach((s, d) => {
        c.fillStyle = s === null ? "rgba(128,128,128,.18)" : colour(s);
        c.fillRect(d * w, 0, Math.ceil(w), height);
      });
      c.fillStyle = "rgba(255,255,255,.35)";
      for (let m = 1; m < 12; m++) {
        const d = Math.round((Date.UTC(year, m, 1) - Date.UTC(year, 0, 1)) / 864e5);
        c.fillRect(d * w, 0, 1, height);
      }
      c.fillStyle = "#fff";
      c.fillRect(at * w - 1, 0, Math.max(3, w + 2), height);
      c.strokeStyle = "#000";
      c.strokeRect(at * w - 1.5, 0.5, Math.max(3, w + 2) + 1, height - 1);
    };
    draw();
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(draw) : null;
    observer?.observe(node);
    return () => observer?.disconnect();
  }, [spreads, at, year]);
  return (
    <canvas
      ref={canvas}
      className="year-strip"
      role="img"
      aria-label={`${year}, each day coloured by its price spread: dark blue calm, red wild. Click to jump to a day.`}
      onClick={(e) => {
        const box = e.currentTarget.getBoundingClientRect();
        onPick(Math.max(0, Math.min(spreads.length - 1, Math.floor(((e.clientX - box.left) / box.width) * spreads.length))));
      }}
    />
  );
}
