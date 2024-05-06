# Battery Optimization Scheduler Documentation

This Python code defines a battery optimization scheduler using the Pyomo optimization library. The scheduler is designed to optimize the charging and discharging schedule of a battery based on given electricity prices.

## Mathematical Model

The optimization problem is formulated as a linear programming problem. The objective is to maximize the total profit from charging and discharging the battery. The profit is calculated as the difference between the revenue from discharging the battery and the cost of charging it.

The mathematical formulation of the objective function is:

$$\max \sum_{t \in T} \left( \frac{{\text{{discharge\_vars}}[t] \times \text{{prices}}[t] \times \text{{discharge\_efficiency}}}}{{\text{{timestep\_hours}}}} - \frac{{\text{{charge\_vars}}[t] \times \text{{prices}}[t]}}{{\text{{charge\_efficiency}} \times \text{{timestep\_hours}}}} \right)
$$

where:
- `T` is the set of time intervals.
- `discharge_vars[t]` is the amount of energy discharged at time `t`.
- `charge_vars[t]` is the amount of energy charged at time `t`.
- `prices[t]` is the electricity price at time `t`.
- `discharge_efficiency` is the efficiency of discharging the battery.
- `charge_efficiency` is the efficiency of charging the battery.
- `timestep_hours` is the length of each time interval in hours.

The model also includes several constraints:

1. The sum of the charge and discharge variables at each time interval must not exceed the battery capacity:

$$\text{{charge\_vars}}[t] + \text{{discharge\_vars}}[t] \leq \text{{battery\_capacity}}
$$

2. The state of charge (SOC) at each time interval is updated based on the charge and discharge variables:

$$\text{{soc\_vars}}[t] = \text{{soc\_vars}}[t - 1] + \frac{{\text{{charge\_vars}}[t - 1] \times \text{{charge\_efficiency}}}}{{\text{{battery\_capacity}}}} - \frac{{\text{{discharge\_vars}}[t - 1]}}{{\text{{discharge\_efficiency}} \times \text{{battery\_capacity}}}}
$$

3. The total energy cycled through the battery must not exceed a given maximum:

$$\text{{energy\_cycled\_vars}}[\text{{num\_intervals}} - 1] \leq \text{{max\_cycles}} \times \text{{battery\_capacity}} \times 2
$$

## Classes

The code defines several classes and interfaces to build, solve, and extract the results from the optimization model. The main classes are:

- `IModelBuilder`: Interface for building the optimization model.
- `IModelSolver`: Interface for solving the optimization model.
- `IModelExtractor`: Interface for extracting the schedule from the solved model.
- `PyomoOptimizationModelBuilder`: Class that implements `IModelBuilder` using Pyomo.
- `GLPKOptimizationSolver`: Class that implements `IModelSolver` using the GLPK solver.
- `PyomoModelExtractor`: Class that implements `IModelExtractor` using Pyomo.
- `BatteryOptimizationScheduler`: Class that uses the above classes to create the optimal battery schedule.