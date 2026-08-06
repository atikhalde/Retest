# SMC Structure Scanner - Backtest Report

Generated: 2026-08-06T15:58:47

## Pattern completion rate

- Total resolved retest/re-accumulation chains: **876**
  - BOS2_CONFIRMED: 424
  - INVALIDATED: 371
  - TIMEOUT: 81
  - STILL_OPEN: 53
- **48.4%** of chains that reached re-accumulation went on to a confirmed BOS2 breakout.

## Forward returns by entry type & horizon

| entry_type           |   horizon_days |   n_trades |   win_rate_pct |   avg_return_pct |   median_return_pct |   best_pct |   worst_pct |
|:---------------------|---------------:|-----------:|---------------:|-----------------:|--------------------:|-----------:|------------:|
| BOS2_CONFIRMED entry |              5 |        393 |           44.3 |            -0.49 |               -0.34 |      18.15 |      -12.91 |
| BOS2_CONFIRMED entry |             10 |        392 |           44.1 |            -0.42 |               -0.72 |      15.03 |      -12.91 |
| BOS2_CONFIRMED entry |             20 |        382 |           42.4 |            -0.78 |               -1.12 |      19.32 |      -14.17 |
| BOS2_CONFIRMED entry |             40 |        358 |           37.7 |            -1.35 |               -4.15 |      26.98 |      -14.47 |
| BOS2_CONFIRMED entry |             60 |        345 |           35.9 |            -1.4  |               -5.26 |      35.89 |      -19.08 |
| PRE_BOS2_READY entry |              5 |        563 |           40.3 |            -0.36 |               -0.78 |      10.16 |       -9.87 |
| PRE_BOS2_READY entry |             10 |        552 |           37.7 |            -0.39 |               -1.29 |      17.45 |      -11.65 |
| PRE_BOS2_READY entry |             20 |        526 |           31.4 |            -0.7  |               -2.12 |      17.11 |      -11.65 |
| PRE_BOS2_READY entry |             40 |        504 |           23.8 |            -1.16 |               -2.9  |      23.4  |      -15.96 |
| PRE_BOS2_READY entry |             60 |        480 |           21   |            -0.98 |               -3.13 |      34.91 |      -15.96 |

## Notes / caveats
- Entries assume next-bar Open after the signal; stop = the chain's retest low.
- No slippage, brokerage, or position sizing modeled.
- `PRE_BOS2_READY` entries include chains that *never* confirmed BOS2 (see `eventually_confirmed` column in `backtest_pre_bos2_trades.csv`) - that's the real cost of entering early, weigh it against the better average price.
- `results/backtest_all_chains.csv` / the 'All Chains' Excel sheet lists EVERY pattern instance found (including INVALIDATED/TIMEOUT/STILL_OPEN ones that never became a trade) with its full P0/BOS1/P1/Retest/BOS2 date-and-price trail.