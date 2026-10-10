"""Unit commitment: thermal units with start-up costs and minimum stable output.

Each thermal tranche is a cluster of identical units; the number online is an integer.
Days are solved in order with a lookahead, so plans see only the next day ahead.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

import highspy
import numpy as np
import numpy.typing as npt
import pandas as pd

from openenergy.data.fleet import SystemInputs
from openenergy.errors import ConfigError, DispatchError
from openenergy.system.model import SystemResult, SystemSpec, result_frames

FloatArray = npt.NDArray[np.float64]
_INF = highspy.kHighsInf


@dataclass(frozen=True)
class UnitParameters:
    """One unit of a technology: size (MW), minimum stable output (share of size), and
    start-up cost (GBP per MW of unit size per start)."""

    unit_mw: float
    min_stable: float
    start_cost_per_mw: float

    def __post_init__(self) -> None:
        if not (math.isfinite(self.unit_mw) and self.unit_mw > 0):
            raise ConfigError(f"unit_mw must be positive, got {self.unit_mw}")
        if not 0 <= self.min_stable < 1:
            raise ConfigError(f"min_stable must be in [0, 1), got {self.min_stable}")
        if not (math.isfinite(self.start_cost_per_mw) and self.start_cost_per_mw >= 0):
            raise ConfigError(
                f"start_cost_per_mw must be non-negative, got {self.start_cost_per_mw}"
            )


@dataclass(frozen=True)
class Commitment:
    """Unit parameters by technology; technologies not listed dispatch continuously."""

    units: Mapping[str, UnitParameters]
    lookahead_hours: float = 24.0
    mip_rel_gap: float = 1e-4

    def __post_init__(self) -> None:
        if not self.units:
            raise ConfigError("commitment needs parameters for at least one technology")
        if not (math.isfinite(self.lookahead_hours) and self.lookahead_hours >= 0):
            raise ConfigError(f"lookahead_hours must be non-negative, got {self.lookahead_hours}")

    @classmethod
    def from_inputs(cls, inputs: SystemInputs, lookahead_hours: float = 24.0) -> Commitment:
        """Unit parameters from the bundled ``unit_parameters.csv``."""
        table = inputs.unit_parameters()
        units = {
            str(name): UnitParameters(
                float(row["unit_mw"]), float(row["min_stable"]), float(row["start_cost_gbp_per_mw"])
            )
            for name, row in table.iterrows()
        }
        return cls(units, lookahead_hours)


def commit(spec: SystemSpec, commitment: Commitment) -> SystemResult:
    """Least-cost commitment and dispatch, one day at a time with a lookahead.

    ``price`` is the marginal price with commitment fixed. ``start_price`` adds start costs:
    each running unit's marginal cost plus its start cost spread over the energy of that
    run; the price in a period is the highest such cost among units online, or the
    marginal price if higher.
    """
    model = _Model(spec, commitment)
    per_day = int(pd.Timedelta(days=1) / spec.step)
    look = round(commitment.lookahead_hours / spec.step_hours)
    total = len(spec.demand)
    for start in range(0, total, per_day):
        model.solve_window(start, min(start + per_day, total), min(start + per_day + look, total))
    return model.result()


class _Model:
    def __init__(self, spec: SystemSpec, commitment: Commitment) -> None:
        self.spec = spec
        self.dt = spec.step_hours
        gens = spec.generators
        self.capacity = np.column_stack([g.capacity_mw.to_numpy(np.float64) for g in gens])
        self.cost = np.column_stack([g.marginal_cost.to_numpy(np.float64) for g in gens])
        self.must = [i for i, g in enumerate(gens) if g.must_run]
        self.units = {
            i: commitment.units[g.technology]
            for i, g in enumerate(gens)
            if not g.must_run and g.technology in commitment.units
        }
        self.flex = [i for i, g in enumerate(gens) if not g.must_run and i not in self.units]
        self.gap = commitment.mip_rel_gap
        total = len(spec.demand)
        self.residual = spec.demand.to_numpy(np.float64) - self.capacity[:, self.must].sum(axis=1)
        self.dispatch: FloatArray = np.zeros(self.capacity.shape, dtype=np.float64)
        self.dispatch[:, self.must] = self.capacity[:, self.must]
        self.online = np.zeros((total, len(gens)))
        self.starts = np.zeros((total, len(gens)))
        self.shed = np.zeros(total)
        self.price = np.zeros(total)
        self.charge = np.zeros((total, len(spec.storage)))
        self.discharge = np.zeros((total, len(spec.storage)))
        self.energy = np.array([0.5 * s.power_mw * s.hours for s in spec.storage])
        self.previous: dict[int, float] | None = None
        self.objective = 0.0

    def solve_window(self, start: int, keep: int, stop: int) -> None:
        lp, layout = self._build(start, stop)
        solution = _run(lp, self.gap)
        integers = [layout.u(i, t) for i in self.units for t in range(stop - start)]
        # HighsLp array properties return copies, so modify and assign back whole arrays.
        lower, upper = np.array(lp.col_lower_), np.array(lp.col_upper_)
        lower[integers] = upper[integers] = np.round(solution[integers])
        lp.col_lower_, lp.col_upper_ = lower, upper
        lp.integrality_ = []
        fixed = highspy.Highs()  # type: ignore[no-untyped-call]
        fixed.setOptionValue("output_flag", False)
        fixed.passModel(lp)
        fixed.run()
        if fixed.getModelStatus() != highspy.HighsModelStatus.kOptimal:
            raise DispatchError("pricing LP with fixed commitment did not solve")
        values = np.asarray(fixed.getSolution().col_value, dtype=np.float64)
        duals = np.asarray(fixed.getSolution().row_dual, dtype=np.float64)
        span = keep - start
        for t in range(span):
            row = start + t
            self.price[row] = duals[layout.balance_row(t)] / self.dt
            self.shed[row] = values[layout.shed(t)]
            for i in self.flex:
                self.dispatch[row, i] = values[layout.q(i, t)]
            for i in self.units:
                self.dispatch[row, i] = values[layout.p(i, t)]
                self.online[row, i] = values[layout.u(i, t)]
                self.starts[row, i] = values[layout.s(i, t)]
            for k in range(len(self.spec.storage)):
                self.charge[row, k] = values[layout.charge(k, t)]
                self.discharge[row, k] = values[layout.discharge(k, t)]
        self.objective += float(sum(values[c] * lp.col_cost_[c] for c in layout.kept_columns(span)))
        self.previous = {i: self.online[keep - 1, i] for i in self.units}
        self.energy = np.array(
            [values[layout.energy(k, span - 1)] for k in range(len(self.spec.storage))]
        )

    def _build(self, start: int, stop: int) -> tuple[highspy.HighsLp, _Layout]:
        n = stop - start
        layout = _Layout(n, list(self.flex), list(self.units), len(self.spec.storage))
        lower = np.zeros(layout.size)
        upper = np.full(layout.size, _INF)
        cost = np.zeros(layout.size)
        rows: list[tuple[list[int], list[float], float, float]] = []
        dt = self.dt
        for t in range(n):
            row = start + t
            balance: tuple[list[int], list[float]] = ([], [])
            for i in self.flex:
                col = layout.q(i, t)
                upper[col] = self.capacity[row, i]
                cost[col] = self.cost[row, i] * dt
                balance[0].append(col)
                balance[1].append(1.0)
            for i, unit in self.units.items():
                p, u, s = layout.p(i, t), layout.u(i, t), layout.s(i, t)
                available = self.capacity[row, i]
                upper[p] = available
                upper[u] = math.ceil(available / unit.unit_mw - 1e-9)
                cost[p] = self.cost[row, i] * dt
                cost[s] = unit.start_cost_per_mw * unit.unit_mw
                rows.append(([p, u], [1.0, -unit.unit_mw], -_INF, 0.0))
                rows.append(([p, u], [1.0, -unit.min_stable * unit.unit_mw], 0.0, _INF))
                if t == 0:
                    if self.previous is not None:
                        rows.append(([s, u], [1.0, -1.0], -self.previous[i], _INF))
                else:
                    rows.append(([s, u, layout.u(i, t - 1)], [1.0, -1.0, 1.0], 0.0, _INF))
                balance[0].append(p)
                balance[1].append(1.0)
            for k, store in enumerate(self.spec.storage):
                one_way = math.sqrt(store.efficiency)
                c, d, e = layout.charge(k, t), layout.discharge(k, t), layout.energy(k, t)
                upper[c] = upper[d] = store.power_mw
                upper[e] = store.power_mw * store.hours
                if t == 0:
                    rows.append(
                        (
                            [e, c, d],
                            [1.0, -one_way * dt, dt / one_way],
                            self.energy[k],
                            self.energy[k],
                        )
                    )
                else:
                    prior = layout.energy(k, t - 1)
                    rows.append(
                        ([e, prior, c, d], [1.0, -1.0, -one_way * dt, dt / one_way], 0.0, 0.0)
                    )
                balance[0].extend([d, c])
                balance[1].extend([1.0, -1.0])
            shed = layout.shed(t)
            cost[shed] = self.spec.voll * dt
            balance[0].append(shed)
            balance[1].append(1.0)
            layout.balance_rows.append(len(rows))
            rows.append((balance[0], balance[1], self.residual[row], self.residual[row]))
        lp = highspy.HighsLp()
        lp.num_col_ = layout.size
        lp.num_row_ = len(rows)
        lp.sense_ = highspy.ObjSense.kMinimize
        lp.col_cost_ = cost
        lp.col_lower_ = lower
        lp.col_upper_ = upper
        lp.row_lower_ = np.array([r[2] for r in rows], dtype=np.float64)
        lp.row_upper_ = np.array([r[3] for r in rows], dtype=np.float64)
        lp.a_matrix_.format_ = highspy.MatrixFormat.kRowwise
        lp.a_matrix_.num_col_ = layout.size
        lp.a_matrix_.num_row_ = len(rows)
        lp.a_matrix_.start_ = np.cumsum([0] + [len(r[0]) for r in rows], dtype=np.int32)
        lp.a_matrix_.index_ = np.array([c for r in rows for c in r[0]], dtype=np.int32)
        lp.a_matrix_.value_ = np.array([v for r in rows for v in r[1]], dtype=np.float64)
        integer = set(layout.u(i, t) for i in self.units for t in range(n))
        lp.integrality_ = [
            highspy.HighsVarType.kInteger if c in integer else highspy.HighsVarType.kContinuous
            for c in range(layout.size)
        ]
        return lp, layout

    def result(self) -> SystemResult:
        spec = self.spec
        index = spec.demand.index
        generation, curtailment, emissions = result_frames(spec, self.dispatch)
        names = [g.name for g in spec.generators]
        committed = [names[i] for i in self.units]
        online = pd.DataFrame(self.online, index=index, columns=names)[committed]
        starts = pd.DataFrame(self.starts, index=index, columns=names)[committed]
        storage = pd.DataFrame(
            self.discharge - self.charge, index=index, columns=[s.name for s in spec.storage]
        )
        price = np.where(np.abs(self.price) < 1e-9, 0.0, self.price)
        return SystemResult(
            price=pd.Series(price, index=index),
            generation=generation,
            storage=storage,
            unserved=pd.Series(self.shed, index=index),
            curtailment=curtailment,
            emissions_t=emissions,
            cost=self.objective,
            backend="commitment",
            technologies={g.name: g.technology for g in spec.generators},
            start_price=pd.Series(self._start_price(price), index=index),
            units_online=online,
            starts=starts,
        )

    def _start_price(self, price: FloatArray) -> FloatArray:
        best = price.copy()
        for i, unit in self.units.items():
            online = np.rint(self.online[:, i]).astype(int)
            share = np.divide(
                self.dispatch[:, i], online, out=np.zeros_like(price), where=online > 0
            )
            for level in range(1, int(online.max(initial=0)) + 1):
                on = online >= level
                edges = np.flatnonzero(np.diff(np.concatenate(([0], on.astype(int), [0]))))
                for first, end in zip(edges[::2], edges[1::2], strict=True):
                    if first == 0:
                        continue
                    energy = share[first:end].sum() * self.dt
                    if energy <= 0:
                        continue
                    uplift = unit.start_cost_per_mw * unit.unit_mw / energy
                    run_cost = self.cost[first:end, i] + uplift
                    best[first:end] = np.maximum(best[first:end], run_cost)
        return best


class _Layout:
    """Column and row positions for one window."""

    def __init__(self, periods: int, flex: list[int], units: list[int], storage: int) -> None:
        self.n = periods
        self.flex = {g: k for k, g in enumerate(flex)}
        self.units = {g: k for k, g in enumerate(units)}
        self.storage = storage
        self.per_period = len(flex) + 3 * len(units) + 3 * storage + 1
        self.size = self.per_period * periods
        self.balance_rows: list[int] = []

    def _base(self, t: int) -> int:
        return t * self.per_period

    def q(self, g: int, t: int) -> int:
        return self._base(t) + self.flex[g]

    def _unit(self, g: int, t: int, offset: int) -> int:
        return self._base(t) + len(self.flex) + 3 * self.units[g] + offset

    def p(self, g: int, t: int) -> int:
        return self._unit(g, t, 0)

    def u(self, g: int, t: int) -> int:
        return self._unit(g, t, 1)

    def s(self, g: int, t: int) -> int:
        return self._unit(g, t, 2)

    def _store(self, k: int, t: int, offset: int) -> int:
        return self._base(t) + len(self.flex) + 3 * len(self.units) + 3 * k + offset

    def charge(self, k: int, t: int) -> int:
        return self._store(k, t, 0)

    def discharge(self, k: int, t: int) -> int:
        return self._store(k, t, 1)

    def energy(self, k: int, t: int) -> int:
        return self._store(k, t, 2)

    def shed(self, t: int) -> int:
        return self._base(t) + self.per_period - 1

    def balance_row(self, t: int) -> int:
        return self.balance_rows[t]

    def kept_columns(self, span: int) -> range:
        return range(0, span * self.per_period)


def _run(lp: highspy.HighsLp, gap: float) -> FloatArray:
    solver = highspy.Highs()  # type: ignore[no-untyped-call]
    solver.setOptionValue("output_flag", False)
    solver.setOptionValue("mip_rel_gap", gap)
    solver.passModel(lp)
    solver.run()
    status = solver.getModelStatus()
    if status != highspy.HighsModelStatus.kOptimal:
        raise DispatchError(f"unit commitment did not solve: {solver.modelStatusToString(status)}")
    return np.asarray(solver.getSolution().col_value, dtype=np.float64)
