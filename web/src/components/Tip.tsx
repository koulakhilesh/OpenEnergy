import { createContext, useContext } from "react";
import type { Options } from "../api/client";

export const OptionsContext = createContext<Options | null>(null);

export function useOptions(): Options {
  const options = useContext(OptionsContext);
  if (!options) throw new Error("options not loaded");
  return options;
}

/** A focusable "?" that shows the explanation on hover, focus or tap. */
export function Tip({ name }: { name: string }) {
  const text = useOptions().help[name] ?? "";
  return (
    <span className="tip" tabIndex={0} role="note" aria-label={text} data-tip={text}>
      ?
    </span>
  );
}
