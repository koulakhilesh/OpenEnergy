import { useState } from "react";
import { Tip, useOptions } from "../components/Tip";

export function Home() {
  const options = useOptions();
  const [source, setSource] = useState<"history" | "scenario">("history");
  const latest = options.history_years[options.history_years.length - 1];
  return (
    <>
      <h1>OpenEnergy battery value</h1>
      <p>
        What would a grid battery have earned trading GB day-ahead prices, or what might it earn
        on a NESO Future Energy Scenarios pathway? Each run plans every day at noon the day before
        and compares with perfect foresight. 1, 2 and 4 hour batteries answer at once; other
        durations take 15 to 45 seconds.
      </p>
      <form action="/result" method="get">
        <fieldset>
          <legend>Prices</legend>
          <label>
            <input
              type="radio"
              name="source"
              value="history"
              checked={source === "history"}
              onChange={() => setSource("history")}
            />{" "}
            Historic GB year
          </label>{" "}
          <select
            name="year"
            aria-label="Historic year"
            defaultValue={latest}
            onChange={() => setSource("history")}
          >
            {options.history_years.map((year) => (
              <option key={year}>{year}</option>
            ))}
          </select>
          <br />
          <label>
            <input
              type="radio"
              name="source"
              value="scenario"
              checked={source === "scenario"}
              onChange={() => setSource("scenario")}
            />{" "}
            FES pathway
          </label>{" "}
          <select name="pathway" aria-label="FES pathway" onChange={() => setSource("scenario")}>
            {options.pathways.map((pathway) => (
              <option key={pathway}>{pathway}</option>
            ))}
          </select>{" "}
          in{" "}
          <select name="target" aria-label="FES year" onChange={() => setSource("scenario")}>
            {options.scenario_years.map((year) => (
              <option key={year}>{year}</option>
            ))}
          </select>{" "}
          <Tip name="pathway" />
        </fieldset>
        <fieldset>
          <legend>Battery and plan</legend>
          <label>
            Power (MW){" "}
            <input
              name="power_mw"
              type="number"
              defaultValue={1}
              min={options.power_range[0]}
              max={options.power_range[1]}
              step={0.1}
              required
            />
          </label>{" "}
          <Tip name="power" />
          <label>
            Duration (hours){" "}
            <input
              name="hours"
              type="number"
              defaultValue={2}
              min={options.hours_range[0]}
              max={options.hours_range[1]}
              step={0.5}
              required
            />
          </label>{" "}
          <Tip name="duration" />
          <br />
          <label>
            Forecast{" "}
            <select name="forecast">
              {Object.entries(options.forecasts).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>{" "}
          <Tip name="forecast" />
          <label>
            Frequency response (historic {options.response_from} onwards){" "}
            <select name="services">
              {Object.entries(options.services).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>{" "}
          <Tip name="response" />
        </fieldset>
        <button type="submit">Run</button>
      </form>
      <p>
        Or see <a href="/explore">every year and pathway at a glance</a>, or{" "}
        <a href="/compare?item=gb-2019&item=gb-2022&item=gb-2025">compare years side by side</a>.
      </p>
    </>
  );
}
