import { useEffect, useState } from "react";
import { api } from "./api/client";
import { OptionsContext } from "./components/Tip";
import { useLoad } from "./hooks";
import { Arbitrage } from "./pages/Arbitrage";
import { Compare } from "./pages/Compare";
import { Explore } from "./pages/Explore";
import { ResultPage } from "./pages/Result";
import { Run } from "./pages/Run";
import { Scenarios } from "./pages/Scenarios";
import { Fleet } from "./sim/Fleet";
import { Future } from "./sim/Future";
import { Play } from "./sim/Play";
import { Research } from "./sim/Research";
import { Simulator } from "./sim/Simulator";

const TITLES: Record<string, string> = {
  "/": "OpenEnergy · Britain's grid, hour by hour",
  "/play": "Beat the battery | OpenEnergy",
  "/2035": "2035 | OpenEnergy",
  "/fleet": "Real batteries | OpenEnergy",
  "/research": "Research | OpenEnergy",
  "/run": "Value a battery | OpenEnergy",
  "/result": "Battery value | OpenEnergy",
  "/explore": "Explore | OpenEnergy",
  "/compare": "Compare | OpenEnergy",
  "/scenarios": "FES pathways | OpenEnergy",
  "/embed/arbitrage": "How a battery earns | OpenEnergy",
};

const LENSES: [string, string][] = [
  ["/", "Simulator"],
  ["/play", "Play"],
  ["/2035", "2035"],
  ["/fleet", "Real batteries"],
  ["/research", "Research"],
];

// Lenses run in the browser on static data; the research pages ask the API.
const STATIC = ["/", "/play", "/2035", "/fleet", "/research"];
// v6.0 addresses, now views of the simulator; their queries still work.
const MOVED: Record<string, string> = { "/lab": "/", "/replay": "/" };

function StaticPage({ path, params, embedded }: { path: string; params: URLSearchParams; embedded: boolean }) {
  switch (path) {
    case "/2035":
      return <Future params={params} />;
    case "/play":
      return <Play params={params} />;
    case "/fleet":
      return <Fleet params={params} />;
    case "/research":
      return <Research />;
    default:
      return <Simulator params={params} embedded={embedded} />;
  }
}

function ApiPage({ path, params }: { path: string; params: URLSearchParams }) {
  switch (path) {
    case "/run":
      return <Run />;
    case "/result":
      return <ResultPage params={params} />;
    case "/explore":
      return <Explore params={params} />;
    case "/compare":
      return <Compare params={params} />;
    case "/scenarios":
      return <Scenarios />;
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

function WithOptions({ path, params }: { path: string; params: URLSearchParams }) {
  const options = useLoad(api.options, "options");
  return (
    <>
      {options.state === "loading" && <p aria-live="polite">Loading…</p>}
      {options.state === "error" && <p role="alert">{options.message}</p>}
      {options.state === "done" && (
        <OptionsContext.Provider value={options.value}>
          <ApiPage path={path} params={params} />
          <p className="source">
            OpenEnergy {options.value.version}. Code MIT; data keep their own licences, credited with
            each result.
          </p>
        </OptionsContext.Provider>
      )}
    </>
  );
}

function initialTheme(): "light" | "dark" {
  const saved = typeof localStorage !== "undefined" ? localStorage.getItem("theme") : null;
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function Brand() {
  return (
    <a className="brand" href="/">
      <img src="/assets/logo.png" alt="" width={28} height={28} />
      OpenEnergy
    </a>
  );
}

/** Each page is its own URL (shareable); the query string holds the choices. */
export function App({ path: asked, search }: { path: string; search: string }) {
  const [theme, setTheme] = useState(initialTheme);
  const path = MOVED[asked] ?? asked;
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  useEffect(() => {
    // The page may already have written its own address (child effects run first).
    if (path !== asked && window.location.pathname === asked) window.history.replaceState(null, "", `${path}${search}`);
  }, [path, asked, search]);
  document.title = TITLES[path] ?? "OpenEnergy";
  const params = new URLSearchParams(search);
  if (path === "/embed/arbitrage") return <Arbitrage />;
  const lens = STATIC.includes(path);
  // ``?embed=1`` shows a lens without the header, for the docs.
  if (lens && params.get("embed") === "1") {
    document.documentElement.dataset.embed = "true";
    return (
      <main className={path === "/" ? "sim-main embedded" : "wide embedded"}>
        <StaticPage path={path} params={params} embedded />
      </main>
    );
  }
  const current = lens ? path : "/research";
  return (
    <>
      <a className="skip" href="#content">
        Skip to content
      </a>
      <header className="top">
        <Brand />
        <nav aria-label="Main" className="tabs">
          {LENSES.map(([href, name]) => (
            <a key={href} href={href} aria-current={href === current ? "page" : undefined}>
              {name}
            </a>
          ))}
        </nav>
        <span className="spacer" />
        <a className="btn ghost small" href="https://koulakhilesh.github.io/OpenEnergy/">
          Docs ↗
        </a>
        <button
          type="button"
          className="btn ghost small"
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          onClick={() => {
            const next = theme === "dark" ? "light" : "dark";
            localStorage.setItem("theme", next);
            setTheme(next);
          }}
        >
          {theme === "dark" ? "Light" : "Dark"}
        </button>
      </header>
      <main id="content" className={path === "/" ? "sim-main" : lens ? "wide" : "narrow"}>
        {lens ? <StaticPage path={path} params={params} embedded={false} /> : <WithOptions path={path} params={params} />}
      </main>
      {path !== "/" && (
        <footer className="foot">
          Code MIT; data keep their own licences, credited on each page.{" "}
          <a href="https://github.com/koulakhilesh/OpenEnergy">Source</a> ·{" "}
          <a href="https://koulakhilesh.github.io/OpenEnergy/">Docs</a>
        </footer>
      )}
    </>
  );
}
