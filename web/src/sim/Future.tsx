import { useEffect, useMemo, useRef, useState } from "react";
import { Axes, Chart, frame, Legend, nice, path } from "../components/Svg";
import { loadSaturation, money, remember, type SaturationRow } from "../engine/data";
import { useLoad } from "../hooks";
import { Sources } from "./Sources";

const COLOURS = ["var(--blue)", "var(--red)", "var(--yellow)", "var(--ink)", "var(--green)"];
const CELL_GW = 2;

/** A number that counts to its new value instead of jumping. */
function useCount(target: number): number {
  const [shown, setShown] = useState(target);
  const from = useRef(target);
  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || typeof requestAnimationFrame === "undefined") {
      setShown(target);
      from.current = target;
      return;
    }
    const start = performance.now();
    const origin = from.current;
    let frameId = 0;
    const step = (now: number) => {
      const k = Math.min(1, (now - start) / 500);
      const value = origin + (target - origin) * (1 - (1 - k) ** 3);
      setShown(value);
      from.current = value;
      if (k < 1) frameId = requestAnimationFrame(step);
    };
    frameId = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frameId);
  }, [target]);
  return shown;
}

export function Future({ params }: { params: URLSearchParams }) {
  const loaded = useLoad(loadSaturation, "saturation");
  const [pathway, setPathway] = useState(params.get("pathway") ?? "Holistic Transition");
  const [index, setIndex] = useState(() => {
    const asked = Number(params.get("fleet"));
    return Number.isInteger(asked) && asked >= 0 && asked <= 4 && params.has("fleet") ? asked : 2;
  });
  const data = loaded.state === "done" ? loaded.value : null;
  const pathways = useMemo(() => (data ? [...new Set(data.summary.map((r) => r.pathway))] : []), [data]);
  const chosen = pathways.includes(pathway) ? pathway : pathways[0];
  const rows = useMemo(
    () => (data ? data.summary.filter((r) => r.pathway === chosen).sort((a, b) => a.battery_scale - b.battery_scale) : []),
    [data, chosen],
  );
  const at = Math.min(index, Math.max(0, rows.length - 1));
  const row = rows[at];
  const first = rows[0];
  const planned = rows.find((r) => r.battery_scale === 1);
  const counted = useCount(row?.revenue_per_mw_year ?? 0);

  useEffect(() => {
    if (chosen) remember(`/2035?${new URLSearchParams({ pathway: chosen, fleet: String(at) })}`);
  }, [chosen, at]);

  if (loaded.state === "loading") return <p>Loading the study…</p>;
  if (loaded.state === "error") return <p role="alert">The saturation study is not available yet.</p>;
  if (!row || !first || !data) return null;
  const fleetGw = row.fleet_battery_mw / 1000;
  const cells = Math.round(fleetGw / CELL_GW);
  const use = Math.min(100, (100 * row.fleet_cycles) / 365);
  const scarcityShare = Math.round((100 * row.scarcity_revenue) / Math.max(1, row.revenue_per_mw_year));
  const versusPlan =
    planned && row !== planned && planned.revenue_per_mw_year > 0
      ? Math.round((100 * (row.revenue_per_mw_year - planned.revenue_per_mw_year)) / planned.revenue_per_mw_year)
      : null;

  return (
    <section className="lens">
      <p className="kicker">2035 · NESO Future Energy Scenarios, made secure, on 2024 and 2025 weather</p>
      <h1>How much storage can Britain use before batteries stop paying?</h1>
      <div className="chips" role="group" aria-label="Pathway">
        {pathways.map((p) => (
          <button key={p} type="button" aria-pressed={p === chosen} onClick={() => setPathway(p)}>
            {p}
          </button>
        ))}
      </div>
      <div className="future">
        <div className="stack">
          <div className="big-number">
            <span className="v">{money(counted)}</span>
            <span className="l">what one more 1 MW / 2 MWh battery earns a year, with perfect foresight</span>
          </div>
          <div className="field">
            <label>
              <span className="field-label">
                Grid batteries{" "}
                <output>
                  {row.battery_scale === 0 ? "none" : `FES plan ×${row.battery_scale}`} · {fleetGw.toFixed(1)} GW
                </output>
              </span>
              <input type="range" min={0} max={rows.length - 1} value={at} onChange={(e) => setIndex(Number(e.target.value))} />
            </label>
          </div>
          <div className="fleet" aria-hidden="true">
            {Array.from({ length: cells }, (_, i) => (
              <span key={`${chosen}-${i}`} className="cell" style={{ animationDelay: `${i * 12}ms` }}>
                <i style={{ height: `${use}%` }} />
              </span>
            ))}
            <span className="help">
              {cells ? `each = ${CELL_GW} GW · filled to ${Math.round(row.fleet_cycles)} cycles a year / 365` : "No grid batteries: yours is the only one."}
            </span>
          </div>
          <p className="answer" aria-live="polite">
            With <b>{fleetGw.toFixed(1)} GW</b> of batteries in {chosen} 2035, one more 1 MW / 2 MWh battery would
            earn about <b>{money(row.revenue_per_mw_year)}</b> a year with perfect foresight
            {row.battery_scale > 0 && first.revenue_per_mw_year > 0
              ? `, ${Math.round((100 * row.revenue_per_mw_year) / first.revenue_per_mw_year)}% of what the first battery earns`
              : ""}
            ; <b>{scarcityShare}%</b> of that comes on the {row.scarcity_days.toFixed(1)} days a year with an hour
            priced at £1,000/MWh or more.
          </p>
          <div className="grid two">
            <div className="card">
              <h3>What one more battery earns (£ per MW-year)</h3>
              <Curve
                rows={data.summary}
                pathways={pathways}
                chosen={chosen}
                at={row.battery_scale}
                value={(r) => r.revenue_per_mw_year}
                part={(r) => r.scarcity_revenue}
                fmt={(v) => `£${Math.round(v / 1000)}k`}
                label="Battery value per MW-year against fleet size"
              />
            </div>
            <div className="card">
              <h3>Firm capacity still needed (GW)</h3>
              <Curve
                rows={data.summary}
                pathways={pathways}
                chosen={chosen}
                at={row.battery_scale}
                value={(r) => r.firm_added_mw / 1000}
                fmt={(v) => `${v}`}
                label="Firm capacity added against fleet size"
              />
            </div>
          </div>
          <Legend
            items={[
              ...pathways.map((p, i) => ({ label: p, colour: COLOURS[i % COLOURS.length] })),
              { label: "Shaded: earned on days with an hour at £1,000/MWh or more", colour: "var(--line-strong)" },
            ]}
          />
        </div>
        <dl className="facts stats">
          {versusPlan !== null && (
            <>
              <dt>Against the FES plan</dt>
              <dd>
                {versusPlan > 0 ? "+" : "−"}
                {Math.abs(versusPlan)}%
              </dd>
            </>
          )}
          <dt>Daily price spread</dt>
          <dd>£{row.daily_spread.toFixed(0)}/MWh</dd>
          <dt>Earned on scarcity days</dt>
          <dd>{scarcityShare}%</dd>
          <dt>One more battery's cycles</dt>
          <dd>{row.battery_cycles.toFixed(0)} a year</dd>
          <dt>Firm capacity added</dt>
          <dd>{(row.firm_added_mw / 1000).toFixed(2)} GW</dd>
          <dt>Loss of load</dt>
          <dd>{row.lole_hours.toFixed(1)} h a year</dd>
          <dt>Curtailed</dt>
          <dd>{row.curtailment_twh.toFixed(1)} TWh</dd>
          <dt>Emissions</dt>
          <dd>{row.emissions_mt.toFixed(1)} Mt CO₂</dd>
          {row.equivalent_firm !== null && (
            <>
              <dt>Firm capacity each MW of batteries replaces</dt>
              <dd>{row.equivalent_firm.toFixed(2)} MW</dd>
            </>
          )}
        </dl>
      </div>
      <p className="help">
        Modelled with OpenEnergy's GB dispatch (unit commitment, interconnectors trading at neighbours' actual
        prices) on 2024 and 2025 weather, fuel and carbon prices. Values are perfect-foresight upper bounds; a real
        battery planning on a forecast earns less. Firm capacity is added as gas peaking plant until loss of load,
        averaged over the two weather years, is within 3 hours a year.{" "}
        <a href="https://koulakhilesh.github.io/OpenEnergy/guides/forward-scenarios/">Method</a>
      </p>
      <Sources texts={[`Storage saturation study: OpenEnergy model output, ${data.source}, built on NESO Future Energy Scenarios 2025 (NESO Open Data Licence v1.0) and the data credited in data/scenarios/README.md.`]} />
    </section>
  );
}

function Curve({
  rows,
  pathways,
  chosen,
  at,
  value,
  part,
  fmt,
  label,
}: {
  rows: SaturationRow[];
  pathways: string[];
  chosen: string;
  at: number;
  value: (r: SaturationRow) => number;
  part?: (r: SaturationRow) => number;
  fmt: (v: number) => string;
  label: string;
}) {
  const scales = [...new Set(rows.map((r) => r.battery_scale))].sort((a, b) => a - b);
  const hi = Math.max(1e-9, ...rows.map(value)) * 1.15;
  const f = frame(420, 260, { n: scales[scales.length - 1] + 1, lo: 0, hi, margin: { left: 52 } });
  const x = (s: number) => f.x(s);
  return (
    <Chart width={420} height={260} label={label}>
      <Axes f={f} yticks={nice(0, hi, 3)} yfmt={fmt} xticks={scales.map((s) => [s, `×${s}`])} />
      {pathways.map((p, i) => {
        const line = rows.filter((r) => r.pathway === p).sort((a, b) => a.battery_scale - b.battery_scale);
        const mine = p === chosen;
        return (
          <g key={p} style={{ opacity: mine ? 1 : 0.35 }}>
            {mine && part && (
              <path
                d={`${path(line.map((r) => [x(r.battery_scale), f.y(part(r))]))}L${x(line[line.length - 1].battery_scale)},${f.y(0)}L${x(line[0].battery_scale)},${f.y(0)}Z`}
                style={{ fill: "var(--line-strong)" }}
              />
            )}
            <path
              d={path(line.map((r) => [x(r.battery_scale), f.y(value(r))]))}
              className={mine ? "line thick" : "line"}
              style={{ stroke: COLOURS[i % COLOURS.length] }}
            />
            {mine &&
              line.map((r) => (
                <circle
                  key={r.battery_scale}
                  cx={x(r.battery_scale)}
                  cy={f.y(value(r))}
                  r={r.battery_scale === at ? 7 : 4}
                  style={{ fill: r.battery_scale === at ? "var(--red)" : COLOURS[i % COLOURS.length] }}
                />
              ))}
          </g>
        );
      })}
    </Chart>
  );
}
