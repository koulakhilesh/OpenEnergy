import type { Item } from "../api/client";
import { money, percent, requestParams } from "../format";
import { Tip } from "./Tip";

/** One row per result with revenue for ``power`` MW and a link to open it. */
export function ResultsTable({ items, power }: { items: Item[]; power: number }) {
  if (items.length === 0) return null;
  return (
    <div className="wide">
      <table>
        <thead>
          <tr>
            <th scope="col">Prices</th>
            <th scope="col">Revenue for {power} MW</th>
            <th scope="col">Per MW</th>
            <th scope="col">
              Share of perfect foresight <Tip name="share" />
            </th>
            <th scope="col">
              Cycles a day <Tip name="cycles" />
            </th>
            <th scope="col">
              <span className="visually-hidden">Open</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map(({ request, summary }) => (
            <tr key={request.key}>
              <td>{request.where}</td>
              <td>{money(summary.revenue_per_mw_year * power)}</td>
              <td>{money(summary.revenue_per_mw_year)}</td>
              <td>{percent(summary.capture_ratio)}</td>
              <td>{summary.cycles_per_day.toFixed(1)}</td>
              <td>
                <a href={`/result?${requestParams(request, power)}`}>Open</a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
