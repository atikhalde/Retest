"""Guard used by the intraday workflow so it's a harmless no-op outside NSE market hours."""
import os
import sys
from datetime import datetime, time as dtime

try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    IST = None

HOLIDAY_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "nse_holidays.txt")


def load_holidays():
    try:
        with open(HOLIDAY_FILE) as f:
            return {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        return set()


def is_market_open(now=None) -> bool:
    now = now or (datetime.now(IST) if IST else datetime.now())
    if now.weekday() >= 5:  # Sat/Sun
        return False
    if now.strftime("%Y-%m-%d") in load_holidays():
        return False
    t = now.time()
    return dtime(9, 15) <= t <= dtime(15, 30)


if __name__ == "__main__":
    if is_market_open():
        print("open")
        sys.exit(0)
    else:
        print("closed")
        sys.exit(1)
