# SMC Structure Scanner - Backtest Report

Generated: 2026-08-06T17:48:45

## Pattern completion rate

- Total resolved retest/re-accumulation chains: **204**
  - BOS2_CONFIRMED: 149
  - INVALIDATED: 45
  - TIMEOUT: 10
  - STILL_OPEN: 11
- **73.0%** of chains that reached re-accumulation went on to a confirmed BOS2 breakout.

## Forward returns by entry type & horizon

| entry_type             |   horizon_days |   n_trades |   win_rate_pct |   avg_return_pct |   median_return_pct |   best_pct |   worst_pct |
|:-----------------------|---------------:|-----------:|---------------:|-----------------:|--------------------:|-----------:|------------:|
| BOS2_CONFIRMED entry   |              5 |        140 |           47.1 |            -0.5  |               -0.2  |       9.51 |      -10.28 |
| BOS2_CONFIRMED entry   |             10 |        140 |           45   |            -0.59 |               -0.5  |      15.03 |      -10.28 |
| BOS2_CONFIRMED entry   |             20 |        136 |           35.3 |            -1.36 |               -1.76 |      23.27 |      -11.82 |
| BOS2_CONFIRMED entry   |             40 |        132 |           37.1 |            -1.18 |               -3.63 |      19.54 |      -13.99 |
| BOS2_CONFIRMED entry   |             60 |        125 |           32.8 |            -1.39 |               -4.97 |      22.49 |      -13.99 |
| PRE_BOS2_READY entry   |              5 |        162 |           39.5 |            -0.07 |               -0.58 |      11.07 |       -8.49 |
| PRE_BOS2_READY entry   |             10 |        161 |           41   |            -0.01 |               -0.86 |      12.15 |       -8.49 |
| PRE_BOS2_READY entry   |             20 |        158 |           35.4 |            -0.27 |               -1.69 |      17.81 |       -9.84 |
| PRE_BOS2_READY entry   |             40 |        154 |           28.6 |             0.16 |               -2.5  |      23.54 |      -10.07 |
| PRE_BOS2_READY entry   |             60 |        150 |           23.3 |            -0.06 |               -2.65 |      23.13 |      -10.07 |
| Reaccum-Reversal entry |              5 |        193 |           64.2 |             1.38 |                1.18 |      12.54 |       -7.4  |
| Reaccum-Reversal entry |             10 |        184 |           58.2 |             1.33 |                1.25 |      16.47 |       -7.81 |
| Reaccum-Reversal entry |             20 |        182 |           52.7 |             1.21 |                0.64 |      14.7  |      -11.51 |
| Reaccum-Reversal entry |             40 |        179 |           45.8 |             1.07 |               -0.59 |      26.59 |      -11.51 |
| Reaccum-Reversal entry |             60 |        172 |           42.4 |             0.91 |               -1.1  |      21.29 |      -11.51 |

## Notes / caveats
- Entries assume next-bar Open after the signal; stop = the chain's retest low.
- No slippage, brokerage, or position sizing modeled.
- `PRE_BOS2_READY` entries include chains that *never* confirmed BOS2 (see `eventually_confirmed` column in `backtest_pre_bos2_trades.csv`) - that's the real cost of entering early, weigh it against the better average price.
- `results/backtest_all_chains.csv` / the 'All Chains' Excel sheet lists EVERY pattern instance found (including INVALIDATED/TIMEOUT/STILL_OPEN ones that never became a trade) with its full P0/BOS1/P1/Retest/BOS2 date-and-price trail.