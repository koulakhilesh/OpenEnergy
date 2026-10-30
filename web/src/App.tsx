import { api } from "./api/client";
import { OptionsContext } from "./components/Tip";
import { useLoad } from "./hooks";
import { Compare } from "./pages/Compare";
import { Explore } from "./pages/Explore";
import { Home } from "./pages/Home";
import { ResultPage } from "./pages/Result";
import { Scenarios } from "./pages/Scenarios";

const TITLES: Record<string, string> = {
  "/": "OpenEnergy",
  "/result": "Battery value | OpenEnergy",
  "/explore": "Explore | OpenEnergy",
  "/compare": "Compare | OpenEnergy",
  "/scenarios": "FES pathways | OpenEnergy",
};

function Page({ path, params }: { path: string; params: URLSearchParams }) {
  switch (path) {
    case "/result":
      return <ResultPage params={params} />;
    case "/explore":
      return <Explore params={params} />;
    case "/compare":
      return <Compare params={params} />;
    case "/scenarios":
      return <Scenarios />;
    case "/":
      return <Home />;
    default:
      return (
        <>
          <h1>Not found</h1>
          <p>
            <a href="/">Back to OpenEnergy</a>
          </p>
        </>
      );
  }
}

/** Each page is its own URL (shareable); the query string holds the choices. */
export function App({ path, search }: { path: string; search: string }) {
  const options = useLoad(api.options, "options");
  document.title = TITLES[path] ?? "OpenEnergy";
  return (
    <main>
      <nav aria-label="Main">
        <a href="/">Battery value</a>
        <a href="/explore">Explore</a>
        <a href="/compare">Compare</a>
        <a href="/scenarios">FES pathways</a>
        <a href="https://koulakhilesh.github.io/OpenEnergy/">Docs</a>
      </nav>
      {options.state === "loading" && <p aria-live="polite">Loading…</p>}
      {options.state === "error" && <p role="alert">{options.message}</p>}
      {options.state === "done" && (
        <OptionsContext.Provider value={options.value}>
          <Page path={path} params={new URLSearchParams(search)} />
        </OptionsContext.Provider>
      )}
      <p className="source">
        OpenEnergy {options.state === "done" ? options.value.version : ""}. Code MIT; data keep
        their own licences, credited with each result.
      </p>
    </main>
  );
}
