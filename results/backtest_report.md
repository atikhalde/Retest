# SMC Structure Scanner - Backtest Report

Generated: 2026-08-06T16:45:48

## Pattern completion rate

- Total resolved retest/re-accumulation chains: **876**
  - BOS2_CONFIRMED: 424
  - INVALIDATED: 371
  - TIMEOUT: 81
  - STILL_OPEN: 53
- **48.4%** of chains that reached re-accumulation went on to a confirmed BOS2 breakout.

## Forward returns by entry type & horizon

| entry_type             |   horizon_days |   n_trades |   win_rate_pct |   avg_return_pct |   median_return_pct |   best_pct |   worst_pct |
|:-----------------------|---------------:|-----------:|---------------:|-----------------:|--------------------:|-----------:|------------:|
| BOS2_CONFIRMED entry   |              5 |        393 |           44.3 |            -0.49 |               -0.34 |      18.15 |      -12.91 |
| BOS2_CONFIRMED entry   |             10 |        392 |           44.1 |            -0.42 |               -0.72 |      15.03 |      -12.91 |
| BOS2_CONFIRMED entry   |             20 |        383 |           42.3 |            -0.8  |               -1.15 |      19.32 |      -14.17 |
| BOS2_CONFIRMED entry   |             40 |        362 |           37.3 |            -1.42 |               -4.25 |      26.98 |      -14.47 |
| BOS2_CONFIRMED entry   |             60 |        352 |           35.2 |            -1.53 |               -5.3  |      35.89 |      -19.08 |
| PRE_BOS2_READY entry   |              5 |        563 |           40.3 |            -0.36 |               -0.78 |      10.16 |       -9.87 |
| PRE_BOS2_READY entry   |             10 |        557 |           37.3 |            -0.4  |               -1.31 |      17.45 |      -11.65 |
| PRE_BOS2_READY entry   |             20 |        544 |           30.5 |            -0.78 |               -2.13 |      17.11 |      -11.65 |
| PRE_BOS2_READY entry   |             40 |        528 |           22.9 |            -1.27 |               -2.95 |      23.4  |      -15.96 |
| PRE_BOS2_READY entry   |             60 |        521 |           19.6 |            -1.21 |               -3.14 |      34.91 |      -15.96 |
| Reaccum-Reversal entry |              5 |        726 |           58.5 |             0.77 |                0.7  |      13.97 |      -10.2  |
| Reaccum-Reversal entry |             10 |        691 |           52.7 |             0.83 |                0.36 |      19.91 |      -10.2  |
| Reaccum-Reversal entry |             20 |        682 |           48.1 |             0.67 |               -0.44 |      24.6  |      -12.66 |
| Reaccum-Reversal entry |             40 |        661 |           39.5 |             0.39 |               -1.93 |      33.69 |      -12.66 |
| Reaccum-Reversal entry |             60 |        648 |           36.3 |             0.27 |               -2.26 |      41.38 |      -12.66 |

## Notes / caveats
- Entries assume next-bar Open after the signal; stop = the chain's retest low.
- No slippage, brokerage, or position sizing modeled.
- `PRE_BOS2_READY` entries include chains that *never* confirmed BOS2 (see `eventually_confirmed` column in `backtest_pre_bos2_trades.csv`) - that's the real cost of entering early, weigh it against the better average price.
- `results/backtest_all_chains.csv` / the 'All Chains' Excel sheet lists EVERY pattern instance found (including INVALIDATED/TIMEOUT/STILL_OPEN ones that never became a trade) with its full P0/BOS1/P1/Retest/BOS2 date-and-price trail.