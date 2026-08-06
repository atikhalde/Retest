# `data/` folder

- `universe.csv` - **bootstrap sample only** (5 well-known large caps with
  market caps captured on 2026-08-06). The real, full NSE-cash-equity
  universe (currently ~3,700 candidates before filtering, ~600+ pass the
  default >=1000cr filter) is built automatically by the
  **"Update universe"** GitHub Actions workflow
  (`.github/workflows/update_universe.yml`).

  **Run it once manually right after setting up secrets** (Actions tab ->
  "Update universe" -> "Run workflow") so the scanner has a real universe to
  work with before its first scheduled Sunday run. It pulls Dhan's live
  scrip-master CSV and enriches it with market caps via yfinance.

  Note: yfinance's market-cap lookup uses an unofficial Yahoo Finance
  endpoint that can rate-limit bursts of thousands of requests from a single
  IP. `build_universe()` handles this by caching each symbol's market cap
  for `max_age_days` (default 25) and only re-fetching new/stale symbols, so
  a partially-rate-limited run never wipes out previously-resolved data -
  coverage simply improves run over run.

- `nse_holidays.txt` - NSE trading holiday list (update yearly).

- `cache/` - gitignored; local disk cache for the downloaded Dhan
  scrip-master CSV.
