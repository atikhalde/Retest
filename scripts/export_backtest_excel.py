"""
Builds the ONE backtest deliverable: results/backtest_results.xlsx
(single file, single worksheet).

Columns, in this exact order:
    Symbol, Quality Score, Quality Grade, Fresh Reversal Entry Date,
    Fresh Reversal Entry Price, Re-Accumulation Date, Retest Date,
    BOS1 Breakout Date, PRE_BOS2_READY (Fresh-Entry) Date, SL Level,
    Target Price

One row per historical pattern instance that reached a confirmed "fresh
reversal" (the first green candle closing back above the last confirmed
swing-low candle's high inside the re-accumulation window) - that's the
signal SL Level/Target Price are computed against:
    SL Level      = the chain's retest low (the structural stop used
                    everywhere else in this project)
    Target Price  = Fresh Reversal Entry Price + TARGET_REWARD_RISK *
                    (Fresh Reversal Entry Price - SL Level), i.e. the same
                    1:1 reward:risk math as scanner.py's live trade plans
                    (see config.target_reward_risk)

De-duped by (Symbol, Fresh Reversal Entry Date) and sorted by that date,
most recent first.
"""
import os

import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

# Must match config.py's Config.target_reward_risk (kept as a local constant
# since this script intentionally has no import-time dependency on the
# smc_scanner package / PYTHONPATH being set - see other scripts/ files).
TARGET_REWARD_RISK = 1.0

HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)

QUALITY_FILL = {
    "A": "C6EFCE",  # green
    "B": "DDEBF7",  # light blue
    "C": "FFEB9C",  # yellow
    "D": "FFC7CE",  # red
}

FINAL_COLUMN_ORDER = [
    "Symbol", "Quality Score", "Quality Grade", "Fresh Reversal Entry Date",
    "Fresh Reversal Entry Price", "Re-Accumulation Date", "Retest Date",
    "BOS1 Breakout Date", "PRE_BOS2_READY (Fresh-Entry) Date", "SL Level",
    "Target Price",
]

DATE_COLS = [
    "Fresh Reversal Entry Date", "Re-Accumulation Date", "Retest Date",
    "BOS1 Breakout Date", "PRE_BOS2_READY (Fresh-Entry) Date",
]


def build_workbook(results_dir=RESULTS_DIR, out_path=None) -> str:
    out_path = out_path or os.path.join(results_dir, "backtest_results.xlsx")

    all_chains = pd.read_csv(
        os.path.join(results_dir, "backtest_all_chains.csv"),
        parse_dates=["bos1_date", "retest_date", "reaccumulation_start_date",
                     "reaccum_reversal_date", "pre_bos2_ready_date"],
    )

    # only keep pattern instances that actually reached a fresh reversal -
    # that's what Fresh Reversal Entry Date/Price and the derived SL
    # Level/Target Price are computed against
    df = all_chains[all_chains["reaccum_reversal_date"].notna()].copy()

    df["SL Level"] = df["retest_price"]
    df["Target Price"] = (
        df["reaccum_reversal_price"]
        + TARGET_REWARD_RISK * (df["reaccum_reversal_price"] - df["retest_price"])
    ).round(2)

    out = pd.DataFrame({
        "Symbol": df["symbol"],
        "Quality Score": df["quality_score"],
        "Quality Grade": df["quality_grade"],
        "Fresh Reversal Entry Date": df["reaccum_reversal_date"],
        "Fresh Reversal Entry Price": df["reaccum_reversal_price"],
        "Re-Accumulation Date": df["reaccumulation_start_date"],
        "Retest Date": df["retest_date"],
        "BOS1 Breakout Date": df["bos1_date"],
        "PRE_BOS2_READY (Fresh-Entry) Date": df["pre_bos2_ready_date"],
        "SL Level": df["SL Level"],
        "Target Price": df["Target Price"],
    })[FINAL_COLUMN_ORDER]

    # de-dupe: the same (symbol, reversal date) can appear more than once
    # when multiple candidate base levels produce overlapping chains
    out = out.drop_duplicates(subset=["Symbol", "Fresh Reversal Entry Date"], keep="first")

    # sorted by Fresh Reversal Entry Date (most recent tactical entries first)
    out = out.sort_values("Fresh Reversal Entry Date", ascending=False, na_position="last").reset_index(drop=True)

    for col in DATE_COLS:
        out[col] = pd.to_datetime(out[col]).dt.strftime("%Y-%m-%d").replace("NaT", "")

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        out.to_excel(writer, sheet_name="Backtest Results", index=False)

    from openpyxl import load_workbook
    wb = load_workbook(out_path)
    ws = wb["Backtest Results"]
    ws.freeze_panes = "A2"

    for col_idx, col in enumerate(out.columns, start=1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")
        max_len = max([len(str(col))] + [len(str(v)) for v in out[col].astype(str).values[:1000]])
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max(max_len + 2, 12), 34)

    quality_col_idx = out.columns.get_loc("Quality Grade") + 1
    for row_idx in range(2, len(out) + 2):
        val = ws.cell(row=row_idx, column=quality_col_idx).value
        letter = str(val)[0] if val else None
        fill_hex = QUALITY_FILL.get(letter)
        if fill_hex:
            ws.cell(row=row_idx, column=quality_col_idx).fill = PatternFill(
                start_color=fill_hex, end_color=fill_hex, fill_type="solid")

    ref = f"A1:{get_column_letter(len(out.columns))}{len(out) + 1}"
    tbl = Table(displayName="BacktestResults", ref=ref)
    tbl.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(tbl)

    wb.save(out_path)
    print(f"Wrote {out_path}  ({len(out)} rows, {len(out.columns)} columns, 1 sheet)")
    return out_path


if __name__ == "__main__":
    build_workbook()
