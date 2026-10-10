"""Merit-order dispatch: each period independently, cheapest available plant first."""

from __future__ import annotations

import numpy as np
import pandas as pd

from openenergy.system.model import SystemResult, SystemSpec, result_frames

_TOLERANCE_MW = 1e-6


def merit_order(spec: SystemSpec) -> SystemResult:
    """Exact least-cost dispatch for a system without storage.

    Must-run units run at their profile. The rest are stacked by marginal cost; the price
    is the cost of the last unit needed, or the value of lost load when capacity runs out.
    """
    gens = spec.generators
    capacity = np.column_stack([g.capacity_mw.to_numpy(dtype=np.float64) for g in gens])
    cost = np.column_stack([g.marginal_cost.to_numpy(dtype=np.float64) for g in gens])
    must_run = np.array([g.must_run for g in gens])

    dispatch = np.where(must_run, capacity, 0.0)
    residual = spec.demand.to_numpy(dtype=np.float64) - dispatch.sum(axis=1)

    flexible = np.where(must_run | (capacity <= 0), 0.0, capacity)
    ranking = np.where(flexible > 0, cost, np.inf)
    order = np.argsort(ranking, axis=1, kind="stable")
    stacked = np.take_along_axis(flexible, order, axis=1)
    cumulative = np.cumsum(stacked, axis=1)
    taken = np.clip(residual[:, None] - (cumulative - stacked), 0.0, stacked)
    flexible_dispatch = np.zeros_like(capacity)
    np.put_along_axis(flexible_dispatch, order, taken, axis=1)
    dispatch = dispatch + flexible_dispatch

    total = cumulative[:, -1]
    shed = np.clip(residual - total, 0.0, None)
    marginal = np.argmax(cumulative >= residual[:, None] - _TOLERANCE_MW, axis=1)
    sorted_cost = np.take_along_axis(ranking, order, axis=1)
    price = np.take_along_axis(sorted_cost, marginal[:, None], axis=1)[:, 0]
    price = np.where(shed > _TOLERANCE_MW, spec.voll, price)
    price = np.where(np.isfinite(price), price, 0.0)

    index = spec.demand.index
    generation, curtailment, emissions = result_frames(spec, dispatch)
    unserved = pd.Series(shed, index=index)
    energy_cost = float((dispatch * cost).sum() + shed.sum() * spec.voll) * spec.step_hours
    return SystemResult(
        price=pd.Series(price, index=index),
        generation=generation,
        storage=pd.DataFrame(index=index),
        unserved=unserved,
        curtailment=curtailment,
        emissions_t=emissions,
        cost=energy_cost,
        backend="merit",
        technologies={g.name: g.technology for g in gens},
    )
