const PAGES: [href: string, title: string, text: string][] = [
  ["/run", "Value a battery", "A whole year of trading, with frequency response, on any GB year from 2017 or a FES pathway."],
  ["/explore", "Explore", "Every year and pathway at a glance, for 1, 2 and 4-hour batteries."],
  ["/compare?item=gb-2019&item=gb-2022&item=gb-2025", "Compare", "Years and pathways side by side, day by day."],
  ["/scenarios", "FES pathways", "The modelled 2030 and 2035 systems against NESO's own numbers."],
  [
    "https://koulakhilesh.github.io/OpenEnergy/guides/web-app/",
    "JSON API",
    "Every result as JSON from /api, typed by an OpenAPI schema, and the CSV and YAML downloads.",
  ],
  ["https://koulakhilesh.github.io/OpenEnergy/findings/", "Findings", "What the models found, with the numbers behind them."],
];

/** The analyst pages: whole-year results from the API, tables and downloads. */
export function Research() {
  return (
    <section className="lens">
      <p className="kicker">Research · whole years, pathways and downloads</p>
      <h1>For analysts</h1>
      <p className="lede">
        Precomputed and live backtests from the Python engine, with tables, CSV and scenario files to take away.
      </p>
      <div className="tiles">
        {PAGES.map(([href, title, text]) => (
          <a key={href} className="tile" href={href}>
            <b>{title}</b>
            <span>{text}</span>
          </a>
        ))}
      </div>
    </section>
  );
}
