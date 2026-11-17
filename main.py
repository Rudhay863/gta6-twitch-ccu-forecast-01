"""Forecast GTA VI's launch-day Twitch viewers, hour by hour (quantiles).

Model: launch-day shape learned from past big launches.
-------------------------------------------------------
Every comparable launch contributes its launch-day hourly curve as log-ratios
to its own hour-1 print: r_h = ln(viewers(h) / viewers(1)) for h = 2..24.
For the target case, each hour's forecast quantiles are the weighted
quantiles of those log-ratios across the comparable pool, scaled by the
target's own hour-1 print: q_tau(h) = p1 * exp(Q_tau(r_h)).

Two choices make this work, both validated on the practice cases and by
leave-one-out over the comparables (see BUILD-NOTES.md):

1. Pool filter. Only launches whose shape can transfer to a rolling
   midnight-local console launch with no early access: a complete 24-hour
   launch day, an hour-1 print that is already a real audience (at least
   2% of the day's peak, so the game had actually unlocked by hour 1),
   and an unlock that is neither a single simultaneous global unlock nor
   an early-access launch. Simultaneous launches (tiny hour-1 trickle,
   then a vertical spike at their unlock hour) and early-access launches
   (hour 1 already saturated) have shapes that do not transfer.
   The target's own pre-release category history is not a launch and is
   excluded the same way (it has no launch day).

2. Similarity weights. The day's growth depends strongly on how big hour 1
   already is (across the pool, corr(log hour-1, peak log-ratio) = -0.77:
   a small hour-1 base grows far more over the day than a large one).
   Each comparable is weighted by a Gaussian kernel on log hour-1
   (bandwidth 1.0 in natural-log units), so launches that started at a
   similar scale to the target dominate the quantiles.

Pinball loss on the log scale rewards honest quantiles, so the spread comes
from the weighted cross-launch distribution itself, not from a guessed
volatility: no Normal assumption, no hand-set sigma.

Determinism: pure standard library, no randomness, no wall clock, no
environment input beyond the case file and the two MAKEFUN_* directories.
Iteration order is fixed (comparables sorted by name), so two runs write
identical bytes.

Usage (as the grader runs it):
    python3 /bot/main.py            (reads /input, writes /output)
    MAKEFUN_INPUT_DIR=in MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import json
import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# The grader's -P leaves /bot off sys.path: put it back first, so a helper
# module shipped beside this file would import. (This entry is one file.)
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]

# A launch only joins the pool when hour 1 already held at least this share
# of the day's peak: below it the game had not really unlocked by hour 1.
MIN_HOUR1_SHARE = 0.02
# Gaussian kernel bandwidth on log hour-1 viewers.
LOG_H1_BANDWIDTH = 1.0
# Persistence fallback (house baseline shape) when the pool is too small.
FALLBACK_SIGMA = 0.15
FALLBACK_Z = [-1.645, -0.674, 0.0, 0.674, 1.645]


def _parse_time(text):
    """ISO 8601 with a trailing Z, to an aware datetime."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _launch_day_hours(comp):
    """{hour: viewers} for the 24 hours from the comparable's day_start.

    Returns None when the day is incomplete or hour 1 is not positive:
    such a comparable carries no launch-day shape.
    """
    start = _parse_time(comp["day_start"])
    hours = {}
    for point in comp.get("hourly") or []:
        when = _parse_time(point["from"])
        slot = int((when - start).total_seconds() // 3600) + 1
        if 1 <= slot <= 24 and point.get("viewers") is not None:
            hours[slot] = point["viewers"]
    if len(hours) < 24:
        return None
    if hours[1] <= 0:
        return None
    return hours


def _unlock_kind(comp):
    """'simultaneous', 'early-access', or None, from the unlock note."""
    text = (comp.get("unlock") or "").lower()
    if "early access" in text or "early-access" in text:
        return "early-access"
    if "simultaneous" in text or "single global" in text:
        return "simultaneous"
    return None


def _pool(case):
    """Comparable launches whose launch-day shape can transfer to the target."""
    pool = []
    for comp in sorted(case.get("comparables") or [], key=lambda c: c.get("name", "")):
        hours = _launch_day_hours(comp)
        if hours is None:
            continue
        if _unlock_kind(comp) is not None:
            continue
        peak = max(hours.values())
        if hours[1] < MIN_HOUR1_SHARE * peak:
            continue
        pool.append((comp.get("name", ""), hours))
    return pool


def _weighted_quantile(pairs, level):
    """Smallest value whose cumulative weight reaches `level` of the total.

    pairs is a list of (value, weight); weights need not sum to 1.
    """
    total = sum(w for _, w in pairs)
    if total <= 0:
        return pairs[0][0] if pairs else 0.0
    running = 0.0
    for value, weight in sorted(pairs):
        running += weight
        if running >= level * total:
            return value
    return sorted(pairs)[-1][0]


def _round2(value):
    """Round to 2 decimals, half up (whole numbers come back as ints)."""
    scaled = value * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    rounded = whole / 100
    return int(rounded) if rounded.is_integer() else rounded


def _forecast_case(case):
    known = [row for row in case.get("known") or [] if row.get("hour") == 1]
    first_print = max(1.0, float(known[0]["viewers"])) if known else 1.0
    pool = _pool(case)
    rows = []
    if len(pool) < 3:
        # Too little shape to learn from: fall back to persistence.
        for row in case.get("forecast") or []:
            hour = row["hour"]
            qs = [
                _round2(first_print * math.exp(z * FALLBACK_SIGMA * math.sqrt(hour - 1)))
                for z in FALLBACK_Z
            ]
            rows.append({"hour": hour, "q": qs})
        return {"hours": rows}

    log_first = math.log(first_print)
    for row in case.get("forecast") or []:
        hour = row["hour"]
        quantiles = []
        for level in LEVELS:
            pairs = []
            for _, hours in pool:
                weight = math.exp(
                    -0.5 * ((math.log(hours[1]) - log_first) / LOG_H1_BANDWIDTH) ** 2
                )
                pairs.append((math.log(hours[hour] / hours[1]), weight))
            quantiles.append(_weighted_quantile(pairs, level))
        # Quantiles of one distribution at rising levels cannot fall, but
        # enforce it explicitly so the output is valid by construction.
        # The floor starts below any real log-ratio: viewers dip below the
        # hour-1 print in the small hours, so a 0.0 floor would wrongly
        # clamp the low quantiles up to the hour-1 print itself.
        fixed = []
        floor = float("-inf")
        for value in quantiles:
            floor = max(floor, value)
            fixed.append(floor)
        qs = [
            _round2(min(1e9, max(1.0, first_print * math.exp(value))))
            for value in fixed
        ]
        # Rounding to 2 decimals is monotone, so the row stays ordered.
        rows.append({"hour": hour, "q": qs})
    return {"hours": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = _forecast_case(case)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
