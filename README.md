# GTA VI Twitch Viewers Forecaster

[![make.fun](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Rudhay863/gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Rudhay863/gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)

Entry for [Forecast GTA VI's launch-day Twitch viewers hour by hour](https://make.fun/bounty/gta6-twitch-ccu-forecast-01) on [make.fun](https://make.fun).

Referral: https://make.fun/r/xk7vph3j

## What it does

`main.py` (Python 3.13, standard library only) forecasts the Twitch concurrent-viewer count in the "Grand Theft Auto VI" category for each hour 2–24 of launch day (2026-11-19, UTC), as five quantiles (5%, 25%, 50%, 75%, 95%) per hour, from the hour-1 print and the launch-day shapes of past big game launches.

## Model

1. **Launch-day shape pool.** Every comparable launch contributes its launch-day hourly curve as log-ratios to its own hour-1 print: `r_h = ln(viewers(h) / viewers(1))`. Only launches whose shape can transfer to a rolling midnight-local console launch with no early access join the pool: a complete 24-hour launch day, an hour-1 print that is already a real audience (at least 2% of the day's peak, so the game had actually unlocked by hour 1), and an unlock that is neither a single simultaneous global unlock nor an early-access launch. Simultaneous launches (tiny hour-1 trickle, then a vertical spike at their unlock hour) and early-access launches (hour 1 already saturated) have shapes that do not transfer.
2. **Similarity weights.** The day's growth depends strongly on how big hour 1 already is (across the pool, corr(log hour-1, peak log-ratio) = −0.77: a small hour-1 base grows far more over the day than a large one). Each comparable is weighted by a Gaussian kernel on log hour-1 (bandwidth 1.0), so launches that started at a similar scale to the target dominate the quantiles.
3. **Honest spread.** Each hour's forecast quantiles are the weighted quantiles of the log-ratios across the pool, scaled by the target's own hour-1 print. No Normal assumption, no hand-set sigma — the spread comes from the cross-launch distribution itself.

If the pool is too small (< 3 launches), the program falls back to the house persistence shape (every hour stays at the hour-1 print, spread widening as `q = p·exp(z·0.15·sqrt(h−1))`).

## Local practice grade

Graded on the kit's 4 practice cases against the true hourly answers (mean pinball loss on the log scale, lower is better):

| Case | Loss | Typical miss | 90% coverage | Starter (house baseline) |
|---|---|---|---|---|
| Marvel's Wolverine | 0.294 | 76.0% | 0.957 | 0.744 |
| Red Dead Redemption 2 | 0.221 | 34.9% | 0.957 | 0.287 |
| God of War Ragnarök | 0.142 | 18.5% | 0.957 | 0.215 |
| Marvel's Spider-Man 2 | 0.205 | 25.8% | 0.783 | 0.303 |
| **Mean** | **0.215** | **37.2%** | **0.913** | **0.387** |

Mean loss 0.215 vs the house baseline's 0.387 — 44% lower, beating the baseline on all four practice cases. Typical miss 37.2% (baseline 82.7%); the 90% band covers 91.3% of hours (baseline 78.3%).

The final's pool is strictly better than the practice pool: it adds the four practice launches themselves (Wolverine, RDR2, God of War Ragnarök, Spider-Man 2) — console-exclusive, rolling-midnight, no-early-access launches, the closest analogues to GTA VI — so the final forecast should be at least as good as the practice grade.

## Running

```sh
python3 main.py            # reads /input, writes /output
MAKEFUN_INPUT_DIR=in MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Deterministic: no randomness, no wall clock, no network. Two runs write identical bytes. Runs in ~0.5 s for the practice cases (limit is 8 s per case).

## License

MIT — see [LICENSE](LICENSE).
