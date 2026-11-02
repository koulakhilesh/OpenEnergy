import { BarsWithLine } from "../components/BarsWithLine";
import { Legend } from "../components/Svg";
import { NEW_TAB } from "../components/links";
import { label, money } from "../engine/data";
import { useLoad } from "../hooks";
import { Sources } from "./Sources";

export const LIVE_URL = "https://raw.githubusercontent.com/koulakhilesh/OpenEnergy/live/live.json";

export interface LiveDay {
  day: string;
  mae: number;
  earned: number;
  perfect: number;
}

export interface Live {
  day: string;
  issued: string;
  pricesKnownUntil: string;
  start: string;
  forecast: number[];
  planMw: number[];
  stretch: number;
  track: LiveDay[];
  summary: { days: number; mae: number | null; capture: number | null };
  note: string;
  attribution: string[];
}

async function loadLive(): Promise<Live> {
  const response = await fetch(LIVE_URL, { cache: "no-cache" });
  if (!response.ok) throw new Error("could not load the live forecast");
  return response.json();
}

const hour = (i: number) => `${String(i).padStart(2, "0")}:00`;
const when = (stamp: string) => `${label(new Date(stamp))}, ${stamp.slice(11, 16)} UTC`;

/** Tomorrow's GB day-ahead prices, forecast each morning, and how earlier forecasts did. */
export function LiveForecast() {
  const live = useLoad(loadLive, "live");
  const data = live.state === "done" ? live.value : null;
  const prices = data?.forecast ?? [];
  const low = prices.indexOf(Math.min(...prices));
  const high = prices.indexOf(Math.max(...prices));
  const recent = data ? data.track.slice(-14).reverse() : [];

  return (
    <section className="lens">
      <p className="kicker">Live · forecast every morning from open data</p>
      <h1>Tomorrow's prices</h1>
      {live.state === "loading" && <p>Loading the latest forecast…</p>}
      {live.state === "error" && <p role="alert">The live forecast is not available right now.</p>}
      {data && (
        <p className="answer" aria-live="polite">
          OpenEnergy forecasts GB day-ahead prices for <b>{label(new Date(`${data.day}T00:00:00Z`))}</b> from{" "}
          <b>{money(prices[low])}</b>/MWh at {hour(low)} to <b>{money(prices[high])}</b> at {hour(high)} UTC. A 1 MW,
          2 MWh battery planning on it would charge in the cheap hours and sell in the dear ones.
        </p>
      )}
      {data && (
        <div className="grid two">
          <div className="card">
            <h3>Forecast and plan (UTC)</h3>
            <BarsWithLine
              bars={data.planMw}
              line={prices}
              label="Tomorrow's forecast price and the battery's plan by hour"
            />
            <Legend
              items={[
                { label: "Battery selling, MW", colour: "var(--blue)" },
                { label: "Battery buying, MW", colour: "var(--red)" },
                { label: "Forecast price, £/MWh", colour: "var(--ink)" },
              ]}
            />
            <p className="help">
              Made {when(data.issued)}, with prices published up to {when(data.pricesKnownUntil)}.
            </p>
          </div>
          <div className="card">
            <h3>Track record</h3>
            {data.summary.days ? (
              <p>
                Over the last <b>{data.summary.days}</b> days with published prices, the forecast was off by{" "}
                <b>{money(data.summary.mae)}</b>/MWh on average, and the battery planning on it earned{" "}
                <b>{data.summary.capture === null ? "–" : `${Math.round(100 * data.summary.capture)}%`}</b> of
                what it would with perfect foresight.
              </p>
            ) : (
              <p className="help">No forecast has been scored yet: prices are published about two days late.</p>
            )}
            {recent.length > 0 && (
              <table>
                <thead>
                  <tr>
                    <th>Day</th>
                    <th>Average error, £/MWh</th>
                    <th>Battery earned</th>
                    <th>Perfect foresight</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.map((d) => (
                    <tr key={d.day}>
                      <td>{label(new Date(`${d.day}T00:00:00Z`))}</td>
                      <td>{d.mae.toFixed(1)}</td>
                      <td>{money(d.earned)}</td>
                      <td>{money(d.perfect)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
      {data && (
        <p className="help">
          {data.note}{" "}
          <a href="https://koulakhilesh.github.io/OpenEnergy/guides/research/#live-forecast" {...NEW_TAB}>
            Method
          </a>
        </p>
      )}
      <Sources texts={data?.attribution ?? []} />
    </section>
  );
}
