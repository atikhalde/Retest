# SMC Structure Scanner

Automated screener for the **Base → Impulse (BOS #1) → Retest →
Re-accumulation → Continuation (BOS #2) → Markup** structure — the same
read done manually on Pearl Global Industries (PGIL) in Aug 2026 — running
on a schedule in GitHub Actions against live Dhan market data, with Telegram
alerts and a historical backtest of the pattern's actual edge.

Key feature: it doesn't just flag stocks *after* they've already broken out.
It has a dedicated **`PRE_BOS2_READY`** stage that fires once a stock has
finished re-accumulating and is coiled tightly just under the breakout level
— **before** BOS #2 actually happens — so you can watch/prepare instead of
chasing.

## Stages

| Stage | Meaning |
|---|---|
| `IN_RETEST` | Just bounced off the retest zone; too early to call it re-accumulation |
| `BASING` | Re-accumulating, but still well below the breakout trigger (P1) |
| 🟡 `PRE_BOS2_READY` | **Re-accumulation minimum satisfied AND price is coiled within ~3% of P1.** The "catch it before it breaks" alert. |
| 🟢 `FRESH_BOS2` | Continuation breakout just confirmed (within the last few bars) — actionable now |
| ⚪ `STALE_BOS2` | Breakout already happened too long ago to be a fresh idea |

## Repo layout

```
src/smc_scanner/
  config.py         tunable parameters (env-var overridable)
  indicators.py      EMA/RSI/MACD/ATR + confluence scoreboard
  pivots.py           fractal swing-high/low detection
  pattern.py          the core Base->Impulse->Retest->Reaccum->BOS2 detector
  scanner.py          orchestration: universe -> data -> pattern -> alerts
  backtest.py         historical edge test (win rate / forward returns)
  universe.py         builds & loads the scan universe (NSE cash equities, mkt cap filter)
  notify.py           Telegram alerting
  data_sources/
    dhan.py           Dhan HQ v2 API client (auth, historical+intraday candles)
    yfinance_source.py  fallback source, used for local testing & backtests
  cli.py              `python -m smc_scanner.cli {build-universe,scan,backtest}`
scripts/
  market_hours_guard.py   used by the intraday workflow to no-op outside NSE hours
.github/workflows/
  update_universe.yml     weekly - rebuilds data/universe.csv
  eod_scan.yml            daily, ~15:45 IST - confirmation scan after close
  intraday_scan.yml       every 15 min during market hours - catches PRE_BOS2_READY/FRESH_BOS2 live
  backtest.yml            on-demand / monthly - historical edge report
  tests.yml               runs pytest on every push
data/
  universe.csv        scan universe (bootstrap sample checked in; rebuilt by the workflow)
  nse_holidays.txt    NSE holiday calendar (update yearly)
results/
  latest_scan.csv, state.json, backtest_*.csv/md   (committed back by the workflows)
```

## 1. Dhan API setup

You said you already have a Dhan token + client ID. Two auth modes are
supported (`src/smc_scanner/data_sources/dhan.py`):

**Recommended for unattended cron (survives weekends without manual refresh):**
1. On [web.dhan.co](https://web.dhan.co) → *My Profile → Access DhanHQ APIs → Setup TOTP*.
2. Scan the QR with an authenticator app **and** save the base32 secret it shows you.
3. Set repo secrets: `DHAN_CLIENT_ID`, `DHAN_PIN`, `DHAN_TOTP_SECRET`.
4. Every workflow run mints a brand-new 24h access token itself via
   `POST https://auth.dhan.co/app/generateAccessToken` — nothing to rotate.

**Simplest, but needs daily manual refresh:**
1. `web.dhan.co → My Profile → Access DhanHQ APIs → Generate Access Token` (valid 24h).
2. Set repo secrets: `DHAN_CLIENT_ID`, `DHAN_ACCESS_TOKEN`.
3. You must update `DHAN_ACCESS_TOKEN` yourself every day (or the daily/intraday runs will fail after ~24h).

Rate limits (per Dhan's docs): 5 data requests/sec, 100k/day — the client
throttles to 4/sec automatically, and the universe is capped by your market
cap filter to keep each run comfortably under this.

## 2. Telegram alerts

You mentioned you already have a bot. Add these as repo secrets:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID` (message your bot once, then hit
  `https://api.telegram.org/bot<token>/getUpdates` to read your chat id back)

Alerts only fire on a **stage transition** into `PRE_BOS2_READY` or
`FRESH_BOS2` (tracked in `results/state.json`) — you won't get spammed every
15 minutes for the same stock sitting in the same stage.

## 3. Add secrets on GitHub

Repo → **Settings → Secrets and variables → Actions → New repository secret**:

```
DHAN_CLIENT_ID
DHAN_PIN              (if using TOTP mode)
DHAN_TOTP_SECRET       (if using TOTP mode)
DHAN_ACCESS_TOKEN      (if using static-token mode instead)
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

## 4. First run

1. Actions tab → **"Update universe"** → *Run workflow* (builds a real
   `data/universe.csv` from Dhan's live scrip master + market caps — the
   checked-in file is just a 5-symbol bootstrap sample).
2. Actions tab → **"EOD scan"** → *Run workflow* to sanity check end-to-end
   with your real Dhan credentials.
3. Once that's green, the schedules take over automatically:
   - **Intraday scan**: every 15 min, 9:15 AM–3:30 PM IST, Mon–Fri
   - **EOD scan**: 15:45 IST, Mon–Fri
   - **Update universe**: Sundays
   - **Backtest**: on-demand, or monthly

## Local usage

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in for local testing; GitHub Actions uses repo secrets instead
export $(grep -v '^#' .env | xargs)   # or use python-dotenv / direnv

export PYTHONPATH=src
python -m smc_scanner.cli build-universe
python -m smc_scanner.cli scan --mode eod
python -m smc_scanner.cli scan --mode intraday   # includes today's in-progress candle via Dhan intraday API
python -m smc_scanner.cli backtest --data-source yfinance --limit 150
```

Testing without Dhan credentials at all (yfinance fallback):
```bash
python -m smc_scanner.cli scan --data-source yfinance --mode eod
```

## Backtest: what it actually measures

`backtest.py` walks each symbol's **entire** history once and enumerates
*every* retest → re-accumulation chain (not just the latest, unlike the live
scanner), classifying each into:

- `BOS2_CONFIRMED` — broke back above P1 with a volume kick
- `INVALIDATED` — closed back below P0 first (structure failed)
- `TIMEOUT` — re-accumulation dragged on past `max_reaccum_bars` unresolved
- `STILL_OPEN` — ran into the end of available data (excluded from stats)

For every chain it also finds the first day it would have flagged
`PRE_BOS2_READY`, and back-tests **both** entry styles (confirmed breakout
vs. anticipatory pre-breakout) at fixed forward horizons (5/10/20/40/60
trading days), with a hard stop at the chain's retest low.

Run it (`python -m smc_scanner.cli backtest`) and read
`results/backtest_report.md` before trusting live alerts — on a first
15-symbol large-cap smoke test the pattern completed only ~43% of the time
it reached re-accumulation, and forward returns were mixed/negative at
longer horizons. **Re-tune `Config` (breakout buffer, volume multipliers,
proximity %, min re-accum bars) against your own universe/holding-period
before sizing real risk on this.**

### Running it yourself in GitHub Actions

Actions tab → **"Backtest"** → *Run workflow* (optionally set how many
symbols from `data/backtest_universe_sample.txt` to use). It installs
dependencies, runs the backtest via yfinance (no Dhan quota used), exports
`results/backtest_results.xlsx`, commits everything back to the repo, and
also uploads it as a downloadable workflow artifact.

### Excel workbook contents

`scripts/export_backtest_excel.py` turns the raw CSVs into
`results/backtest_results.xlsx` with 8 sheets:

| Sheet | Contents |
|---|---|
| **Live Signals Now** | **the "what looks like PGIL right now" view** - every symbol currently `FRESH_BOS2` or `PRE_BOS2_READY` as of the most recent bar fetched, independent of historical stats (e.g. on one run this listed PGIL, SBIN, BAJFINANCE, CHOLAFIN, PIDILITIND and 12 others all showing `FRESH_BOS2` the same day) |
| Summary | headline stats + forward-return table by entry type & horizon |
| Outcome Counts | BOS2_CONFIRMED / INVALIDATED / TIMEOUT / STILL_OPEN breakdown |
| By Symbol | per-stock signal counts & average returns |
| All Chains | every single pattern instance found, one row per chain, with its full stage trail: `symbol`, `outcome`, `p0_date`/`p0_price`, `bos1_date`/`bos1_price`, `p1_date`/`p1_price`, `retest_date`/`retest_price`, `reaccumulation_start_date`, `reaccum_bars`, `pre_bos2_ready_date`, `bos2_date`/`bos2_price` — includes chains that never became a trade (invalidated/timed out), for full transparency |
| BOS2 Trades | the subset of "All Chains" that confirmed BOS2, plus entry price/date, stop, `trade_status`, and 5/10/20/40/60-day forward returns |
| PreBOS2 Trades | the anticipatory entry (first `PRE_BOS2_READY` day) version of the same, plus `eventually_confirmed` (did it actually break out later?) |
| Notes | methodology & caveats, verbatim from `backtest_report.md` |

`trade_status` on every trade row is one of:
- `PENDING_ENTRY` — the signal fired on the very last available bar (i.e. **today**), so there's no next session's Open yet to simulate an entry on. This is why a just-fired signal (like PGIL's current breakout) shows up with blank returns instead of being silently dropped — it hasn't had a chance to move yet.
- `STOPPED_OUT` — the stop (chain's retest low) was hit; every horizon reports that same locked-in exit return from then on, even without that many days of trailing data yet.
- `OPEN` — still within the holding period, more horizons pending.
- `COMPLETE` — ran the full horizon window without ever stopping out.

Return columns are colour-scaled (red→yellow→green) and every sheet is a
filterable/sortable Excel table.

## Tuning

Everything lives in `src/smc_scanner/config.py`, most of it also overridable
via env vars (see `.env.example`): pivot window, breakout volume multiples,
retest tolerance, minimum re-accumulation length, `PRE_BOS2_READY` proximity
threshold, volatility-contraction threshold, recency window, RSI/EMA/price
filters, and the market-cap floor.

## Caveats

- **Not investment advice.** Structural/technical filter only.
- yfinance (used for market cap in `build_universe` and for backtests) hits
  an unofficial Yahoo endpoint that can rate-limit large bursts from one IP.
  `build_universe` caches resolved market caps for 25 days and only retries
  missing/stale ones, so coverage improves run-over-run even if one run gets
  throttled.
- Pivot detection has an inherent confirmation lag (`pivot_right` bars) —
  by design, to avoid repainting.
- The intraday mode's indicators (EMA/RSI/MACD) on the still-forming candle
  are provisional until the session closes.
- Treat `PRE_BOS2_READY` as a **watch** alert, not a buy signal — the
  backtest's `INVALIDATED`/`TIMEOUT` outcome counts show a meaningful chunk
  of these never actually break out.
