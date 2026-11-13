# Polymarket NVIDIA CEO forecaster

Forecasts the Yes price of every trading market of Polymarket's event
"Next CEO of NVIDIA?" at every minute of the 4 hours after a checkpoint,
as five quantiles (0.05, 0.25, 0.5, 0.75, 0.95). Scored by mean pinball
loss; lower is better.

## Method

Per market, from its last price `x`:

- `sigma` = RMS of the 1-minute price changes over the last 120 minutes
  (floored at 0.0005, capped at 0.01). A short window tracks the current
  volatility regime; longer windows are polluted by old jumps.
- `spread(h) = sigma * h**0.3` for minute `h = 1..240`. Prices are jumpy
  and bounded in [0, 1], so the spread grows slower than a random walk's
  `sqrt(h)`.
- `q_tau(h) = x + z_tau * spread(h)`, with `z` the standard normal
  quantiles and the two outer ones widened 1.6x: the jump process has much
  heavier tails than a Gaussian.
- No drift term: 1-minute moves are slightly mean-reverting, so the centre
  stays at the last price.

## Practice score

Local scorer (validated to reproduce the house baseline exactly):
**0.267107** vs the house baseline's **0.363589**, beating it on every one
of the six practice cases (p00-p05).

## Run

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Python 3.13, stdlib only, no network, deterministic.
