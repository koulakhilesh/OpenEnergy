# Documentation for model.py

This Python module, `model.py`, contains classes and methods for building and solving an optimization model for a battery's charging and discharging schedule using Pyomo and GLPK.

## Classes

### 1. PyomoOptimizationModelBuilder

This class builds and defines an optimization model for a battery's charging and discharging schedule.

#### Method: build_model

This method builds the optimization model. It takes as input the number of time intervals, the prices for each time interval, the battery, the length of each time interval in hours, and the maximum number of cycles. It defines the time intervals, variables, objective function, and constraints of the model.

#### Method: define_time_intervals

This method defines the time intervals for the model. It creates a range set from 0 to the number of intervals minus 1.

#### Method: define_variables

This method defines the variables for the model. It defines the charge, discharge, state of charge (SOC), and energy cycled variables for each time interval. The charge and discharge variables are bounded by the battery's capacity, and the SOC variable is bounded between 0.05 and 0.95.

#### Method: _objective_rule

This method defines the rule for the objective function. The objective is to maximize the total profit from discharging and charging the battery over all time intervals. The profit for each time interval is calculated as the revenue from discharging the battery minus the cost of charging the battery, adjusted for the battery's charge and discharge efficiencies and the length of the time interval.

The objective function is defined as follows:

$$\text{{objective}} = \sum_{t \in T} \left( \text{{discharge\_vars}}[t] \times \text{{prices}}[t] \times \text{{discharge\_efficiency}} / \text{{timestep\_hours}} \right) - \left( \text{{charge\_vars}}[t] \times \text{{prices}}[t] / (\text{{charge\_efficiency}} \times \text{{timestep\_hours}}) \right)$$

#### Method: define_objective_function

This method defines the objective function for the model using the objective rule.

#### Method: _charging_discharging_rule

This method defines the rule for the charging and discharging constraint. The sum of the charge and discharge variables for each time interval must be less than or equal to the battery's capacity.

The charging and discharging constraint is defined as follows:

$$\text{{charge\_vars}}[t] + \text{{discharge\_vars}}[t] \leq \text{{capacity\_mwh}}$$

#### Method: _soc_update_rule

This method defines the rule for the SOC update constraint. The SOC for each time interval is equal to the SOC for the previous time interval plus the charge variable for the previous time interval, adjusted for the battery's charge efficiency and capacity, minus the discharge variable for the previous time interval, adjusted for the battery's discharge efficiency and capacity.

The SOC update constraint is defined as follows:

$$\text{{soc\_vars}}[t] = \text{{soc\_vars}}[t - 1] + \left( \text{{charge\_vars}}[t - 1] \times \text{{charge\_efficiency}} / \text{{capacity\_mwh}} \right) - \left( \text{{discharge\_vars}}[t - 1] / (\text{{discharge\_efficiency}} \times \text{{capacity\_mwh}}) \right)$$

#### Method: _energy_cycled_update_rule

This method defines the rule for the energy cycled update constraint. The energy cycled for each time interval is equal to the energy cycled for the previous time interval plus the charge variable for the previous time interval, adjusted for the battery's charge efficiency, plus the discharge variable for the previous time interval, adjusted for the battery's discharge efficiency.

The energy cycled update constraint is defined as follows:

$$\text{{energy\_cycled\_vars}}[t] = \text{{energy\_cycled\_vars}}[t - 1] + \text{{charge\_vars}}[t - 1] \times \text{{charge\_efficiency}} + \text{{discharge\_vars}}[t - 1] / \text{{discharge\_efficiency}}$$

#### Method: define_constraints

This method defines the constraints for the model. It defines the initial SOC constraint, the charging and discharging constraint, the SOC update constraint, the energy cycled update constraint, and the maximum cycles constraint.

The maximum cycles constraint is defined as follows:

$$\text{{energy\_cycled\_vars}}[\text{{num\_intervals}} - 1] \leq \text{{max\_cycles}} \times \text{{capacity\_mwh}} \times 2$$

### 2. GLPKOptimizationSolver

This class solves the optimization model using the GLPK solver.

#### Method: solve

This method solves the optimization model. It creates a GLPK solver, solves the model, checks and logs the solver's termination condition and status, and returns the result.
