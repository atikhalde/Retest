# SMC Structure Scanner - Backtest Report

Generated: 2026-08-06T11:09:30

## Pattern completion rate

- Total resolved retest/re-accumulation chains: **158**
  - BOS2_CONFIRMED: 68
  - INVALIDATED: 73
  - TIMEOUT: 17
  - STILL_OPEN: 8
- **43.0%** of chains that reached re-accumulation went on to a confirmed BOS2 breakout.

## Forward returns by entry type & horizon

| entry_type           |   horizon_days |   n_trades |   win_rate_pct |   avg_return_pct |   median_return_pct |   best_pct |   worst_pct |
|:---------------------|---------------:|-----------:|---------------:|-----------------:|--------------------:|-----------:|------------:|
| BOS2_CONFIRMED entry |              5 |         66 |           48.5 |             0.69 |               -0.3  |      18.15 |       -6.66 |
| BOS2_CONFIRMED entry |             10 |         65 |           40   |             0.08 |               -0.85 |      15.03 |       -9.37 |
| BOS2_CONFIRMED entry |             20 |         64 |           45.3 |             0.55 |               -0.32 |      19.32 |      -11.04 |
| BOS2_CONFIRMED entry |             40 |         57 |           38.6 |            -1.06 |               -3.26 |      17.59 |      -13.99 |
| BOS2_CONFIRMED entry |             60 |         55 |           38.2 |            -1.98 |               -5    |      12.97 |      -13.99 |
| PRE_BOS2_READY entry |              5 |        112 |           47.3 |            -0.05 |               -0.21 |      10.01 |       -7.47 |
| PRE_BOS2_READY entry |             10 |        112 |           36.6 |             0.14 |               -1.08 |      17.45 |       -7.47 |
| PRE_BOS2_READY entry |             20 |        106 |           33   |            -0.15 |               -1.66 |      16.9  |       -7.47 |
| PRE_BOS2_READY entry |             40 |        102 |           28.4 |            -0.5  |               -2.14 |      21.63 |      -15.96 |
| PRE_BOS2_READY entry |             60 |         99 |           22.2 |            -0.76 |               -2.53 |      24.3  |      -15.96 |

## Notes / caveats
- Entries assume next-bar Open after the signal; stop = the chain's retest low.
- No slippage, brokerage, or position sizing modeled.
- `PRE_BOS2_READY` entries include chains that *never* confirmed BOS2 (see `eventually_confirmed` column in `backtest_pre_bos2_trades.csv`) - that's the real cost of entering early, weigh it against the better average price.