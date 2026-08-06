"""
Builds ONE simple worksheet from the backtest CSVs: results/backtest_simple.xlsx

6 columns, in the order things actually happen:
    Symbol, BOS1 Breakout Date, Retest Date, Re-Accumulation Date,
    Reversal Date, Setup Quality

Setup Quality is a composite A/B/C/D grade combining confluence (trend/
momentum/volume), how clean the re-accumulation structure was (fewer
confirmed pivot-low reversals = cleaner), volatility contraction, and
re-accumulation duration fit - see src/smc_scanner/scoring.py.

One row per pattern instance found, sorted by Reversal Date (most recent
first). For every other detail (prices, outcome, entry/returns, full
multi-sheet breakdown, score component breakdown), see backtest_results.xlsx
instead.
"""
import os

import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)

COLUMN_RENAME = {
    "symbol": "Symbol",
    "bos1_date": "BOS1 Breakout Date",
    "retest_date": "Retest Date",
    "reaccumulation_start_date": "Re-Accumulation Date",
    "reaccum_reversal_date": "Reversal Date",
    "quality_grade": "Setup Quality",
}

FINAL_COLUMN_ORDER = [
    "Symbol", "BOS1 Breakout Date", "Retest Date", "Re-Accumulation Date", "Reversal Date",
    "Setup Quality",
]

QUALITY_FILL = {
    "A": "C6EFCE",  # green
    "B": "DDEBF7",  # light blue
    "C": "FFEB9C",  # yellow
    "D": "FFC7CE",  # red
}

DATE_COLS = ["BOS1 Breakout Date", "Retest Date", "Re-Accumulation Date", "Reversal Date"]


def build_simple_workbook(results_dir=RESULTS_DIR, out_path=None) -> str:
    out_path = out_path or os.path.join(results_dir, "backtest_simple.xlsx")

    all_chains = pd.read_csv(os.path.join(results_dir, "backtest_all_chains.csv"),
                              parse_dates=["bos1_date", "retest_date",
                                           "reaccumulation_start_date", "reaccum_reversal_date"])

    merged = all_chains.rename(columns=COLUMN_RENAME)
    for col in FINAL_COLUMN_ORDER:
        if col not in merged.columns:
            merged[col] = None
    out = merged[FINAL_COLUMN_ORDER].copy()

    # only keep rows that actually had a reversal signal
    out = out[out["Reversal Date"].notna()].copy()

    # de-dupe: the same (symbol, reversal date) can appear more than once
    # when multiple candidate base levels produce overlapping chains
    out = out.drop_duplicates(subset=["Symbol", "Reversal Date"], keep="first")

    # sorted by Reversal Date (most recent tactical entries first)
    out = out.sort_values("Reversal Date", ascending=False, na_position="last").reset_index(drop=True)

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
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max(max_len + 2, 12), 30)

    quality_col_idx = out.columns.get_loc("Setup Quality") + 1
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
    print(f"Wrote {out_path}  ({len(out)} rows, {len(out.columns)} columns)")
    return out_path


if __name__ == "__main__":
    build_simple_workbook()
