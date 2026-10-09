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

## Attribution

> Open Power System Data. 2020. Data Package Time series. Version 2020-10-06.
> <https://doi.org/10.25832/time_series/2020-10-06>.
> (Primary data from various sources, for a complete list see URL).

The primary price and load data come from the ENTSO-E Transparency Platform. Every
`summary.json` written by OpenEnergy repeats this attribution.
