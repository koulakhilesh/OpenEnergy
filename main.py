import argparse
import os
import typing as t
from datetime import date, datetime

import numpy as np
import pandas as pd

from scripts.assets import Battery
from scripts.forecast import FeatureEngineer
from scripts.market_simulator import EnergyMarketSimulator, PnLCalculator
from scripts.optimizer import (
    BatteryOptimizationScheduler,
    GLPKOptimizationSolver,
    PyomoModelExtractor,
    PyomoOptimizationModelBuilder,
)
from scripts.prices import (
    ForecastPriceModel,
    HistoricalAveragePriceModel,
    SimulatedPriceEnvelopeGenerator,
    SimulatedPriceModel,
    SimulatedPriceNoiseAdder,
)
from scripts.shared import CSVDataProvider, Logger


def create_price_model(args):
    if args.price_model == "SimulatedPriceModel":
        envelope_generator = SimulatedPriceEnvelopeGenerator()
        noise_adder = SimulatedPriceNoiseAdder()
        return SimulatedPriceModel(
            envelope_generator=envelope_generator, noise_adder=noise_adder
        )

    elif args.price_model == "HistoricalPriceModel":
        data_provider = CSVDataProvider(args.csv_path)
        return HistoricalAveragePriceModel(data_provider=data_provider)

    elif args.price_model == "ForecastedPriceModel":
        data_provider = CSVDataProvider(args.csv_path)
        feature_engineer = FeatureEngineer()
        pretrained_model = ForecastPriceModel.load_model(args.price_forecast_model)
        return ForecastPriceModel(
            data_provider=data_provider,
            feature_engineer=feature_engineer,
            model=pretrained_model,
        )


def create_battery(args):
    return Battery(
        capacity_mwh=args.battery_capacity,
        charge_efficiency=args.charge_efficiency,
        discharge_efficiency=args.discharge_efficiency,
    )


def create_scheduler(battery, args):
    model_builder = PyomoOptimizationModelBuilder()
    solver = GLPKOptimizationSolver(args.log_level)
    model_extractor = PyomoModelExtractor()
    return BatteryOptimizationScheduler(
        battery=battery,
        model_builder=model_builder,
        solver=solver,
        model_extractor=model_extractor,
    )


def create_dependencies(args):
    price_model = create_price_model(args)
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    battery = create_battery(args)
    scheduler = create_scheduler(battery, args)
    pnl_calculator = PnLCalculator(battery=battery)

    return start_date, end_date, battery, price_model, pnl_calculator, scheduler


def run_simulation(
    args=None,
) -> t.Optional[t.List[t.Tuple[date, pd.DataFrame, np.float64]]]:
    # Parse command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--battery_capacity", type=np.float64, default=1.0)
    parser.add_argument("--charge_efficiency", type=np.float64, default=0.9)
    parser.add_argument("--discharge_efficiency", type=np.float64, default=0.9)
    parser.add_argument("--start_date", type=str, default="2015-02-01")
    parser.add_argument("--end_date", type=str, default="2015-02-02")
    parser.add_argument("--price_model", type=str, default="SimulatedPriceModel")
    parser.add_argument(
        "--csv_path",
        type=str,
        default=os.path.join(
            "data", "time_series", "time_series_60min_singleindex_filtered.csv"
        ),
    )
    parser.add_argument(
        "--price_forecast_model",
        type=str,
        default=os.path.join("models", "prices", "price_forecast_model.pkl"),
    )
    parser.add_argument("--log_level", type=str, default="INFO")

    if args is None:
        args = parser.parse_args()
    else:
        args = parser.parse_args(args)

    log_level = getattr(Logger, args.log_level.upper(), Logger.INFO)
    logger = Logger(log_level)

    try:
        (
            start_date,
            end_date,
            battery,
            price_model,
            pnl_calculator,
            scheduler,
        ) = create_dependencies(args)

        # Create an instance of EnergyMarketSimulator with SimulatedPriceModel
        simulator = EnergyMarketSimulator(
            start_date=start_date,
            end_date=end_date,
            battery=battery,
            price_model=price_model,
            pnl_calculator=pnl_calculator,
            scheduler=scheduler,
            log_level=log_level,
        )
        # Run the simulation
        results = simulator.simulate()
        logger.debug(f"Simulation results with SimulatedPriceModel: \n{results}")
        return results

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return None


if __name__ == "__main__":
    run_simulation()
