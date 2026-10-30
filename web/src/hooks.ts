import { useEffect, useState } from "react";
import { ApiError } from "./api/client";

export type Loaded<T> =
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "done"; value: T };

/** Run ``load`` whenever ``key`` changes; messages come only from the API or a fixed text. */
export function useLoad<T>(load: () => Promise<T>, key: string): Loaded<T> {
  const [loaded, setLoaded] = useState<Loaded<T>>({ state: "loading" });
  useEffect(() => {
    let current = true;
    setLoaded({ state: "loading" });
    load().then(
      (value) => current && setLoaded({ state: "done", value }),
      (error: unknown) =>
        current &&
        setLoaded({
          state: "error",
          message:
            error instanceof ApiError ? error.message : "Something went wrong. Please try again.",
        }),
    );
    return () => {
      current = false;
    };
  }, [key]); // ``key`` stands for ``load``'s inputs
  return loaded;
}

/** Seconds since mounted, for "running for N s" messages. */
export function useElapsed(running: boolean): number {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!running) return;
    const started = Date.now();
    setSeconds(0);
    const tick = setInterval(() => setSeconds(Math.round((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(tick);
  }, [running]);
  return seconds;
}
