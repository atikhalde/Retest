"""
Standalone/ad-hoc regenerator for results/backtest_results.xlsx from an
existing results/backtest_all_chains.csv (e.g. if you want to rebuild the
workbook without re-running the whole backtest).

The normal `python -m smc_scanner.cli backtest` path builds this workbook
directly from memory now and does NOT need this script or any intermediate
CSV - see smc_scanner.backtest.build_results_table /
smc_scanner.backtest.write_results_excel, which this script just calls too.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from smc_scanner.backtest import build_results_table, write_results_excel  # noqa: E402
from smc_scanner.config import Config  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def build_workbook(results_dir=RESULTS_DIR, out_path=None) -> str:
    out_path = out_path or os.path.join(results_dir, "backtest_results.xlsx")
    all_chains = pd.read_csv(os.path.join(results_dir, "backtest_all_chains.csv"))
    out = build_results_table(all_chains, cfg=Config())
    write_results_excel(out, out_path)
    print(f"Wrote {out_path}  ({len(out)} rows, {len(out.columns)} columns, 1 sheet)")
    return out_path


if __name__ == "__main__":
    build_workbook()
