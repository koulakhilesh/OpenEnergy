import highsLoader, { type Highs } from "highs";
import wasmUrl from "highs/runtime?url";

let loading: Promise<Highs> | null = null;

/** HiGHS (WebAssembly, about 3 MB), fetched once on first use. */
export function loadHighs(): Promise<Highs> {
  loading ??= highsLoader({ locateFile: () => wasmUrl });
  return loading;
}
