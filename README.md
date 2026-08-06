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
| 🟠 `FRESH_REVERSAL` | **A higher-low reversal just confirmed** — a green candle closing back above the last confirmed swing-low candle's high, inside the base. Earlier/tighter tactical entry than waiting for the full P1 breakout (e.g. PGIL on 27 Jul, AUBank on 24 Jul 2026). |
| 🟡 `PRE_BOS2_READY` | **Re-accumulation minimum satisfied AND price is coiled within ~3% of P1.** The "catch it before it breaks" alert. |
| 🟢 `FRESH_BOS2` | Continuation breakout just confirmed (within the last few bars) — actionable now |
| ⚪ `STALE_BOS2` | Breakout already happened too long ago to be a fresh idea |

## Setup Quality (A/B/C/D)

Every signal also gets a composite 0-100 quality score and letter grade
(`src/smc_scanner/scoring.py`), so signals aren't all treated equally - a
`FRESH_REVERSAL` at 9/9 confluence with one clean pivot low is a very
different bet than one at 2/9 confluence sitting 13% below resistance.

| Component | Points | What it measures |
|---|---|---|
| Confluence | 40 | EMA trend/rising, RSI>threshold/rising, MACD histogram, volume vs average, green candle, near 52w high (scaled from the 0-9 confluence score) |
| Structure cleanliness | 20 | Fewer confirmed pivot-low reversals in the re-accumulation window = a cleaner base (1 reversal scores highest, 5+ scores lowest) |
| Volatility contraction | 15 | Has the range tightened up (coiled) ahead of the move |
| Re-accumulation duration fit | 15 | ~10-40 trading days is the sweet spot; too short or too long scores lower |
| Stage maturity | 10 | How confirmed the setup is right now (FRESH_BOS2 > FRESH_REVERSAL > PRE_BOS2_READY > BASING > IN_RETEST) |

**Grades:** A (80-100, High-Quality) · B (65-79, Good) · C (50-64, Moderate/Watch) · D (<50, Weak/Low-Quality)

Shown as `quality_score`/`quality_grade` in every scan result, in Telegram
alerts, in the "Live Signals Now" sheet of `backtest_results.xlsx`, and as
the "Setup Quality" column in `backtest_simple.xlsx`. Historical rows in the
backtest are scored **as of the moment the signal fired** (not with today's
hindsight), so a symbol's live grade today can differ from its grade back
when that specific historical signal triggered - that's intentional, it
avoids look-ahead bias in the backtest numbers.

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
`PRE_BOS2_READY` and the first "higher-low reversal" day, and back-tests
**three** entry styles (confirmed breakout / anticipatory pre-breakout /
reversal) at granular forward horizons (1,2,3,4,5,6,7,8,9,10,12,15,20,25,30,
40,60 trading days), with a hard stop at the chain's retest low. Override
via `--horizons "1,2,3,..."` on the CLI.

### Best holding period found so far

On an 80-symbol run, the **Reaccum-Reversal entry** (the best of the three
styles) peaks at a **4-7 trading day hold**: win rate peaks at day 4
(67.5%), average return peaks at day 7 (1.48%), and the whole 4-7 day
window is a consistent plateau (64.9-67.5% win rate). Both win rate and
average return decay steadily beyond day ~10-15, dropping to 47-53% win
rate by day 20-30 - holding this entry style for weeks adds risk without
added expected return. The other two entry styles (BOS2_CONFIRMED,
PRE_BOS2_READY) never develop a comparably strong edge at any horizon in
this sample - re-validate on your own universe before trusting this.

Run it (`python -m smc_scanner.cli backtest`) and read
`results/backtest_report.md` before trusting live alerts. **Re-tune
`Config` (breakout buffer, volume multipliers, proximity %, min re-accum
bars) against your own universe/holding-period before sizing real risk on
this.**

### Running it yourself in GitHub Actions

Actions tab → **"Backtest"** → *Run workflow* (optionally set how many
symbols from `data/backtest_universe_sample.txt` to use). It installs
dependencies, runs the backtest via yfinance (no Dhan quota used), exports
`results/backtest_results.xlsx`, commits everything back to the repo, and
also uploads it as a downloadable workflow artifact.

### Excel workbook contents

Two workbooks get produced - start with the simple one:

**`results/backtest_simple.xlsx`** (via `scripts/export_backtest_simple.py`) -
**one plain-English sheet**, one row per pattern instance, sorted so the most
recently active setups are on top:

`Stock | Status | Base Date/Price | Breakout Date/Price | Peak Date/Price | Retest Date/Price | Re-Accumulation Start/Days | Pre-Breakout Alert Date | Confirmed Breakout Date/Price | Entry Date/Price | Stop Loss | Return 5D/10D/20D/40D/60D % | Trade Status`

`Status` is colour-coded: green = Breakout Confirmed, red = Failed (support
broke), yellow = Timed Out, blue = Still Forming. `Trade Status` tells you
exactly why a row has blank returns - e.g. "Pending (triggered on latest
bar - no return yet)" for a signal that fired today, like PGIL's current
breakout.

**`results/backtest_results.xlsx`** (via `scripts/export_backtest_excel.py`)
- the full, multi-sheet breakdown for deeper analysis:

| Sheet | Contents |
|---|---|
| Live Signals Now | symbols currently `FRESH_BOS2`/`PRE_BOS2_READY` as of the latest bar - independent of historical stats |
| Summary | headline stats + forward-return table by entry type & horizon |
| Outcome Counts | BOS2_CONFIRMED / INVALIDATED / TIMEOUT / STILL_OPEN breakdown |
| By Symbol | per-stock signal counts & average returns |
| All Chains | every pattern instance, full stage trail, incl. invalidated/timed-out ones |
| BOS2 Trades | confirmed-breakout entries, entry price/date, stop, `trade_status`, forward returns |
| PreBOS2 Trades | anticipatory (pre-breakout) entries, plus `eventually_confirmed` |
| Notes | methodology & caveats |

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
