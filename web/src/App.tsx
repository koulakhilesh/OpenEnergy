import { useEffect, useState } from "react";
import { api } from "./api/client";
import { OptionsContext } from "./components/Tip";
import { useLoad } from "./hooks";
import { Arbitrage } from "./pages/Arbitrage";
import { Compare } from "./pages/Compare";
import { Explore } from "./pages/Explore";
import { Future } from "./pages/Future";
import { Home } from "./pages/Home";
import { Lab } from "./pages/Lab";
import { Play } from "./pages/Play";
import { Replay } from "./pages/Replay";
import { ResultPage } from "./pages/Result";
import { Run } from "./pages/Run";
import { Scenarios } from "./pages/Scenarios";

const TITLES: Record<string, string> = {
  "/": "OpenEnergy",
  "/lab": "Battery Lab | OpenEnergy",
  "/replay": "Grid replay | OpenEnergy",
  "/2035": "2035 | OpenEnergy",
  "/play": "Beat the battery | OpenEnergy",
  "/run": "Value a battery | OpenEnergy",
  "/result": "Battery value | OpenEnergy",
  "/explore": "Explore | OpenEnergy",
  "/compare": "Compare | OpenEnergy",
  "/scenarios": "FES pathways | OpenEnergy",
  "/embed/arbitrage": "How a battery earns | OpenEnergy",
};

const NAV: [string, string][] = [
  ["/lab", "Battery Lab"],
  ["/replay", "Grid replay"],
  ["/2035", "2035"],
  ["/play", "Beat the battery"],
  ["/run", "Value a battery"],
  ["/explore", "Explore"],
];

// Pages that run in the browser on static data; the rest ask the API.
const STATIC = ["/", "/lab", "/replay", "/2035", "/play"];

function StaticPage({ path, params }: { path: string; params: URLSearchParams }) {
  switch (path) {
    case "/lab":
      return <Lab params={params} />;
    case "/replay":
      return <Replay params={params} />;
    case "/2035":
      return <Future params={params} />;
    case "/play":
      return <Play params={params} />;
    default:
      return <Home />;
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
      <span className="mark" aria-hidden="true">
        <i className="c" />
        <i className="t" />
        <i className="s" />
      </span>
      OpenEnergy
    </a>
  );
}

/** Each page is its own URL (shareable); the query string holds the choices. */
export function App({ path, search }: { path: string; search: string }) {
  const [theme, setTheme] = useState(initialTheme);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  document.title = TITLES[path] ?? "OpenEnergy";
  const params = new URLSearchParams(search);
  if (path === "/embed/arbitrage") return <Arbitrage />;
  const wide = STATIC.includes(path);
  // ``?embed=1`` shows an in-browser page without the header, for the docs.
  if (wide && params.get("embed") === "1") {
    document.documentElement.dataset.embed = "true";
    return (
      <main className="wide embedded">
        <StaticPage path={path} params={params} />
      </main>
    );
  }
  return (
    <>
      <a className="skip" href="#content">
        Skip to content
      </a>
      <header className="top">
        <Brand />
        <nav aria-label="Main" className="tabs">
          {NAV.map(([href, name]) => (
            <a key={href} href={href} aria-current={href === path ? "page" : undefined}>
              {name}
            </a>
          ))}
          <a href="https://koulakhilesh.github.io/OpenEnergy/">Docs</a>
        </nav>
        <span className="spacer" />
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
      <main id="content" className={wide ? "wide" : "narrow"}>
        {wide ? <StaticPage path={path} params={params} /> : <WithOptions path={path} params={params} />}
      </main>
      <footer className="foot">
        Code MIT; data keep their own licences, credited on each page.{" "}
        <a href="https://github.com/koulakhilesh/OpenEnergy">Source</a> ·{" "}
        <a href="https://koulakhilesh.github.io/OpenEnergy/">Docs</a>
      </footer>
    </>
  );
}
