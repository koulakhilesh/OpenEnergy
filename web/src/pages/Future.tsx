import { useMemo, useState } from "react";
import { Axes, Chart, frame, Legend, nice, path } from "../components/Svg";
import { loadSaturation, money, type SaturationRow } from "../engine/data";
import { useLoad } from "../hooks";

const COLOURS = ["var(--blue)", "var(--red)", "var(--yellow)", "var(--ink)", "var(--green)"];

export function Future({ params }: { params: URLSearchParams }) {
  const loaded = useLoad(loadSaturation, "saturation");
  const [pathway, setPathway] = useState(params.get("pathway") ?? "Holistic Transition");
  const [index, setIndex] = useState(2);
  const data = loaded.state === "done" ? loaded.value : null;
  const pathways = useMemo(() => (data ? [...new Set(data.summary.map((r) => r.pathway))] : []), [data]);
  const chosen = pathways.includes(pathway) ? pathway : pathways[0];
  const rows = useMemo(
    () => (data ? data.summary.filter((r) => r.pathway === chosen).sort((a, b) => a.battery_scale - b.battery_scale) : []),
    [data, chosen],
  );
  const row = rows[Math.min(index, rows.length - 1)];
  const first = rows[0];

  return (
    <section className="page">
      <p className="kicker">2035 · NESO Future Energy Scenarios, made secure, on 2024 and 2025 weather</p>
      <h1>How much storage can Britain use?</h1>
      <p className="lede">
        Each pathway's 2035 system, topped up with just enough firm capacity to meet Britain's reliability
        standard, with its battery fleet scaled from none to three times NESO's own figure. Drag the fleet and
        watch what one more battery would earn.
      </p>
      {loaded.state === "loading" && <p>Loading the study…</p>}
      {loaded.state === "error" && <p role="alert">The saturation study is not available yet.</p>}
      {row && first && (
        <div className="grid lab">
          <aside className="card controls">
            <h3>Pathway</h3>
            <div className="chips" role="group" aria-label="Pathway">
              {pathways.map((p) => (
                <button key={p} type="button" aria-pressed={p === chosen} onClick={() => setPathway(p)}>
                  {p}
                </button>
              ))}
            </div>
            <div className="field">
              <label>
                <span className="field-label">
                  Battery fleet <output>× {row.battery_scale} ({(row.fleet_battery_mw / 1000).toFixed(1)} GW)</output>
                </span>
                <input
                  type="range"
                  min={0}
                  max={rows.length - 1}
                  value={Math.min(index, rows.length - 1)}
                  onChange={(e) => setIndex(Number(e.target.value))}
                />
              </label>
              <p className="help">Times the pathway's own 2035 battery fleet, at the same duration.</p>
            </div>
            <dl className="facts">
              <dt>Firm capacity added</dt>
              <dd>{(row.firm_added_mw / 1000).toFixed(2)} GW</dd>
              <dt>Loss of load</dt>
              <dd>{row.lole_hours.toFixed(1)} h a year</dd>
              <dt>Daily price spread</dt>
              <dd>£{row.daily_spread.toFixed(0)}/MWh</dd>
              <dt>Hours at £1,000+</dt>
              <dd>{row.scarcity_hours.toFixed(1)} a year</dd>
              <dt>Curtailed</dt>
              <dd>{row.curtailment_twh.toFixed(1)} TWh</dd>
              {row.equivalent_firm !== null && (
                <>
                  <dt>Firm capacity each MW of batteries replaces</dt>
                  <dd>{row.equivalent_firm.toFixed(2)} MW</dd>
                </>
              )}
            </dl>
          </aside>
          <div className="stack">
            <p className="answer" aria-live="polite">
              With <b>{(row.fleet_battery_mw / 1000).toFixed(1)} GW</b> of batteries in {chosen} 2035, one more
              1 MW / 2 MWh battery would earn about <b>{money(row.revenue_per_mw_year)}</b> a year with perfect
              foresight
              {row.battery_scale > 0 && first.revenue_per_mw_year > 0
                ? `, ${Math.round((100 * row.revenue_per_mw_year) / first.revenue_per_mw_year)}% of what the first battery earns`
                : ""}
              ; <b>{Math.round((100 * row.scarcity_revenue) / Math.max(1, row.revenue_per_mw_year))}%</b> of that
              comes on the {row.scarcity_days.toFixed(1)} days a year with an hour priced at £1,000/MWh or more.
            </p>
            <div className="grid two">
              <div className="card">
                <h3>What one more battery earns (£ per MW-year)</h3>
                <Curve
                  rows={data!.summary}
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
                  rows={data!.summary}
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
            <p className="help">
              Modelled with OpenEnergy's GB dispatch (unit commitment, interconnectors trading at neighbours'
              actual prices) on 2024 and 2025 weather, fuel and carbon prices. Values are perfect-foresight upper
              bounds; a real battery planning on a forecast earns less. Firm capacity is added as gas peaking
              plant until loss of load, averaged over the two weather years, is within 3 hours a year. Source:{" "}
              {data!.source}.
            </p>
          </div>
        </div>
      )}
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
