"""What happens to GB net load as wind and solar grow?

Scales 2019 wind and solar output from x1 to x4 and reports renewable share, minimum net
load, ramps and the surplus above an 8 GW must-run floor, then sizes storage for x3.

Run: uv run python examples/renewables_scaling.py
"""

from datetime import date
from pathlib import Path

from openenergy.data import OPSDCsvSource
from openenergy.system import load_system, net_load, netload_by_year, sizing_grid

DATA = Path(__file__).parents[1] / "data/time_series/time_series_60min_singleindex_filtered.csv"
MUST_RUN_MW = 8000.0


def main() -> None:
    system = load_system(OPSDCsvSource(DATA), "GB_GBN", date(2019, 1, 1), date(2019, 12, 31))
    print(
        f"GB 2019, must-run {MUST_RUN_MW / 1e3:g} GW, {system.load_flagged} load glitches removed\n"
    )
    print(
        f"{'scale':>6}{'RE share':>10}{'min GW':>8}{'ramp1h GW':>11}{'surplus TWh':>13}{'of RE':>8}"
    )
    for scale in (1, 2, 3, 4):
        (stats,) = netload_by_year(system.frame, scale, scale, MUST_RUN_MW)
        print(
            f"{scale:>6}{stats.renewable_share:>10.1%}{stats.min_net_mw / 1e3:>8.1f}"
            f"{stats.ramp_1h_p99_mw / 1e3:>11.1f}{stats.surplus_mwh / 1e6:>13.2f}"
            f"{stats.surplus_share:>8.1%}"
        )

    net = net_load(system.frame, 3, 3)
    grid = sizing_grid(net, [2000, 5000, 10000], [4, 8, 24], must_run_mw=MUST_RUN_MW)
    table = grid.pivot(index="power_mw", columns="hours", values="absorbed_share")
    print("\nshare of x3 surplus absorbed by storage")
    print(f"{'GW':>6}" + "".join(f"{f'{h:g}h':>8}" for h in table.columns))
    for power in table.index:
        print(f"{power / 1e3:>6.0f}" + "".join(f"{v:>8.1%}" for v in table.loc[power]))


if __name__ == "__main__":
    main()
