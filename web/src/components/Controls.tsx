import type { ReactNode } from "react";
import { Tip, useOptions } from "./Tip";

interface Props {
  action: string;
  params: URLSearchParams;
  power: number;
  /** Show the frequency-response choice. */
  services?: boolean;
  children?: ReactNode;
}

/** Duration, forecast, power (and optionally response) for explore and compare, as a GET form. */
export function Controls({ action, params, power, services, children }: Props) {
  const options = useOptions();
  return (
    <form action={action} method="get">
      <fieldset>
        <label>
          Duration{" "}
          <select name="hours" defaultValue={params.get("hours") ?? "2"}>
            {options.precomputed_hours.map((hours) => (
              <option key={hours} value={String(hours)}>
                {hours} hours
              </option>
            ))}
          </select>
        </label>{" "}
        <Tip name="duration" />
        <label>
          Forecast{" "}
          <select name="forecast" defaultValue={params.get("forecast") ?? "naive_last_week"}>
            {Object.entries(options.forecasts).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>{" "}
        <Tip name="forecast" />
        {services && (
          <>
            <label>
              Frequency response{" "}
              <select name="services" defaultValue={params.get("services") ?? "none"}>
                {Object.entries(options.services).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>{" "}
            <Tip name="response" />
          </>
        )}
        <label>
          Power (MW){" "}
          <input
            name="power_mw"
            type="number"
            defaultValue={power}
            min={options.power_range[0]}
            max={options.power_range[1]}
            step={0.1}
            required
          />
        </label>{" "}
        <Tip name="power" />
        <br />
        {children}
        <button type="submit">Show</button>
      </fieldset>
    </form>
  );
}
