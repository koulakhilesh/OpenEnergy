import datetime
import typing as t

import pandas as pd
import pyomo.environ as pyo

from scripts.assets import Battery
from scripts.optimizer import PyomoOptimizationModelBuilder
from scripts.shared import Logger

from .interfaces import IRenewableOptimizer


class RenewablePortfolioOptimizer(IRenewableOptimizer):
    """
    Optimizer for renewable energy portfolios including solar, wind, and battery storage.

    This optimizer uses mixed-integer linear programming to maximize revenue
    from renewable energy generation and battery storage operations.
    """

    def __init__(self, logger_level: int = Logger.INFO):
        """Initialize the renewable portfolio optimizer.

        Args:
            logger_level (int): Logging level.
        """
        self.logger = Logger(logger_level)

    def optimize_portfolio(
        self,
        solar_capacity: float,
        wind_capacity: float,
        battery_capacity: float,
        prices: t.List[float],
        date: datetime.date,
        solar_generation: t.Optional[t.List[float]] = None,
        wind_generation: t.Optional[t.List[float]] = None,
    ) -> t.Dict[str, t.Any]:
        """Optimize renewable portfolio operation.

        Args:
            solar_capacity (float): Solar capacity in MW.
            wind_capacity (float): Wind capacity in MW.
            battery_capacity (float): Battery capacity in MWh.
            prices (List[float]): Hourly electricity prices.
            date (datetime.date): Operating date.
            solar_generation (List[float], optional): Hourly solar generation forecast.
            wind_generation (List[float], optional): Hourly wind generation forecast.

        Returns:
            Dict: Optimization results including dispatch schedules and revenues.
        """
        try:
            # Create optimization model
            model = self._build_portfolio_model(
                solar_capacity,
                wind_capacity,
                battery_capacity,
                prices,
                solar_generation or [0] * 24,
                wind_generation or [0] * 24,
            )

            # Solve the model
            solver = pyo.SolverFactory("glpk")
            results = solver.solve(model, tee=False)

            if results.solver.termination_condition == pyo.TerminationCondition.optimal:
                return self._extract_results(model, date)
            else:
                self.logger.warning("Optimization failed, using heuristic solution")
                return self._get_heuristic_solution(
                    solar_capacity,
                    wind_capacity,
                    battery_capacity,
                    prices,
                    date,
                    solar_generation or [0] * 24,
                    wind_generation or [0] * 24,
                )

        except Exception as e:
            self.logger.error(f"Optimization error: {e}")
            return self._get_heuristic_solution(
                solar_capacity,
                wind_capacity,
                battery_capacity,
                prices,
                date,
                solar_generation or [0] * 24,
                wind_generation or [0] * 24,
            )

    def _build_portfolio_model(
        self,
        solar_capacity: float,
        wind_capacity: float,
        battery_capacity: float,
        prices: t.List[float],
        solar_generation: t.List[float],
        wind_generation: t.List[float],
    ) -> pyo.ConcreteModel:
        """Build the optimization model for the renewable portfolio."""
        model = pyo.ConcreteModel()

        # Time periods
        model.T = pyo.RangeSet(0, 23)

        # Variables
        model.solar_dispatch = pyo.Var(
            model.T, within=pyo.NonNegativeReals, bounds=(0, solar_capacity)
        )
        model.wind_dispatch = pyo.Var(
            model.T, within=pyo.NonNegativeReals, bounds=(0, wind_capacity)
        )
        model.battery_charge = pyo.Var(
            model.T, within=pyo.NonNegativeReals, bounds=(0, battery_capacity)
        )
        model.battery_discharge = pyo.Var(
            model.T, within=pyo.NonNegativeReals, bounds=(0, battery_capacity)
        )
        model.battery_soc = pyo.Var(
            model.T,
            within=pyo.NonNegativeReals,
            bounds=(0.05 * battery_capacity, 0.95 * battery_capacity),
        )

        # Parameters
        model.prices = pyo.Param(model.T, initialize=dict(enumerate(prices)))
        model.solar_available = pyo.Param(
            model.T, initialize=dict(enumerate(solar_generation))
        )
        model.wind_available = pyo.Param(
            model.T, initialize=dict(enumerate(wind_generation))
        )

        # Objective: Maximize revenue
        def revenue_rule(m):
            return sum(
                m.prices[t]
                * (
                    m.solar_dispatch[t]
                    + m.wind_dispatch[t]
                    + m.battery_discharge[t]
                    - m.battery_charge[t]
                )
                for t in m.T
            )

        model.objective = pyo.Objective(rule=revenue_rule, sense=pyo.maximize)

        # Constraints
        # Solar generation limits
        def solar_limit_rule(m, t):
            return m.solar_dispatch[t] <= m.solar_available[t]

        model.solar_limit = pyo.Constraint(model.T, rule=solar_limit_rule)

        # Wind generation limits
        def wind_limit_rule(m, t):
            return m.wind_dispatch[t] <= m.wind_available[t]

        model.wind_limit = pyo.Constraint(model.T, rule=wind_limit_rule)

        # Battery SOC evolution
        def soc_evolution_rule(m, t):
            if t == 0:
                return (
                    m.battery_soc[t]
                    == 0.5 * battery_capacity
                    + m.battery_charge[t] * 0.9
                    - m.battery_discharge[t] / 0.9
                )
            else:
                return (
                    m.battery_soc[t]
                    == m.battery_soc[t - 1]
                    + m.battery_charge[t] * 0.9
                    - m.battery_discharge[t] / 0.9
                )

        model.soc_evolution = pyo.Constraint(model.T, rule=soc_evolution_rule)

        # Battery charge/discharge mutual exclusivity (simplified)
        def battery_operation_rule(m, t):
            return m.battery_charge[t] + m.battery_discharge[t] <= battery_capacity

        model.battery_operation = pyo.Constraint(model.T, rule=battery_operation_rule)

        return model

    def _extract_results(
        self, model: pyo.ConcreteModel, date: datetime.date
    ) -> t.Dict[str, t.Any]:
        """Extract optimization results from the solved model."""
        results = {
            "date": date,
            "optimal_value": pyo.value(model.objective),
            "dispatch_schedule": [],
            "summary": {},
        }

        total_solar_dispatch = 0
        total_wind_dispatch = 0
        total_battery_charge = 0
        total_battery_discharge = 0
        total_revenue = 0

        for t in model.T:
            hour_data = {
                "hour": t,
                "solar_dispatch_mw": pyo.value(model.solar_dispatch[t]),
                "wind_dispatch_mw": pyo.value(model.wind_dispatch[t]),
                "battery_charge_mw": pyo.value(model.battery_charge[t]),
                "battery_discharge_mw": pyo.value(model.battery_discharge[t]),
                "battery_soc_mwh": pyo.value(model.battery_soc[t]),
                "price": pyo.value(model.prices[t]),
                "net_export_mw": (
                    pyo.value(model.solar_dispatch[t])
                    + pyo.value(model.wind_dispatch[t])
                    + pyo.value(model.battery_discharge[t])
                    - pyo.value(model.battery_charge[t])
                ),
            }

            hour_revenue = hour_data["net_export_mw"] * hour_data["price"]
            hour_data["revenue"] = hour_revenue

            results["dispatch_schedule"].append(hour_data)

            total_solar_dispatch += hour_data["solar_dispatch_mw"]
            total_wind_dispatch += hour_data["wind_dispatch_mw"]
            total_battery_charge += hour_data["battery_charge_mw"]
            total_battery_discharge += hour_data["battery_discharge_mw"]
            total_revenue += hour_revenue

        results["summary"] = {
            "total_solar_dispatch_mwh": total_solar_dispatch,
            "total_wind_dispatch_mwh": total_wind_dispatch,
            "total_battery_charge_mwh": total_battery_charge,
            "total_battery_discharge_mwh": total_battery_discharge,
            "total_revenue": total_revenue,
            "battery_efficiency": total_battery_discharge / total_battery_charge
            if total_battery_charge > 0
            else 0,
        }

        return results

    def _get_heuristic_solution(
        self,
        solar_capacity: float,
        wind_capacity: float,
        battery_capacity: float,
        prices: t.List[float],
        date: datetime.date,
        solar_generation: t.List[float],
        wind_generation: t.List[float],
    ) -> t.Dict[str, t.Any]:
        """Get a heuristic solution when optimization fails."""
        results: t.Dict[str, t.Any] = {
            "date": date,
            "optimal_value": 0,
            "dispatch_schedule": [],
            "summary": {},
        }

        total_revenue: float = 0.0

        for hour in range(24):
            price = prices[hour] if hour < len(prices) else (prices[-1] if prices else 0.0)
            solar_gen = solar_generation[hour] if hour < len(solar_generation) else 0
            wind_gen = wind_generation[hour] if hour < len(wind_generation) else 0

            # Simple heuristic: dispatch all available renewable generation
            hour_data = {
                "hour": hour,
                "solar_dispatch_mw": min(solar_gen, solar_capacity),
                "wind_dispatch_mw": min(wind_gen, wind_capacity),
                "battery_charge_mw": 0,  # No battery optimization in heuristic
                "battery_discharge_mw": 0,
                "battery_soc_mwh": 0.5 * battery_capacity,
                "price": price,
                "net_export_mw": min(solar_gen, solar_capacity)
                + min(wind_gen, wind_capacity),
            }

            hour_revenue = hour_data["net_export_mw"] * price
            hour_data["revenue"] = hour_revenue
            total_revenue += hour_revenue

            dispatch_schedule = t.cast(
                t.List[t.Dict[str, t.Any]], results["dispatch_schedule"]
            )
            dispatch_schedule.append(hour_data)

        results["optimal_value"] = total_revenue
        dispatch_schedule = t.cast(
            t.List[t.Dict[str, t.Any]], results["dispatch_schedule"]
        )
        results["summary"] = {
            "total_solar_dispatch_mwh": sum(
                h["solar_dispatch_mw"] for h in dispatch_schedule
            ),
            "total_wind_dispatch_mwh": sum(
                h["wind_dispatch_mw"] for h in dispatch_schedule
            ),
            "total_battery_charge_mwh": 0,
            "total_battery_discharge_mwh": 0,
            "total_revenue": total_revenue,
            "battery_efficiency": 0,
        }

        return results
