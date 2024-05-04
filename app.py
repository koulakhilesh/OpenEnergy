from datetime import date
from scripts.battery import Battery
from scripts.scheduler import (
    BatteryOptimizationScheduler,
    PyomoOptimizationModelBuilder,
    GLPKOptimizationSolver,
    PyomoModelExtractor,
)
from scripts.prices import (
    SimulatedPriceModel,
    SimulatedPriceEnvelopeGenerator,
    SimulatedPriceNoiseAdder,
)
from scripts.energy_market_simulator import PnLCalculator, EnergyMarketSimulator


def main():
    # Create dependencies for SimulatedPriceModel
    envelope_generator = SimulatedPriceEnvelopeGenerator()
    noise_adder = SimulatedPriceNoiseAdder()
    simulated_model = SimulatedPriceModel(
        envelope_generator=envelope_generator, noise_adder=noise_adder
    )

    # Create dependencies for BatteryOptimizationScheduler
    battery = Battery(capacity_mwh=1.0, charge_efficiency=0.9, discharge_efficiency=0.9)
    model_builder = PyomoOptimizationModelBuilder()
    solver = GLPKOptimizationSolver()
    model_extractor = PyomoModelExtractor()
    scheduler = BatteryOptimizationScheduler(
        battery=battery,
        model_builder=model_builder,
        solver=solver,
        model_extractor=model_extractor,
    )

    # Create dependencies for EnergyMarketSimulator
    pnl_calculator = PnLCalculator(battery=battery)

    # Create an instance of EnergyMarketSimulator with SimulatedPriceModel
    simulator = EnergyMarketSimulator(
        start_date=date(2022, 1, 1),
        end_date=date(2022, 12, 31),
        battery=battery,
        price_model=simulated_model,
        pnl_calculator=pnl_calculator,
        scheduler=scheduler,
    )

    # Run the simulation
    results = simulator.simulate()
    print(f"Simulation results with SimulatedPriceModel: \n{results}")


if __name__ == "__main__":
    main()
