"""
Composite setup-quality scoring.

Combines everything the scanner already knows about a pattern instance into
one 0-100 score and an A/B/C/D grade, so signals aren't all treated equally -
a FRESH_REVERSAL with 9/9 confluence and a single clean pivot low is a very
different bet than one with 3/9 confluence and four choppy reversals.

Components (100 pts total):
    40 pts - confluence score (EMA/RSI/MACD/volume/trend/candle/52w-high),
             scaled from the existing 0-9 confluence_score
    20 pts - structure cleanliness: fewer confirmed pivot-low reversals in
             the re-accumulation window = a cleaner, less choppy base
             (1 reversal = cleanest, 5+ = a messy, repeatedly-tested range)
    15 pts - volatility contraction: has the range tightened up (coiled)
             ahead of the move, vs. still wide/undecided
    15 pts - re-accumulation duration fit: a base of ~10-40 trading days is
             the sweet spot (long enough to be real, not so long it's gone
             stale); too short or too long score lower
    10 pts - stage maturity: how far along/confirmed the setup is right now
             (FRESH_BOS2 > FRESH_REVERSAL > PRE_BOS2_READY > BASING > IN_RETEST)

Grades:
    A  (80-100)  High-Quality Setup
    B  (65-79)   Good Setup
    C  (50-64)   Moderate / Watch
    D  (<50)     Weak / Low-Quality
"""
import math

STAGE_MATURITY_PTS = {
    "FRESH_BOS2": 10,
    "FRESH_REVERSAL": 9,
    "PRE_BOS2_READY": 7,
    "BASING": 4,
    "IN_RETEST": 2,
    "STALE_BOS2": 1,
}


def _confluence_points(confluence_raw, confluence_max=9) -> float:
    if confluence_raw is None or confluence_max in (None, 0):
        return 20.0  # neutral default if unknown
    return round((confluence_raw / confluence_max) * 40, 1)


def _structure_points(num_reversals) -> float:
    if num_reversals is None or (isinstance(num_reversals, float) and math.isnan(num_reversals)):
        return 10.0  # neutral - no reversal formed yet
    n = int(num_reversals)
    if n <= 0:
        return 10.0
    return {1: 20.0, 2: 16.0, 3: 12.0, 4: 8.0}.get(n, 4.0)


def _volatility_points(volatility_contracted) -> float:
    if volatility_contracted is None:
        return 10.0  # neutral/unknown
    return 15.0 if volatility_contracted else 7.0


def _duration_points(reaccum_bars) -> float:
    if reaccum_bars is None or (isinstance(reaccum_bars, float) and math.isnan(reaccum_bars)):
        return 8.0  # neutral - not yet in re-accumulation
    b = int(reaccum_bars)
    if b < 10:
        return 8.0
    if b <= 40:
        return 15.0
    if b <= 70:
        return 10.0
    return 5.0


def _stage_points(stage) -> float:
    return float(STAGE_MATURITY_PTS.get(stage, 3))


def grade_for_score(score: float) -> str:
    if score >= 80:
        return "A - High-Quality Setup"
    if score >= 65:
        return "B - Good Setup"
    if score >= 50:
        return "C - Moderate / Watch"
    return "D - Weak / Low-Quality"


def compute_quality_score(stage, confluence_raw=None, confluence_max=9,
                           num_reversals=None, volatility_contracted=None,
                           reaccum_bars=None) -> dict:
    """Returns {'quality_score': float 0-100, 'quality_grade': str, breakdown...}."""
    p_confluence = _confluence_points(confluence_raw, confluence_max)
    p_structure = _structure_points(num_reversals)
    p_volatility = _volatility_points(volatility_contracted)
    p_duration = _duration_points(reaccum_bars)
    p_stage = _stage_points(stage)

    total = round(p_confluence + p_structure + p_volatility + p_duration + p_stage, 1)
    return {
        "quality_score": total,
        "quality_grade": grade_for_score(total),
        "score_confluence": p_confluence,
        "score_structure": p_structure,
        "score_volatility": p_volatility,
        "score_duration": p_duration,
        "score_stage": p_stage,
    }
