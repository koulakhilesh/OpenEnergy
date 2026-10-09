# Concepts

## Time and units

Prices are a series on a regular UTC grid; each timestamp labels the start of its interval
of length $\Delta t$ hours. Power is in MW, energy in MWh and prices in currency per MWh.
Days are UTC days.

## Battery physics

A battery has a power rating $P$ (MW), a rated energy $E_{rated}$ (MWh), charge and
discharge efficiencies $\eta_c, \eta_d$, and a state-of-charge window
$[SOC_{min}, SOC_{max}]$ expressed as fractions of usable energy.

For charge $c_t$ and discharge $d_t$ (MW) in interval $t$, stored energy evolves as

$$E_{t+1} = E_t + \eta_c\, c_t\, \Delta t - \frac{d_t\, \Delta t}{\eta_d}$$

Each interval adds its own throughput to the equivalent full cycle count:

$$N \mathrel{+}= \frac{(c_t + d_t)\,\Delta t}{2 E_{rated}}$$

State of health is computed from lifetime totals, so it never compounds:

$$SOH = 1 - k_{cycle}\, N - k_{calendar}\, \text{age in years}$$

Usable energy is $E_{rated} \cdot SOH$. Ageing is applied at the end of every UTC day,
including days that are not simulated.

## Dispatch

Each day is planned by maximising forecast revenue less an optional degradation cost
$\kappa$ per MWh of throughput:

$$\max \sum_t \hat p_t\, (d_t - c_t)\, \Delta t - \kappa \sum_t (c_t + d_t)\, \Delta t$$

subject to the energy balance above for $t = 0 \dots T-1$ with $E_0$ fixed, and:

- $0 \le c_t \le P\, u_t$ and $0 \le d_t \le P\,(1 - u_t)$ with $u_t \in \{0, 1\}$, so the
  battery never charges and discharges at once (an LP would, to burn energy at negative
  prices);
- $SOC_{min}\, E_{usable} \le E_t \le SOC_{max}\, E_{usable}$;
- $E_T \ge E_{target}$, by default the energy the day started with;
- optionally, $\sum_t (c_t + d_t)\, \Delta t \le 2 N_{max}\, E_{usable}$.

The model is solved with [HiGHS](https://highs.dev); a day takes a few milliseconds.

## Backtest timing

For each day $D$:

1. The forecaster receives prices strictly before the decision time, `lead_hours` before
   the start of $D$ (default 12, i.e. noon on $D-1$).
2. The optimiser plans $D$ on the forecast.
3. The plan is applied through the battery physics and valued at actual prices.
4. The battery state carries into $D+1$.

Days with missing prices, or for which the forecaster has no usable history, are skipped
and listed with the reason. Scenarios that are not perfect foresight also run a
perfect-foresight benchmark on the same days.

## Forecasters

| Method | Description |
|--------|-------------|
| `perfect_foresight` | The actual prices; the upper bound. |
| `naive_last_week` | The same interval seven days earlier, falling back to fourteen. |
| `noisy_foresight` | Actual prices plus seeded Gaussian error of a chosen spread. |
| `gradient_boosting` | Gradient-boosted trees on calendar features and 1/2/7/14-day lags (needs the `forecast` extra). |

The gradient-boosting model masks any lag at or after the decision time in exactly the
same way during training and forecasting, and is trained only on a window that ends
before the backtest starts.

## Metrics

| Metric | Definition |
|--------|------------|
| Revenue | $\sum_t p_t\,(d_t - c_t)\,\Delta t$ at actual prices |
| Revenue per MW-year | Revenue $/\,P \times 365\,/$ days simulated |
| Captured spread | Revenue per MWh discharged |
| Equivalent cycles | Lifetime $N$ at the end of the run |
| Forecast MAE / RMSE | Error of the forecast against actual prices |
| Capture ratio | Revenue / perfect-foresight revenue on common days |
