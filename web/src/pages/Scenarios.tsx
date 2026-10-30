import { api } from "../api/client";
import { useLoad } from "../hooks";

const COLUMNS: [string, string, number][] = [
  ["price_mean", "Mean price", 1],
  ["daily_spread", "Daily spread", 1],
  ["imports_twh", "Imports", 1],
  ["fes_imports_twh", "FES imports", 1],
  ["exports_twh", "Exports", 1],
  ["fes_exports_twh", "FES exports", 1],
  ["curtailment_twh", "Curtailment", 1],
  ["fes_curtailment_twh", "FES curtailment", 1],
  ["unserved_gwh", "Unserved (GWh)", 1],
];

export function Scenarios() {
  const loaded = useLoad(api.scenarios, "scenarios");
  return (
    <>
      <h1>FES pathways on 2025's weather</h1>
      <p>
        Prices in GBP/MWh, energy in TWh. FES columns are NESO's own figures for the same year; the
        model's are from one weather year with price-taking links and unit commitment, so the gaps
        are part of the result.
      </p>
      {loaded.state === "loading" && <p aria-live="polite">Loading…</p>}
      {loaded.state === "error" && <p role="alert">{loaded.message}</p>}
      {loaded.state === "done" && (
        <>
          <div className="wide">
            <table>
              <thead>
                <tr>
                  <th scope="col">Pathway</th>
                  <th scope="col">Year</th>
                  {COLUMNS.map(([key, name]) => (
                    <th scope="col" key={key}>
                      {name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loaded.value.rows.map((row) => (
                  <tr key={`${row.pathway}-${row.year}`}>
                    <td>{row.pathway}</td>
                    <td>{row.year}</td>
                    {COLUMNS.map(([key, , digits]) => (
                      <td key={key}>
                        {(row[key as keyof typeof row] as number).toFixed(digits)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="source">{loaded.value.note}</p>
          <p className="source">{loaded.value.attribution}</p>
        </>
      )}
    </>
  );
}
