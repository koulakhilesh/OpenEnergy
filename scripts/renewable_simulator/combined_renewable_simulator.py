import datetime
import typing as t
from dataclasses import dataclass

import pandas as pd

from scripts.assets import Battery, PVSystem, WindSystem
from scripts.pv_generation_models.interfaces import IPVData
from scripts.wind_generation_models.interfaces import IWindData

from .interfaces import IRenewablePortfolio


@dataclass
class RenewableAsset:
    """Data class representing a renewable energy asset."""

    name: str
    asset_type: str  # 'solar', 'wind', 'battery'
    capacity_mw: float
    system: t.Union[PVSystem, WindSystem, Battery]
    data_provider: t.Union[IPVData, IWindData, None]


class CombinedRenewableSimulator(IRenewablePortfolio):
    """
    Combined renewable energy simulator supporting solar, wind, and battery storage.

    This simulator manages a portfolio of renewable assets and can optimize
    their combined operation for maximum economic benefit.
    """

    def __init__(self):
        """Initialize the combined renewable simulator."""
        self.assets: t.List[RenewableAsset] = []
        self.battery: t.Optional[Battery] = None

    def add_solar_asset(
        self,
        name: str,
        capacity_mw: float,
        pv_system: PVSystem,
        pv_data: IPVData,
    ) -> None:
        """Add a solar PV asset to the portfolio.

        Args:
            name (str): Asset name.
            capacity_mw (float): Solar capacity in MW.
            pv_system (PVSystem): PV system configuration.
            pv_data (IPVData): PV generation data provider.
        """
        asset = RenewableAsset(
            name=name,
            asset_type="solar",
            capacity_mw=capacity_mw,
            system=pv_system,
            data_provider=pv_data,
        )
        self.assets.append(asset)

    def add_wind_asset(
        self,
        name: str,
        capacity_mw: float,
        wind_system: WindSystem,
        wind_data: IWindData,
    ) -> None:
        """Add a wind asset to the portfolio.

        Args:
            name (str): Asset name.
            capacity_mw (float): Wind capacity in MW.
            wind_system (WindSystem): Wind system configuration.
            wind_data (IWindData): Wind generation data provider.
        """
        asset = RenewableAsset(
            name=name,
            asset_type="wind",
            capacity_mw=capacity_mw,
            system=wind_system,
            data_provider=wind_data,
        )
        self.assets.append(asset)

    def add_battery_storage(self, battery: Battery) -> None:
        """Add battery storage to the portfolio.

        Args:
            battery (Battery): Battery system.
        """
        self.battery = battery
        asset = RenewableAsset(
            name="battery_storage",
            asset_type="battery",
            capacity_mw=battery.capacity_mwh,  # Using capacity as proxy
            system=battery,
            data_provider=None,
        )
        self.assets.append(asset)

    def calculate_total_generation(
        self, date: datetime.date
    ) -> t.Tuple[t.List[float], t.List[float]]:
        """Calculate total generation from all renewable assets.

        Args:
            date (datetime.date): The date for generation calculation.

        Returns:
            Tuple[List[float], List[float]]: Total actual and potential generation.
        """
        total_actual = [0.0] * 24
        total_potential = [0.0] * 24

        for asset in self.assets:
            if asset.asset_type in ["solar", "wind"] and asset.data_provider:
                actual, potential = asset.data_provider.get_generation(date)

                # Add to totals
                for hour in range(24):
                    total_actual[hour] += actual[hour] if hour < len(actual) else 0
                    total_potential[hour] += (
                        potential[hour] if hour < len(potential) else 0
                    )

        return total_actual, total_potential

    def get_asset_breakdown(
        self, date: datetime.date
    ) -> t.Dict[str, t.Tuple[t.List[float], t.List[float]]]:
        """Get generation breakdown by asset type.

        Args:
            date (datetime.date): The date for generation calculation.

        Returns:
            Dict: Asset type mapped to (actual, potential) generation tuples.
        """
        breakdown = {}

        for asset in self.assets:
            if asset.asset_type in ["solar", "wind"] and asset.data_provider:
                actual, potential = asset.data_provider.get_generation(date)

                if asset.asset_type not in breakdown:
                    breakdown[asset.asset_type] = ([0.0] * 24, [0.0] * 24)

                # Aggregate by asset type
                for hour in range(24):
                    breakdown[asset.asset_type][0][hour] += (
                        actual[hour] if hour < len(actual) else 0
                    )
                    breakdown[asset.asset_type][1][hour] += (
                        potential[hour] if hour < len(potential) else 0
                    )

        return breakdown

    def optimize_dispatch(
        self, date: datetime.date, prices: t.List[float]
    ) -> pd.DataFrame:
        """Optimize renewable energy dispatch based on prices.

        Args:
            date (datetime.date): The date for optimization.
            prices (List[float]): Hourly electricity prices.

        Returns:
            pd.DataFrame: Optimized dispatch schedule.
        """
        # Get renewable generation forecasts
        total_actual, total_potential = self.calculate_total_generation(date)

        # Create dispatch schedule
        dispatch_data = []

        for hour in range(24):
            hour_price = prices[hour] if hour < len(prices) else prices[-1]
            renewable_gen = total_actual[hour] if hour < len(total_actual) else 0

            # Simple dispatch strategy: sell all renewable generation
            # In a more sophisticated implementation, this would include
            # battery optimization and curtailment decisions
            dispatch_data.append(
                {
                    "hour": hour,
                    "renewable_generation_mw": renewable_gen,
                    "battery_charge_mw": 0,  # Placeholder
                    "battery_discharge_mw": 0,  # Placeholder
                    "net_export_mw": renewable_gen,
                    "revenue": renewable_gen * hour_price,
                    "price": hour_price,
                }
            )

        return pd.DataFrame(dispatch_data)

    def calculate_portfolio_metrics(
        self, date: datetime.date, prices: t.List[float]
    ) -> t.Dict[str, float]:
        """Calculate portfolio performance metrics.

        Args:
            date (datetime.date): The date for calculation.
            prices (List[float]): Hourly electricity prices.

        Returns:
            Dict: Portfolio performance metrics.
        """
        total_actual, total_potential = self.calculate_total_generation(date)
        dispatch_schedule = self.optimize_dispatch(date, prices)

        # Calculate metrics
        total_generation_mwh = sum(total_actual)
        total_potential_mwh = sum(total_potential)
        capacity_factor = (
            total_generation_mwh / total_potential_mwh if total_potential_mwh > 0 else 0
        )
        total_revenue = dispatch_schedule["revenue"].sum()
        average_price = sum(prices) / len(prices) if prices else 0

        return {
            "total_generation_mwh": total_generation_mwh,
            "total_potential_mwh": total_potential_mwh,
            "capacity_factor": capacity_factor,
            "total_revenue": total_revenue,
            "average_price_per_mwh": average_price,
            "revenue_per_mwh": total_revenue / total_generation_mwh
            if total_generation_mwh > 0
            else 0,
        }

    def get_portfolio_summary(self) -> t.Dict[str, t.Any]:
        """Get a summary of the renewable portfolio.

        Returns:
            Dict: Portfolio summary including asset counts and capacities.
        """
        summary: t.Dict[str, t.Any] = {
            "total_assets": len(self.assets),
            "asset_types": {},
            "total_capacity_mw": 0.0,
            "has_battery": self.battery is not None,
        }

        for asset in self.assets:
            asset_types: t.Dict[str, t.Any] = summary["asset_types"]
            if asset.asset_type not in asset_types:
                asset_types[asset.asset_type] = {
                    "count": 0,
                    "total_capacity_mw": 0.0,
                }

            asset_types[asset.asset_type]["count"] += 1
            asset_types[asset.asset_type]["total_capacity_mw"] += asset.capacity_mw
            summary["total_capacity_mw"] = (
                float(summary["total_capacity_mw"]) + asset.capacity_mw
            )

        return summary
