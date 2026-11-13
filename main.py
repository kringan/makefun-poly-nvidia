#!/usr/bin/env python3
# Polymarket "Next CEO of NVIDIA?" minute-by-minute forecaster.
#
# Task: for each market of the event, forecast the Yes price at every minute
# of the 240 minutes after a checkpoint, as five quantiles (0.05, 0.25, 0.5,
# 0.75, 0.95). Scored by mean pinball loss; lower is better.
#
# What the prices look like (from the practice cases p00-p05):
#   - A market's price is flat most minutes, then moves in a tick, and now
#     and then jumps hard (Colette Kress jumped 0.3535 -> 0.59 in one minute).
#   - Only ~12% of 1-minute steps move at all; the rest are exactly zero.
#   - Volatility clusters: a market that moved in the last 2 hours is far
#     more likely to move in the next 4 than one that sat still for a day.
#   - 1-minute moves are slightly mean-reverting (lag-1 autocorrelation
#     about -0.08), so the centre stays at the last price: no drift term.
#
# The forecast, per market, from its last price x:
#   sigma = RMS of the 1-minute price changes over the last 120 minutes,
#           floored at 0.0005 and capped at 0.01. A short window tracks the
#           current volatility regime; longer windows (24-72h) are polluted
#           by old jumps and score far worse.
#   spread(h) = sigma * h**0.3 for minute h = 1..240. Prices are jumpy and
#           bounded in [0, 1], so the spread grows slower than a random
#           walk's sqrt(h): exponent 0.3 beats 0.5 by a wide margin.
#   q_tau(h) = x + z_tau * spread(h), with z the standard normal quantiles
#           and the two outer ones widened x1.6: the jump process has much
#           heavier tails than a Gaussian, so the 5% / 95% quantiles need
#           extra room or every jump lands outside them.
#   Every quantile is clamped to [0, 1], rounded to 6 decimals, and each
#   row is forced non-decreasing.
#
# Practice score (local scorer, validated to reproduce the house baseline
# exactly): 0.267107 vs the house baseline's 0.363589, beating it on every
# one of the six practice cases. Median error is identical to the baseline
# (the centre is the same last price); the whole gain is the spread.
#
# Stdlib only, no network, deterministic: the same case always gives the
# same bytes. Reads $MAKEFUN_INPUT_DIR (else /input) and writes to
# $MAKEFUN_OUTPUT_DIR (else /output), one <id>.out per <id>.in. Output is
# capped at 1 MiB by the rules; 24 markets x 240 rows x 5 numbers fits
# easily at ~350 KB of compact JSON.
import json
import math
import os

INPUT_DIR = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

QUANTILES = [0.05, 0.25, 0.5, 0.75, 0.95]
# Standard normal quantiles at the five levels; the outer two are widened
# 1.6x because the price process jumps and has far heavier tails than a
# Gaussian (see the header: only ~12% of minutes move, then sometimes hard).
Z = [-1.644854 * 1.6, -0.674490, 0.0, 0.674490, 1.644854 * 1.6]
SIGMA_WINDOW = 120      # minutes of recent history the RMS is taken over
SIGMA_FLOOR = 0.0005    # quiet markets still get a small spread
SIGMA_CAP = 0.01        # a wild market's spread stays bounded
SPREAD_EXP = 0.3        # spread grows like h**0.3, slower than sqrt(h)


def price6(x):
    """Clamp to [0, 1] and round to 6 decimals (0, never -0)."""
    v = round(min(1.0, max(0.0, x)) * 1e6) / 1e6
    return v + 0.0


def market_sigma(prices):
    """RMS of the 1-minute price changes over the last SIGMA_WINDOW minutes."""
    diffs = [prices[i + 1] - prices[i] for i in range(len(prices) - 1)]
    w = diffs[-SIGMA_WINDOW:] if len(diffs) > SIGMA_WINDOW else diffs
    if not w:
        return SIGMA_FLOOR
    sig = math.sqrt(sum(d * d for d in w) / len(w))
    return min(SIGMA_CAP, max(SIGMA_FLOOR, sig))


def forecast_market(prices, horizon):
    """240 rows of five quantiles around the market's last price."""
    x = prices[-1]
    sigma = market_sigma(prices)
    rows = []
    for h in range(1, horizon + 1):
        s = sigma * (h ** SPREAD_EXP)
        row = [price6(x + z * s) for z in Z]
        for i in range(1, 5):
            if row[i] < row[i - 1]:
                row[i] = row[i - 1]
        rows.append(row)
    return rows


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    inputs = sorted(f for f in os.listdir(INPUT_DIR) if f.endswith(".in"))
    for fname in inputs:
        case_id = fname[: -len(".in")]
        with open(os.path.join(INPUT_DIR, fname), "r", encoding="utf-8") as f:
            case = json.load(f)
        if list(case.get("quantiles", [])) != QUANTILES:
            raise ValueError(f"{fname} asks for quantiles {case.get('quantiles')}")
        forecasts = []
        for m in case["markets"]:
            if not m["prices"]:
                raise ValueError(f"market {m['id']} has no prices")
            forecasts.append({"id": m["id"], "q": forecast_market(m["prices"], case["horizon_minutes"])})
        out = {"forecasts": forecasts}
        with open(os.path.join(OUTPUT_DIR, case_id + ".out"), "w", encoding="utf-8") as f:
            f.write(json.dumps(out) + "\n")


if __name__ == "__main__":
    main()
