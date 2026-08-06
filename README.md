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
alerts, and as the "Quality Score"/"Quality Grade" columns in
`backtest_results.xlsx`. Historical rows in the backtest are scored **as of
the moment the signal fired** (not with today's hindsight), so a symbol's
live grade today can differ from its grade back when that specific
historical signal triggered - that's intentional, it avoids look-ahead bias
in the backtest numbers.

## Trade Plan (entry / stop / target / exit window)

For actionable stages (`FRESH_BOS2`, `FRESH_REVERSAL`) the scanner also
computes a concrete trade plan (`src/smc_scanner/trade_plan.py`), wiring
together everything found in this analysis:

- **Entry**: next NSE trading session's open (uses the real trading
  calendar - `data/nse_holidays.txt` + weekends, not just calendar days)
- **Stop Loss**: the chain's retest low (the *structural* stop) - validated
  in `scripts/optimize_stop_loss.py` as the best-performing stop at every
  point in the 4-7 day holding window, beating fixed-% and ATR stops
- **Target**: entry +/- `target_reward_risk` (default 1.0, i.e. 1:1) x the
  stop distance - backtested average risk (~3.33%) and average
  winning-trade return (~3.39%) over a 5-7 day hold are almost exactly 1:1
- **Exit window**: `entry_date` + 4 to + 7 trading days - hold this long
  regardless of whether the target is hit (win rate peaks at day 4 ~67.5%,
  average return peaks at day 7 ~1.48%, edge decays steadily after day ~10)

Exposed as `entry_date`, `entry_price_ref`, `stop_loss`, `risk_pct`,
`target_price`, `target_pct`, `reward_risk`, `exit_by_min_date`,
`exit_by_max_date` in every scan result, printed in a dedicated "TRADE
PLANS" section by `smc_scanner scan`, in the "Live Signals Now" sheet of
`backtest_results.xlsx`, and as a full 📋 *Trade Plan* block in every
Telegram alert. Tune `target_reward_risk`, `hold_days_min`/`hold_days_max`
in `Config` if you re-validate on your own universe and get a different
optimum.

## Repo layout

```
src/smc_scanner/
  config.py         tunable parameters (env-var overridable)
  indicators.py      EMA/RSI/MACD/ATR + confluence scoreboard
  pivots.py           fractal swing-high/low + higher-low reversal detection
  weekly.py           weekly-timeframe BOS1 gate (genuine new N-week-high breakout)
  pattern.py          the core Base->Impulse->Retest->Reaccum->Reversal->BOS2 detector
  scoring.py          composite A/B/C/D setup-quality scoring
  trade_plan.py       entry/stop/target/exit-window generator for actionable signals
  scanner.py          orchestration: universe -> data -> pattern -> alerts
  backtest.py         historical edge test (win rate / forward returns)
  universe.py         builds & loads the scan universe (NSE cash equities, mkt cap filter)
  notify.py           Telegram alerting
  data_sources/
    dhan.py           Dhan HQ v2 API client (auth, historical+intraday candles)
    yfinance_source.py  fallback source, used for local testing & backtests
  cli.py              `python -m smc_scanner.cli {build-universe,scan,backtest}`
scripts/
  market_hours_guard.py     used by the intraday workflow to no-op outside NSE hours
  check_dhan_token.py       Option B daily reminder - alerts via Telegram if the static Dhan token is stale
  export_backtest_excel.py  builds results/backtest_results.xlsx (single sheet, 11 columns - see "Backtest" below)
  optimize_stop_loss.py     sweeps stop-loss methods across the best holding window
.github/workflows/
  update_universe.yml     weekly - rebuilds data/universe.csv
  check_dhan_token.yml    daily, ~08:45 IST (before market open) - Telegram alert if the static token is stale
  eod_scan.yml            daily, ~15:45 IST - confirmation scan after close
  intraday_scan.yml       every 15 min during market hours - catches PRE_BOS2_READY/FRESH_REVERSAL/FRESH_BOS2 live
  backtest.yml            on-demand / monthly - historical edge report + both Excel exports
  tests.yml               runs pytest on every push
data/
  universe.csv        scan universe (bootstrap sample checked in; rebuilt by the workflow)
  nse_holidays.txt    NSE holiday calendar (update yearly)
  backtest_universe_sample.txt   80-symbol curated sample - optional, pass via --symbols-file for a quick/small backtest run (default is the full market-cap-filtered universe)
results/
  latest_scan.csv, state.json, backtest_*.csv/md/xlsx, sl_optimization_*.csv/xlsx
  (committed back by the workflows)
```

## 1. Dhan API setup — you're using Option B (static access token)

**Dhan is the primary data source, yfinance is the automatic fallback.**
Every scan tries Dhan first for every symbol (your own broker account, more
accurate/real-time NSE data). If Dhan fails - auth error, rate limit,
network issue, or just insufficient data for one symbol - the scanner
transparently falls back to yfinance **for that symbol only** and keeps
going, logging why. If Dhan can't even authenticate at all (e.g. token
expired), the whole run just uses yfinance for everything instead of
crashing. No extra config needed - this is `data_source: "dhan"`, the
default. Use `--data-source dhan_only` if you ever want to disable the
fallback (e.g. to debug Dhan itself), or `--data-source yfinance` to skip
Dhan entirely (already the default for `backtest`, since it doesn't need
your live broker quota).

**Your setup (Option B - simplest, but the token expires every 24h):**
1. `web.dhan.co → My Profile → Access DhanHQ APIs → Generate Access Token` (valid 24h).
2. Set repo secrets: `DHAN_CLIENT_ID`, `DHAN_ACCESS_TOKEN`. Do **not** set `DHAN_PIN`/`DHAN_TOTP_SECRET` - their presence would switch the scanner into Option A's auto-refresh mode instead.
3. **You must repeat step 1 and update the `DHAN_ACCESS_TOKEN` secret yourself every day** before market open, or Dhan calls will start failing with an auth error (401/DH-901) once the token expires - the scanner will silently keep working on the yfinance fallback, but you'll be missing Dhan's more accurate data until you refresh it.

**Daily refresh checklist:**
1. Log in to [web.dhan.co](https://web.dhan.co)
2. My Profile → Access DhanHQ APIs → Generate Access Token → copy it
3. Repo → Settings → Secrets and variables → Actions → `DHAN_ACCESS_TOKEN` → Update → paste → Save

**You don't have to remember this on your own** - the **"Check Dhan token"**
workflow (`.github/workflows/check_dhan_token.yml`) runs automatically every
weekday at 08:45 IST (30 min before market open), tries a real Dhan API call,
and sends you a Telegram alert if the token is missing/expired/invalid, with
the exact refresh steps above. It never fails the build - purely a reminder.
Trigger it manually anytime via Actions → "Check Dhan token" → Run workflow
to test it right after you've set up secrets.

If you ever want to switch to Option A instead (auto-refreshing via TOTP,
no more daily manual step): also set `DHAN_PIN` and `DHAN_TOTP_SECRET` (from
web.dhan.co → Access DhanHQ APIs → Setup TOTP) - the scanner checks for
`DHAN_TOTP_SECRET` first and will automatically switch modes.

Rate limits (per Dhan's docs): 5 data requests/sec, 100k/day — the client
throttles to 4/sec automatically, and the universe is capped by your market
cap filter to keep each run comfortably under this.

## 2. Telegram alerts

You mentioned you already have a bot. Add these as repo secrets:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID` (message your bot once, then hit
  `https://api.telegram.org/bot<token>/getUpdates` to read your chat id back)

Alerts fire for `FRESH_REVERSAL` and `PRE_BOS2_READY`, and only when **all**
of the following hold (as of 2026-08-08 — tightened after the universe grew
from 5 → 643 symbols and produced 79 alerts in one run, most of them stale
or low-quality):
- **Freshness**, defined per stage since only one of them is a one-bar event:
  - `FRESH_REVERSAL`: the reversal candle must be **today's** bar, not up to
    `recency_bars` (5) days old — no more "confirmed 5d ago" alerts arriving
    after the move is over.
  - `PRE_BOS2_READY`: this is a persisting coiled-state (can stay true for
    weeks while a stock sits under resistance), so "fresh" means the symbol
    just **entered** this stage this run (its previously tracked stage in
    `results/state.json` wasn't already `PRE_BOS2_READY`) — alerted once on
    entry, not once per day it continues to sit there.
- `quality_grade` is **A or B** (score ≥ 65) — C/D-grade setups (weak
  confluence, no real re-accumulation) are computed and still show up in
  `results/latest_scan.csv` for reference, but don't page you.
- (`FRESH_REVERSAL` only) it hasn't already been alerted for that exact
  reversal date — dedup keyed per-symbol in `results/state.json`, so a
  same-day re-run of the scan can't double-send.

`FRESH_BOS2` is still fully computed, scored, and written to the CSV/report
every run — it's just silent on Telegram. Rationale: it can stay true for up
to `recency_bars` days after the breakout, so it doesn't have as clean a
"same-day" signal as a reversal candle or a stage transition.

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
python -m smc_scanner.cli backtest --data-source yfinance   # defaults: all symbols >= min_market_cap_cr (ex-ETF), 5y history
```

Testing without Dhan credentials at all (yfinance fallback):
```bash
python -m smc_scanner.cli scan --data-source yfinance --mode eod
```

## Backtest: what it actually measures

By default `backtest` runs against **every symbol in `data/universe.csv`
that passes the market-cap filter** (`>= min_market_cap_cr`, currently
1000 cr, ETFs already excluded via `exclude_instrument_types`) - not a
curated sample. Override with `--symbols "A,B,C"` or `--symbols-file
path.txt`, and cap it for a quick/debug run with `--limit N`.

History depth defaults to **5 years** per symbol
(`config.backtest_history_years`), overridable per-run with `--years`, e.g.
`--years 3` or `--years 10`. This is independent of the live scanner's
history window (`daily_history_days`, ~2y) - a live scan only needs enough
bars to run its 26-week BOS1 gate + one active pattern chain, while a
backtest wants as many historical chains as possible for the stats to mean
something.

Symbols are fetched/processed in parallel threads (`--workers`, default 8)
since the default universe is now hundreds of symbols rather than a small
sample - a full run against yfinance can still take a while (I/O bound on
one HTTP call per symbol); reduce `--workers` if you hit Yahoo rate limits,
or use `--limit`/`--symbols-file` for a faster iteration loop while tuning.

`backtest.py` walks each symbol's **entire** fetched history once and
enumerates *every* retest → re-accumulation chain (not just the latest,
unlike the live scanner), classifying each into:

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

### Best stop-loss for that holding period

`scripts/optimize_stop_loss.py` sweeps 14 stop-loss placements (fixed % from
1-10%, ATR-multiple stops, and the structural retest-low stop already used
elsewhere) against every historical Reaccum-Reversal signal, for each
holding period from 3-10 days. Result: **the structural stop (the chain's
retest low) wins outright at every point in the 4-7 day window** - highest
average return (1.28-1.40%) at a moderate, technically-placed risk (~3.3%),
beating both tighter fixed stops (1-2%, which get stopped out 44-75% of the
time and collapse the win rate) and looser stops (5-10%/ATR, which risk
1.5-3x more capital for the same or lower return). This is already the
scanner's default - see `results/sl_optimization_summary.xlsx` for the full
sweep. Re-run with `python scripts/optimize_stop_loss.py` any time.

Run it (`python -m smc_scanner.cli backtest`) and read
`results/backtest_report.md` before trusting live alerts. **Re-tune
`Config` (breakout buffer, volume multipliers, proximity %, min re-accum
bars) against your own universe/holding-period before sizing real risk on
this.**

### Running it yourself in GitHub Actions

Actions tab → **"Backtest"** → *Run workflow* (optionally override `years`,
`workers`, or `limit` - leave `limit` blank for the full >= min-market-cap
universe, which is now the default). It installs dependencies, runs the
backtest via yfinance (no Dhan quota used), exports
`results/backtest_results.xlsx`, commits everything back to the repo, and
also uploads it as a downloadable workflow artifact. The job has a 300-minute
timeout since the default (full universe, 5y history) run is much larger
than the old 150-symbol sample.

### Excel workbook contents

**`results/backtest_results.xlsx`** (via `scripts/export_backtest_excel.py`)
is the only backtest workbook produced - **one file, one worksheet**, one
row per historical pattern instance that reached a confirmed fresh
reversal, de-duped and sorted by most recent Fresh Reversal Entry Date
first:

`Symbol | Quality Score | Quality Grade | Fresh Reversal Entry Date | Fresh Reversal Entry Price | Re-Accumulation Date | Retest Date | BOS1 Breakout Date | PRE_BOS2_READY (Fresh-Entry) Date | SL Level | Target Price`

- `Quality Score`/`Quality Grade` — the same 0-100 composite score & A/B/C/D
  grade described above, color-coded (green=A, blue=B, yellow=C, red=D).
- `Fresh Reversal Entry Date`/`Price` — the tactical reversal signal itself
  (first green candle closing back above the last confirmed swing-low
  candle's high).
- `Re-Accumulation Date` — the day right after the retest low, i.e. when the
  re-accumulation phase began.
- `Retest Date`, `BOS1 Breakout Date` — the earlier stages of the same
  chain, for full traceability back to the original breakout.
- `PRE_BOS2_READY (Fresh-Entry) Date` — the day this chain first coiled
  under resistance (re-accumulation minimum met + price near P1), if it
  ever did.
- `SL Level` — the chain's retest low (the same structural stop used
  everywhere else in this project).
- `Target Price` — `Fresh Reversal Entry Price + target_reward_risk *
  (Fresh Reversal Entry Price - SL Level)`, i.e. the same 1:1 reward:risk
  math as the live scanner's trade plans (`config.target_reward_risk`).

For raw per-chain data (every outcome including invalidated/timed-out
chains, forward returns at every horizon, the full BOS2/PreBOS2/Reversal
trade logs, and the stop-loss sweep), see the underlying CSVs in
`results/` (`backtest_all_chains.csv`, `backtest_bos2_trades.csv`,
`backtest_pre_bos2_trades.csv`, `backtest_reversal_trades.csv`,
`backtest_summary.csv`, `sl_optimization_*.csv`) and `backtest_report.md` -
`export_backtest_excel.py` intentionally distills all of that down to the
single sheet above as the one deliverable meant for day-to-day review.

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
