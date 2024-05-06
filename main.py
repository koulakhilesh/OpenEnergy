import argparse
import os
from datetime import datetime

from scripts.assets import Battery
from scripts.market_simulator import EnergyMarketSimulator, PnLCalculator
from scripts.optimizer import (
    BatteryOptimizationScheduler,
    GLPKOptimizationSolver,
    PyomoModelExtractor,
    PyomoOptimizationModelBuilder,
)
from scripts.prices import (
    CSVDataProvider,
    HistoricalAveragePriceModel,
    SimulatedPriceEnvelopeGenerator,
    SimulatedPriceModel,
    SimulatedPriceNoiseAdder,
)
from scripts.shared import Logger


def create_dependencies(args):
    # Create dependencies for SimulatedPriceModel
    if args.price_model == "SimulatedPriceModel":
        envelope_generator = SimulatedPriceEnvelopeGenerator()
        noise_adder = SimulatedPriceNoiseAdder()
        price_model = SimulatedPriceModel(
            envelope_generator=envelope_generator, noise_adder=noise_adder
        )

    elif args.price_model == "HistoricalPriceModel":
        data_provider = CSVDataProvider(args.csv_path)
        price_model = HistoricalAveragePriceModel(data_provider=data_provider)

    # Convert dates from strings to date objects
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()

    # Create dependencies for BatteryOptimizationScheduler
    battery = Battery(
        capacity_mwh=args.battery_capacity,
        charge_efficiency=args.charge_efficiency,
        discharge_efficiency=args.discharge_efficiency,
    )
    model_builder = PyomoOptimizationModelBuilder()
    solver = GLPKOptimizationSolver(args.log_level)
    model_extractor = PyomoModelExtractor()
    scheduler = BatteryOptimizationScheduler(
        battery=battery,
        model_builder=model_builder,
        solver=solver,
        model_extractor=model_extractor,
    )

    # Create dependencies for EnergyMarketSimulator
    pnl_calculator = PnLCalculator(battery=battery)

    return start_date, end_date, battery, price_model, pnl_calculator, scheduler


def create_app(args=None):
    # Parse command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--battery_capacity", type=float, default=1.0)
    parser.add_argument("--charge_efficiency", type=float, default=0.9)
    parser.add_argument("--discharge_efficiency", type=float, default=0.9)
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
    create_app()
