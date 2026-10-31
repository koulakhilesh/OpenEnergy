/** Power flowing into Britain's grid in one hour, the price on the grid, and the battery. */

export const FUELS: [key: string, name: string][] = [
  ["nuclear", "Nuclear"],
  ["wind", "Wind"],
  ["solar", "Solar"],
  ["hydro", "Hydro"],
  ["biomass", "Biomass"],
  ["gas", "Gas"],
  ["coal", "Coal"],
  ["imports", "Imports"],
  ["storage", "Pumped storage"],
  ["other", "Other"],
];

export function priceColour(price: number | null): string {
  if (price === null) return "var(--line-strong)";
  if (price < 0) return "var(--blue)";
  if (price < 50) return "var(--hydro)";
  if (price < 90) return "var(--biomass)";
  if (price < 130) return "var(--yellow)";
  if (price < 200) return "var(--gas)";
  return "var(--red)";
}

const BUS = { x: 450, y: 220, r: 62 };
const SOURCE_X = 150;
const gw = (mw: number) => `${(mw / 1000).toFixed(1)} GW`;

export function demandOf(mix: Record<string, number | null>): number {
  return FUELS.reduce((sum, [key]) => sum + (mix[key] ?? 0), 0);
}

export interface FlowProps {
  /** Fuels to draw, fixed for the year so the layout does not jump. */
  fuels: [string, string][];
  mix: Record<string, number | null> | null;
  price: number | null;
  /** Grid MW the battery buys (positive) or sells (negative) this hour. */
  battery: number;
  /** Stored energy as a share of capacity, 0 to 1. */
  stored: number;
  hourLabel: string;
}

export function Flow({ fuels, mix, price, battery, stored, hourLabel }: FlowProps) {
  const shown = mix ? fuels : [];
  const total = mix ? demandOf(mix) : 0;
  const action = battery > 1e-6 ? "buy" : battery < -1e-6 ? "sell" : "idle";
  const n = shown.length;
  const priceText = price === null ? "–" : `${price < 0 ? "−" : ""}£${Math.abs(price).toFixed(0)}`;
  const summary = mix
    ? `${hourLabel}: Britain used ${gw(total)}; ${shown
        .filter(([key]) => (mix[key] ?? 0) >= 50)
        .map(([key, name]) => `${name.toLowerCase()} ${gw(mix[key] ?? 0)}`)
        .join(", ")}. Day-ahead price ${priceText}/MWh.`
    : `${hourLabel}: no generation data for this hour.`;
  const out = `M ${BUS.x + BUS.r - 4} ${BUS.y - 10} C ${BUS.x + 120} ${BUS.y - 10}, ${BUS.x + 100} 120, 640 120`;
  const bat = `M ${BUS.x + BUS.r - 6} ${BUS.y + 22} C ${BUS.x + 120} ${BUS.y + 22}, ${BUS.x + 100} 330, 626 330`;
  return (
    <div className="flow">
      <svg viewBox="0 0 760 440" role="img" aria-label={summary}>
        {shown.map(([key, name], i) => {
          const mw = mix?.[key] ?? 0;
          const y = n > 1 ? 28 + (i * 384) / (n - 1) : BUS.y;
          const ey = BUS.y + (i - (n - 1) / 2) * 7;
          const d = `M ${SOURCE_X} ${y} C ${SOURCE_X + 150} ${y}, ${BUS.x - 170} ${ey}, ${BUS.x - BUS.r + 4} ${ey}`;
          return (
            <g key={key} style={{ "--c": `var(--${key})` } as React.CSSProperties}>
              <path d={d} className="flow-band" style={{ strokeWidth: Math.max(0.8, mw / 1100) }} />
              <path d={d} className="flow-dots" style={dots(mw)} />
              <circle cx={SOURCE_X} cy={y} r={4 + Math.sqrt(mw) / 16} className="flow-node" style={{ opacity: mw < 30 ? 0.3 : 1 }} />
              <text x={SOURCE_X - 16} y={y - 1} textAnchor="end" className="flow-label">
                {name}
              </text>
              <text x={SOURCE_X - 16} y={y + 13} textAnchor="end" className="flow-value">
                {gw(mw)}
              </text>
            </g>
          );
        })}
        <g style={{ "--c": "var(--ink)" } as React.CSSProperties}>
          <path d={out} className="flow-band" style={{ strokeWidth: Math.max(0.8, total / 1600), opacity: 0.12 }} />
          <path d={out} className="flow-dots" style={{ ...dots(total), opacity: total ? 0.7 : 0 }} />
          <text x={652} y={104} className="flow-label">
            Homes and
          </text>
          <text x={652} y={119} className="flow-label">
            business
          </text>
          <text x={652} y={134} className="flow-value">
            {gw(total)}
          </text>
        </g>
        <g
          className={`flow-battery ${action}`}
          style={{ "--c": action === "buy" ? "var(--blue)" : "var(--red)" } as React.CSSProperties}
        >
          <path d={bat} className="flow-band" style={{ strokeWidth: 4 }} />
          <path d={bat} className="flow-dots" style={{ strokeWidth: 6, opacity: action === "idle" ? 0 : 1 }} />
          <rect x={630} y={310} width={22} height={40} rx={2} className="flow-tank" />
          <rect x={633} y={313 + 34 * (1 - stored)} width={16} height={34 * stored} className="flow-fill" />
          <text x={662} y={326} className="flow-label">
            Your battery
          </text>
          <text x={662} y={341} className="flow-value">
            {action === "idle" ? "idle" : `${action === "buy" ? "buying" : "selling"} ${Math.abs(battery).toFixed(2)} MW`}
          </text>
          <text x={662} y={356} className="flow-value small">
            (not to scale)
          </text>
        </g>
        <circle cx={BUS.x} cy={BUS.y} r={BUS.r} className="flow-bus" style={{ stroke: priceColour(price) }} />
        <text x={BUS.x} y={BUS.y - 18} textAnchor="middle" className="flow-value">
          GREAT BRITAIN
        </text>
        <text x={BUS.x} y={BUS.y + 10} textAnchor="middle" className="flow-price">
          {priceText}
        </text>
        <text x={BUS.x} y={BUS.y + 28} textAnchor="middle" className="flow-value">
          £/MWh day-ahead
        </text>
        {!mix && (
          <text x={SOURCE_X} y={BUS.y} textAnchor="middle" className="flow-value">
            No generation data
          </text>
        )}
      </svg>
    </div>
  );
}

/** Moving dots: faster for bigger flows, none for almost nothing. */
function dots(mw: number): React.CSSProperties {
  const width = Math.max(0.8, mw / 1100);
  return {
    strokeWidth: Math.min(Math.max(2, width * 0.45), 9),
    opacity: mw < 30 ? 0 : 0.95,
    animationDuration: `${Math.max(0.5, 3.2 - mw / 9000).toFixed(2)}s`,
  };
}
