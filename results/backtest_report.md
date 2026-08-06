# SMC Structure Scanner - Backtest Report

Generated: 2026-08-06T18:04:37

## Pattern completion rate

- Total resolved retest/re-accumulation chains: **203**
  - BOS2_CONFIRMED: 148
  - INVALIDATED: 45
  - TIMEOUT: 10
  - STILL_OPEN: 12
- **72.9%** of chains that reached re-accumulation went on to a confirmed BOS2 breakout.

## Forward returns by entry type & horizon

| entry_type             |   horizon_days |   n_trades |   win_rate_pct |   avg_return_pct |   median_return_pct |   best_pct |   worst_pct |
|:-----------------------|---------------:|-----------:|---------------:|-----------------:|--------------------:|-----------:|------------:|
| BOS2_CONFIRMED entry   |              1 |        144 |           41   |            -0.34 |               -0.43 |       6.25 |       -5.48 |
| BOS2_CONFIRMED entry   |              2 |        143 |           44.1 |            -0.45 |               -0.13 |       6.28 |       -7.91 |
| BOS2_CONFIRMED entry   |              3 |        143 |           44.8 |            -0.53 |               -0.32 |       5.97 |       -7.5  |
| BOS2_CONFIRMED entry   |              4 |        141 |           51.1 |            -0.38 |                0.23 |       9.37 |      -10.28 |
| BOS2_CONFIRMED entry   |              5 |        140 |           47.1 |            -0.5  |               -0.2  |       9.51 |      -10.28 |
| BOS2_CONFIRMED entry   |              6 |        140 |           47.9 |            -0.74 |               -0.56 |      12.12 |      -10.28 |
| BOS2_CONFIRMED entry   |              7 |        140 |           47.1 |            -0.69 |               -0.44 |      14.23 |      -10.28 |
| BOS2_CONFIRMED entry   |              8 |        140 |           44.3 |            -0.86 |               -0.56 |      14.05 |      -10.28 |
| BOS2_CONFIRMED entry   |              9 |        140 |           42.1 |            -0.65 |               -0.46 |      13.71 |      -10.28 |
| BOS2_CONFIRMED entry   |             10 |        139 |           44.6 |            -0.64 |               -0.56 |      15.03 |      -10.28 |
| BOS2_CONFIRMED entry   |             12 |        139 |           44.6 |            -0.57 |               -0.87 |      15.58 |      -11.51 |
| BOS2_CONFIRMED entry   |             15 |        138 |           39.9 |            -1    |               -1.62 |      23.51 |      -11.51 |
| BOS2_CONFIRMED entry   |             20 |        137 |           35   |            -1.4  |               -1.79 |      23.27 |      -11.82 |
| BOS2_CONFIRMED entry   |             25 |        136 |           32.4 |            -1.58 |               -3.21 |      17.36 |      -12.82 |
| BOS2_CONFIRMED entry   |             30 |        134 |           35.8 |            -1.49 |               -2.7  |      20.93 |      -12.82 |
| BOS2_CONFIRMED entry   |             40 |        133 |           36.8 |            -1.21 |               -3.65 |      19.54 |      -13.99 |
| BOS2_CONFIRMED entry   |             60 |        126 |           32.5 |            -1.44 |               -4.98 |      22.49 |      -13.99 |
| PRE_BOS2_READY entry   |              1 |        164 |           45.1 |            -0.19 |               -0.12 |       5.68 |       -6.65 |
| PRE_BOS2_READY entry   |              2 |        164 |           39   |            -0.24 |               -0.38 |       6.23 |       -6.65 |
| PRE_BOS2_READY entry   |              3 |        162 |           46.9 |            -0.17 |               -0.26 |       7.26 |       -8.04 |
| PRE_BOS2_READY entry   |              4 |        162 |           43.2 |             0.01 |               -0.28 |      11.07 |       -8.49 |
| PRE_BOS2_READY entry   |              5 |        162 |           39.5 |            -0.07 |               -0.58 |      11.07 |       -8.49 |
| PRE_BOS2_READY entry   |              6 |        162 |           42.6 |            -0.1  |               -0.75 |       9.72 |       -8.49 |
| PRE_BOS2_READY entry   |              7 |        162 |           45.1 |            -0.05 |               -0.55 |      12.42 |       -8.49 |
| PRE_BOS2_READY entry   |              8 |        162 |           41.4 |            -0.08 |               -0.82 |      15.39 |       -8.49 |
| PRE_BOS2_READY entry   |              9 |        161 |           37.3 |            -0.14 |               -0.92 |      15.22 |       -8.49 |
| PRE_BOS2_READY entry   |             10 |        161 |           41   |            -0.01 |               -0.86 |      12.15 |       -8.49 |
| PRE_BOS2_READY entry   |             12 |        161 |           39.1 |            -0.16 |               -1.02 |      16.92 |       -8.49 |
| PRE_BOS2_READY entry   |             15 |        160 |           37.5 |            -0.27 |               -1.04 |      17.76 |       -9.84 |
| PRE_BOS2_READY entry   |             20 |        158 |           35.4 |            -0.27 |               -1.69 |      17.81 |       -9.84 |
| PRE_BOS2_READY entry   |             25 |        158 |           35.4 |            -0.17 |               -1.82 |      18.89 |      -10.07 |
| PRE_BOS2_READY entry   |             30 |        157 |           29.3 |            -0.17 |               -2.12 |      29.83 |      -10.07 |
| PRE_BOS2_READY entry   |             40 |        154 |           28.6 |             0.16 |               -2.5  |      23.54 |      -10.07 |
| PRE_BOS2_READY entry   |             60 |        150 |           23.3 |            -0.06 |               -2.65 |      23.13 |      -10.07 |
| Reaccum-Reversal entry |              1 |        196 |           55.1 |             0.6  |                0.2  |      12.54 |       -4.72 |
| Reaccum-Reversal entry |              2 |        196 |           56.6 |             0.69 |                0.4  |      12.54 |       -7.89 |
| Reaccum-Reversal entry |              3 |        194 |           66.5 |             1.11 |                0.98 |      12.54 |       -5.6  |
| Reaccum-Reversal entry |              4 |        193 |           67.4 |             1.32 |                1.12 |      12.54 |       -5.75 |
| Reaccum-Reversal entry |              5 |        193 |           64.8 |             1.41 |                1.19 |      12.54 |       -7.4  |
| Reaccum-Reversal entry |              6 |        193 |           64.8 |             1.39 |                1.4  |      13.84 |       -7.93 |
| Reaccum-Reversal entry |              7 |        190 |           64.7 |             1.48 |                1.41 |      13.1  |       -7.57 |
| Reaccum-Reversal entry |              8 |        185 |           62.7 |             1.4  |                1.32 |      13.59 |       -6.67 |
| Reaccum-Reversal entry |              9 |        184 |           59.8 |             1.3  |                1.32 |      14.5  |       -6.93 |
| Reaccum-Reversal entry |             10 |        184 |           58.2 |             1.33 |                1.25 |      16.47 |       -7.81 |
| Reaccum-Reversal entry |             12 |        184 |           55.4 |             1.36 |                1.16 |      18.12 |      -11.51 |
| Reaccum-Reversal entry |             15 |        183 |           57.4 |             1.31 |                1.4  |      16.43 |      -11.51 |
| Reaccum-Reversal entry |             20 |        183 |           52.5 |             1.17 |                0.61 |      14.7  |      -11.51 |
| Reaccum-Reversal entry |             25 |        183 |           49.2 |             0.79 |               -0.03 |      16.67 |      -11.51 |
| Reaccum-Reversal entry |             30 |        182 |           46.7 |             0.84 |               -0.28 |      28.4  |      -11.51 |
| Reaccum-Reversal entry |             40 |        180 |           45.6 |             1.03 |               -0.61 |      26.59 |      -11.51 |
| Reaccum-Reversal entry |             60 |        173 |           42.2 |             0.86 |               -1.11 |      21.29 |      -11.51 |

## Notes / caveats
- Entries assume next-bar Open after the signal; stop = the chain's retest low.
- No slippage, brokerage, or position sizing modeled.
- `PRE_BOS2_READY` entries include chains that *never* confirmed BOS2 (see `eventually_confirmed` column in `backtest_pre_bos2_trades.csv`) - that's the real cost of entering early, weigh it against the better average price.
- `results/backtest_all_chains.csv` / the 'All Chains' Excel sheet lists EVERY pattern instance found (including INVALIDATED/TIMEOUT/STILL_OPEN ones that never became a trade) with its full P0/BOS1/P1/Retest/BOS2 date-and-price trail.