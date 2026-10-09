# Data

## Bundled extract

`data/time_series/time_series_60min_singleindex_filtered.csv` is an hourly extract of the
Open Power System Data time-series package covering Great Britain from 31 December 2014
to 30 September 2020. It contains the GB day-ahead price (in **GBP**/MWh), load, and solar
and wind generation and capacity. Timestamps are UTC (`utc_timestamp`).

Of 2,101 days, 2,085 have a complete set of prices. The gaps are two-hour holes on the
spring clock change each year, two single missing hours, and four outages of about a day.
With the default `max_gap_hours: 2`, the short gaps are interpolated and the outages are
skipped.

Prices include genuine scarcity spikes, up to £999/MWh in September–November 2016;
they are kept.

## Renewable capacity factors

The extract also has hourly capacity-factor profiles (generation divided by installed
capacity) for `solar`, `wind`, `wind_onshore` and `wind_offshore`, from 2015 to
29 December 2019; OPSD stops publishing capacity after that.

In 233 hours the solar profile exceeds 1.0 (up to 1.367): reported capacity lags new
build, so generation divided by capacity overshoots. OpenEnergy clips profiles to [0, 1]
and reports how many values were clipped. The same lag pushes GB solar capacity factors to
15–18%, above the roughly 11% usually quoted; this changes absolute output but not
capture rates, which depend on the shape of the profile.

Other OPSD zones can be used by pointing `data.path` at a larger OPSD
`time_series_*_singleindex.csv`. OPSD publishes GB prices in GBP and all other zones in
EUR; OpenEnergy labels the currency accordingly.

## Carbon intensity

`data/carbon_intensity/gb_national.csv` holds GB national carbon intensity for every
half-hour from 1 January 2018 to 30 September 2020: NESO's forecast and its estimated
actual, in gCO2/kWh. It was downloaded with `scripts/fetch_carbon_intensity.py` and is
stored exactly as published.

The archive has 438 half-hours without an actual value (nine runs, the longest about three
days) and 16 implausible forecasts (up to 13,579 gCO2/kWh). OpenEnergy treats any value
outside 0–1000 gCO2/kWh as missing and reports how many it rejected. Annual mean actual
intensity falls from 248 (2018) to 214 (2019) and 182 gCO2/kWh (2020 to September).

These are **average** intensities of the whole system. Storage and renewables change the
**marginal** plant, whose emissions can differ; emissions results in OpenEnergy show
direction and rough scale, not causal impact.

## Attribution

**Prices, load and renewables**

> Open Power System Data. 2020. Data Package Time series. Version 2020-10-06.
> <https://doi.org/10.25832/time_series/2020-10-06>.
> (Primary data from various sources, for a complete list see URL).

The primary price and load data come from the ENTSO-E Transparency Platform.

**Carbon intensity**

> National Energy System Operator (NESO). Carbon Intensity API.
> <https://carbonintensity.org.uk/>. Licensed under
> [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/);
> [terms of use](https://github.com/carbon-intensity/terms).

OpenEnergy treats out-of-range values as missing and averages half-hours to the analysis
step; the bundled file itself is unchanged. OpenEnergy is not affiliated with or endorsed
by Open Power System Data or NESO.

Each data folder has a `README.md` with the full source, licence and known issues, and
every `summary.json` repeats the attribution for the data a run used.
