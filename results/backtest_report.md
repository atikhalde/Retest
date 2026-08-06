# SMC Structure Scanner - Backtest Report

Generated: 2026-08-06T19:41:02

## Pattern completion rate

- Total resolved retest/re-accumulation chains: **201**
  - BOS2_CONFIRMED: 146
  - INVALIDATED: 45
  - TIMEOUT: 10
  - STILL_OPEN: 14
- **72.6%** of chains that reached re-accumulation went on to a confirmed BOS2 breakout.

## Forward returns by entry type & horizon

| entry_type             |   horizon_days |   n_trades |   win_rate_pct |   avg_return_pct |   median_return_pct |   best_pct |   worst_pct |
|:-----------------------|---------------:|-----------:|---------------:|-----------------:|--------------------:|-----------:|------------:|
| BOS2_CONFIRMED entry   |              1 |        143 |           41.3 |            -0.33 |               -0.4  |       6.25 |       -5.48 |
| BOS2_CONFIRMED entry   |              2 |        143 |           44.1 |            -0.45 |               -0.13 |       6.28 |       -7.91 |
| BOS2_CONFIRMED entry   |              3 |        141 |           45.4 |            -0.48 |               -0.32 |       5.97 |       -7.5  |
| BOS2_CONFIRMED entry   |              4 |        140 |           50.7 |            -0.39 |                0.14 |       9.37 |      -10.28 |
| BOS2_CONFIRMED entry   |              5 |        140 |           47.1 |            -0.5  |               -0.2  |       9.51 |      -10.28 |
| BOS2_CONFIRMED entry   |              6 |        140 |           47.9 |            -0.74 |               -0.56 |      12.12 |      -10.28 |
| BOS2_CONFIRMED entry   |              7 |        140 |           47.1 |            -0.69 |               -0.44 |      14.23 |      -10.28 |
| BOS2_CONFIRMED entry   |              8 |        140 |           44.3 |            -0.86 |               -0.56 |      14.05 |      -10.28 |
| BOS2_CONFIRMED entry   |              9 |        139 |           41.7 |            -0.7  |               -0.46 |      13.71 |      -10.28 |
| BOS2_CONFIRMED entry   |             10 |        139 |           44.6 |            -0.64 |               -0.56 |      15.03 |      -10.28 |
| BOS2_CONFIRMED entry   |             12 |        139 |           44.6 |            -0.57 |               -0.87 |      15.58 |      -11.51 |
| BOS2_CONFIRMED entry   |             15 |        138 |           39.9 |            -1    |               -1.62 |      23.51 |      -11.51 |
| BOS2_CONFIRMED entry   |             20 |        137 |           35   |            -1.4  |               -1.79 |      23.27 |      -11.82 |
| BOS2_CONFIRMED entry   |             25 |        134 |           32.1 |            -1.58 |               -3.21 |      17.36 |      -12.82 |
| BOS2_CONFIRMED entry   |             30 |        134 |           35.8 |            -1.49 |               -2.7  |      20.93 |      -12.82 |
| BOS2_CONFIRMED entry   |             40 |        131 |           35.9 |            -1.31 |               -3.68 |      19.54 |      -13.99 |
| BOS2_CONFIRMED entry   |             60 |        126 |           32.5 |            -1.44 |               -4.98 |      22.49 |      -13.99 |
| PRE_BOS2_READY entry   |              1 |        164 |           45.1 |            -0.19 |               -0.12 |       5.68 |       -6.65 |
| PRE_BOS2_READY entry   |              2 |        162 |           38.9 |            -0.23 |               -0.38 |       6.23 |       -6.65 |
| PRE_BOS2_READY entry   |              3 |        162 |           46.9 |            -0.17 |               -0.26 |       7.26 |       -8.04 |
| PRE_BOS2_READY entry   |              4 |        162 |           43.2 |             0.01 |               -0.28 |      11.07 |       -8.49 |
| PRE_BOS2_READY entry   |              5 |        162 |           39.5 |            -0.07 |               -0.58 |      11.07 |       -8.49 |
| PRE_BOS2_READY entry   |              6 |        162 |           42.6 |            -0.1  |               -0.75 |       9.72 |       -8.49 |
| PRE_BOS2_READY entry   |              7 |        162 |           45.1 |            -0.05 |               -0.55 |      12.42 |       -8.49 |
| PRE_BOS2_READY entry   |              8 |        161 |           41.6 |            -0.08 |               -0.86 |      15.39 |       -8.49 |
| PRE_BOS2_READY entry   |              9 |        161 |           37.3 |            -0.14 |               -0.92 |      15.22 |       -8.49 |
| PRE_BOS2_READY entry   |             10 |        161 |           41   |            -0.01 |               -0.86 |      12.15 |       -8.49 |
| PRE_BOS2_READY entry   |             12 |        161 |           39.1 |            -0.16 |               -1.02 |      16.92 |       -8.49 |
| PRE_BOS2_READY entry   |             15 |        159 |           37.7 |            -0.26 |               -1.02 |      17.76 |       -9.84 |
| PRE_BOS2_READY entry   |             20 |        158 |           35.4 |            -0.27 |               -1.69 |      17.81 |       -9.84 |
| PRE_BOS2_READY entry   |             25 |        157 |           35   |            -0.2  |               -1.83 |      18.89 |      -10.07 |
| PRE_BOS2_READY entry   |             30 |        156 |           28.8 |            -0.19 |               -2.12 |      29.83 |      -10.07 |
| PRE_BOS2_READY entry   |             40 |        154 |           28.6 |             0.16 |               -2.5  |      23.54 |      -10.07 |
| PRE_BOS2_READY entry   |             60 |        150 |           23.3 |            -0.06 |               -2.65 |      23.13 |      -10.07 |
| Reaccum-Reversal entry |              1 |        197 |           54.8 |             0.57 |                0.19 |      12.54 |       -5.79 |
| Reaccum-Reversal entry |              2 |        195 |           55.9 |             0.65 |                0.3  |      12.54 |       -7.89 |
| Reaccum-Reversal entry |              3 |        194 |           66.5 |             1.11 |                0.98 |      12.54 |       -5.79 |
| Reaccum-Reversal entry |              4 |        194 |           67   |             1.28 |                1.1  |      12.54 |       -5.79 |
| Reaccum-Reversal entry |              5 |        194 |           64.4 |             1.37 |                1.19 |      12.54 |       -7.4  |
| Reaccum-Reversal entry |              6 |        191 |           63.9 |             1.28 |                1.33 |      13.84 |       -7.93 |
| Reaccum-Reversal entry |              7 |        186 |           63.4 |             1.39 |                1.41 |      13.1  |       -7.57 |
| Reaccum-Reversal entry |              8 |        185 |           62.2 |             1.34 |                1.28 |      13.59 |       -6.67 |
| Reaccum-Reversal entry |              9 |        185 |           59.5 |             1.26 |                1.31 |      14.5  |       -6.93 |
| Reaccum-Reversal entry |             10 |        185 |           57.8 |             1.29 |                1.19 |      16.47 |       -7.81 |
| Reaccum-Reversal entry |             12 |        184 |           54.9 |             1.29 |                1.08 |      18.12 |      -11.51 |
| Reaccum-Reversal entry |             15 |        184 |           57.1 |             1.27 |                1.36 |      16.43 |      -11.51 |
| Reaccum-Reversal entry |             20 |        184 |           52.2 |             1.13 |                0.57 |      14.7  |      -11.51 |
| Reaccum-Reversal entry |             25 |        184 |           48.9 |             0.75 |               -0.04 |      16.67 |      -11.51 |
| Reaccum-Reversal entry |             30 |        183 |           46.4 |             0.8  |               -0.31 |      28.4  |      -11.51 |
| Reaccum-Reversal entry |             40 |        181 |           45.3 |             0.99 |               -0.63 |      26.59 |      -11.51 |
| Reaccum-Reversal entry |             60 |        174 |           42   |             0.83 |               -1.18 |      21.29 |      -11.51 |

## Notes / caveats
- Entries assume next-bar Open after the signal; stop = the chain's retest low.
- No slippage, brokerage, or position sizing modeled.
- `PRE_BOS2_READY` entries include chains that *never* confirmed BOS2 (see `eventually_confirmed` column in `backtest_pre_bos2_trades.csv`) - that's the real cost of entering early, weigh it against the better average price.
- `results/backtest_all_chains.csv` / the 'All Chains' Excel sheet lists EVERY pattern instance found (including INVALIDATED/TIMEOUT/STILL_OPEN ones that never became a trade) with its full P0/BOS1/P1/Retest/BOS2 date-and-price trail.