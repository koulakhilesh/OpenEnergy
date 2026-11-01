import { useMemo, useState } from "react";
import { Axes, Chart, frame, Legend, nice } from "../components/Svg";
import { FLEET_YEARS, type FleetUnitYear, loadFleet, loadFleetUnits, loadPrices, money } from "../engine/data";
import { useLoad } from "../hooks";
import { Sources } from "./Sources";

const ZONES: [string, string][] = [
  ["", "All of GB"],
  ["scotland", "Scotland"],
  ["england_wales", "England and Wales"],
];
type Column = "name" | "mw" | "days" | "dischargeHours" | "totalPerMwYear" | "dayAheadPerMwYear" | "bmPerMwYear";
const COLUMNS: [Column, string][] = [
  ["name", "Battery"],
  ["mw", "MW"],
  ["days", "Days running"],
  ["dischargeHours", "Full-power hours"],
  ["totalPerMwYear", "Estimated total, £/MW-yr"],
  ["dayAheadPerMwYear", "Metered energy at day-ahead price, £/MW-yr"],
  ["bmPerMwYear", "Balancing Mechanism, £/MW-yr"],
];

/** Means by UTC hour of day, skipping gaps. */
function byHour(values: (number | null)[]): (number | null)[] {
  const sum = new Array(24).fill(0);
  const count = new Array(24).fill(0);
  values.forEach((v, i) => {
    if (v === null) return;
    sum[i % 24] += v;
    count[i % 24] += 1;
  });
  return sum.map((s, h) => (count[h] ? s / count[h] : null));
}

/** What GB's real grid batteries did, from Elexon's metered data, next to the optimiser. */
export function Fleet({ params }: { params: URLSearchParams }) {
  const asked = Number(params.get("year"));
  const [year, setYear] = useState(FLEET_YEARS.includes(asked) ? asked : 2025);
  const [zone, setZone] = useState("");
  const [sort, setSort] = useState<Column>("totalPerMwYear");
  const units = useLoad(loadFleetUnits, "fleet-units");
  const fleet = useLoad(() => loadFleet(year), `fleet-${year}`);
  const prices = useLoad(() => loadPrices(year), `prices-${year}`);
  const all = units.state === "done" ? units.value : null;
  const summary = all?.years.find((r) => r.year === year);
  const rows = useMemo(
    () =>
      (all?.units ?? [])
        .filter((u) => u.year === year && (!zone || u.zone === zone))
        .sort((a, b) => (sort === "name" ? a.name.localeCompare(b.name) : (b[sort] as number) - (a[sort] as number))),
    [all, year, zone, sort],
  );
  const net = fleet.state === "done" ? byHour(fleet.value.net) : null;
  const price = prices.state === "done" ? byHour(prices.value.price) : null;

  return (
    <section className="lens">
      <p className="kicker">Real batteries · Elexon metered data for every GB grid battery</p>
      <h1>What Britain's real batteries did</h1>
      <div className="chips" role="group" aria-label="Year">
        {FLEET_YEARS.map((y) => (
          <button key={y} type="button" aria-pressed={y === year} onClick={() => setYear(y)}>
            {y}
          </button>
        ))}
      </div>
      {units.state === "loading" && <p>Loading the fleet…</p>}
      {units.state === "error" && <p role="alert">The real battery data is not available yet.</p>}
      {summary && (
        <p className="answer" aria-live="polite">
          In {year}, <b>{summary.units}</b> battery units ran ({summary.mw_years.toFixed(0)} MW-years
          {summary.repd_battery_mw ? `, about ${Math.round((100 * summary.mw_years) / summary.repd_battery_mw)}% of GB's grid batteries` : ""}).
          With their contracts priced at the day-ahead price, the Balancing Mechanism and imbalance, they made an
          estimated <b>{money(summary.real_estimated_total_per_mw_year)}</b> per MW-year; OpenEnergy's optimiser earns{" "}
          {money(summary.model_1h_fundamentals_per_mw_year)} for a 1-hour battery on its forecast and{" "}
          {money(summary.model_1h_perfect_per_mw_year)} with perfect foresight, on the day-ahead market alone.
        </p>
      )}
      <div className="grid two">
        <div className="card">
          <h3>The fleet through the day ({year}, UTC)</h3>
          {net && price ? <DayShape net={net} price={price} /> : <div className="chart-empty" />}
          <Legend
            items={[
              { label: "Fleet exporting, MW", colour: "var(--blue)" },
              { label: "Fleet importing, MW", colour: "var(--red)" },
              { label: "Day-ahead price, £/MWh", colour: "var(--ink)" },
            ]}
          />
        </div>
        <div className="card">
          <h3>Per MW-year, real and modelled</h3>
          {summary ? (
            <dl className="facts">
              <dt>Real: estimated total</dt>
              <dd>{money(summary.real_estimated_total_per_mw_year)}</dd>
              <dt> contracts (PN) at day-ahead price</dt>
              <dd>{money(summary.real_pn_day_ahead_per_mw_year)}</dd>
              <dt> Balancing Mechanism, net</dt>
              <dd>{money(summary.real_bm_net_per_mw_year)}</dd>
              <dt> imbalance at system price</dt>
              <dd>{money(summary.real_imbalance_per_mw_year)}</dd>
              <dt>Real: metered energy at day-ahead price</dt>
              <dd>{money(summary.real_metered_day_ahead_per_mw_year)}</dd>
              <dt>Real: full-power hours discharged</dt>
              <dd>{summary.discharge_hours.toFixed(0)}</dd>
              <dt>Real: energy out per energy in</dt>
              <dd>{(100 * summary.round_trip).toFixed(0)}%</dd>
              <dt>Model 1 h: last week's prices</dt>
              <dd>{money(summary.model_1h_naive_per_mw_year)}</dd>
              <dt>Model 1 h: OpenEnergy forecast</dt>
              <dd>{money(summary.model_1h_fundamentals_per_mw_year)}</dd>
              <dt>Model 1 h: perfect foresight</dt>
              <dd>{money(summary.model_1h_perfect_per_mw_year)}</dd>
              <dt>Model 2 h: perfect foresight</dt>
              <dd>{money(summary.model_2h_perfect_per_mw_year)}</dd>
            </dl>
          ) : (
            <p className="help">No comparison for {year} yet.</p>
          )}
          <p className="help">
            Real batteries also earn from frequency response and intraday trading, which open data does not show
            per unit; the model trades the day-ahead market only.{" "}
            <a href="https://koulakhilesh.github.io/OpenEnergy/guides/real-batteries/">Method</a>
          </p>
        </div>
      </div>
      <h2>Every unit in {year}</h2>
      <div className="chips" role="group" aria-label="Zone">
        {ZONES.map(([value, name]) => (
          <button key={name} type="button" aria-pressed={zone === value} onClick={() => setZone(value)}>
            {name}
          </button>
        ))}
      </div>
      <div className="wide">
        <table>
          <thead>
            <tr>
              {COLUMNS.map(([key, name]) => (
                <th key={key} aria-sort={sort === key ? (key === "name" ? "ascending" : "descending") : undefined}>
                  <button type="button" className="link" onClick={() => setSort(key)}>
                    {name}
                  </button>
                </th>
              ))}
              <th>Zone</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((u: FleetUnitYear) => (
              <tr key={u.unit}>
                <td title={u.unit}>{u.name}</td>
                <td>{u.mw.toFixed(0)}</td>
                <td>{u.days}</td>
                <td>{u.dischargeHours.toFixed(0)}</td>
                <td>{money(u.totalPerMwYear)}</td>
                <td>{money(u.dayAheadPerMwYear)}</td>
                <td>{money(u.bmPerMwYear)}</td>
                <td>{u.zone === "scotland" ? "Scotland" : u.zone === "england_wales" ? "England and Wales" : "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Sources texts={[...(all?.attribution ?? []), ...(prices.state === "done" ? prices.value.attribution : [])]} />
    </section>
  );
}

function DayShape({ net, price }: { net: (number | null)[]; price: (number | null)[] }) {
  const n = net.map((v) => v ?? 0);
  const p = price.map((v) => v ?? 0);
  const hiMw = Math.max(1, ...n.map(Math.abs)) * 1.1;
  const f = frame(420, 220, { n: 24, bars: true, lo: -hiMw, hi: hiMw, margin: { left: 56, right: 44 } });
  const hiP = Math.max(1, ...p) * 1.1;
  const yp = (v: number) => f.top + (1 - v / hiP) * (f.height - f.top - f.bottom);
  return (
    <Chart width={420} height={220} label="Real battery fleet's mean net output and the mean day-ahead price by hour of day">
      <Axes f={f} yticks={nice(-hiMw, hiMw, 4)} yfmt={(v) => `${v} MW`} xticks={[[0.5, "00"], [6.5, "06"], [12.5, "12"], [18.5, "18"], [23.5, "23"]]} />
      {n.map((v, h) => (
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
        d={p.map((v, h) => `${h ? "L" : "M"}${f.x(h + 0.5).toFixed(1)},${yp(v).toFixed(1)}`).join("")}
        className="line thick"
        style={{ stroke: "var(--ink)" }}
      />
      <text x={f.width - 4} y={yp(hiP / 1.1) + 4} textAnchor="end" className="band-label">
        £{Math.round(hiP / 1.1)}
      </text>
    </Chart>
  );
}
