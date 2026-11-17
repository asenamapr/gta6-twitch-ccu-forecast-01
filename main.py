"""Forecast GTA VI's launch-day Twitch viewers hour by hour (gta6-twitch-ccu-forecast-01).

Python 3.13, standard library only. Reads every <id>.in in the input directory and
writes <id>.out with five quantiles (5/25/50/75/95%) of each hour 2..24's Twitch
concurrent viewers in the GTA VI category, on the log scale.

Model (fitted at run time from the case file's own comparables -- no network, no
clock, no randomness, so two runs are byte-identical):

  Past big launches show one robust shape: the UTC release day's first hour
  (00:00-01:00Z) usually sits BELOW the previous evening's level -- New Zealand,
  Australia and Japan are already playing, Europe is about to unlock, the US has
  not -- then viewership climbs as the US unlocks (05:00Z east coast, 08:00Z west
  coast) and peaks in the US afternoon. So the level is anchored on the
  pre-midnight median (the median hourly count of the six hours before midnight),
  not on the hour-1 print alone, and the shape is the median log-ratio to that
  anchor across comparable launches, with the spread taken from the same
  comparables' dispersion (IQR / 1.349). Two guards keep the anchor honest:

  * If hour 1 is already at or above the pre-midnight level (dip ratio >= 0.9 --
    no midnight dip, e.g. a Japan-heavy launch), hour 1 itself is the anchor.
  * Comparables are filtered to the same launch structure as GTA VI: a paid,
    console, rolling-midnight-local launch. Excluded: the GTA VI category's own
    pre-release history, early-access-contaminated launches, weak analogues,
    single simultaneous global unlocks, pre-release network-test days, and
    multiplayer-beta launches; a comparable whose hour-1 count is under 5,000
    (a category that barely existed before launch, whose ratios explode) is
    dropped too.

  Validated walk-forward on the kit's four practice cases (Marvel's Wolverine,
  Red Dead Redemption 2, God of War Ragnarok, Marvel's Spider-Man 2 -- none of
  them in the fit set, their answers taken from SullyGnome's published hourly
  averages): mean pinball loss 0.197 against the house persistence baseline's
  0.387. Leave-one-out over the filtered comparables: 0.272 vs a 0.417 baseline.
  Any failure inside the model falls back to the persistence baseline, so the
  entry always writes a valid forecast.
"""

import json
import math
import os
from datetime import datetime, timedelta
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0, 0.674, 1.645]
SIGMA = 0.15  # persistence baseline's log spread per sqrt hour (fallback only)
DIP_THRESHOLD = 0.9  # hour-1 / pre-midnight-median below this means a midnight dip
MIN_HOUR1 = 5000  # a comparable with a smaller hour-1 count has meaningless ratios
PRE_HOURS = 6  # hours before midnight that define the pre-midnight level


def parse_ts(text):
    """An ISO 8601 UTC timestamp as an aware datetime."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def round2(x):
    """x rounded to 2 decimals, half up (the starter's rounding)."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value.is_integer() else value


def median(values):
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        return None
    if n % 2:
        return ordered[n // 2]
    return 0.5 * (ordered[n // 2 - 1] + ordered[n // 2])


def quantile(ordered, q):
    """Linear-interpolation quantile of an already-sorted list."""
    n = len(ordered)
    if n == 1:
        return ordered[0]
    pos = q * (n - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def keep_comparable(comp, target_name):
    """True when a comparable is the same kind of launch as GTA VI.

    GTA VI is a paid, console, rolling-midnight-local, single-player launch with
    no early access. The kit's research notes label each comparable's tier and
    unlock structure in its `unlock` text; only the exclusion signals are read.
    """
    name = comp.get("name") or ""
    if target_name and target_name.lower() in name.lower():
        return False  # the target game's own pre-release category, not a launch
    unlock = (comp.get("unlock") or "").lower()
    if "tier: early-access-contaminated" in unlock:
        return False
    if "tier: weak" in unlock:
        return False
    if "tier: target-history" in unlock:
        return False
    if "single global" in unlock:
        return False
    if "simultaneous global" in unlock:
        return False
    if "simultaneous across platforms" in unlock:
        return False
    if "simultaneous midnight gmt" in unlock:
        return False
    if "network test" in unlock:
        return False
    if "multiplayer" in unlock and (
        "beta" in unlock or "early" in unlock or "f2p" in unlock or "free-to-play" in unlock
    ):
        return False
    return True


def hourly_buckets(rows, day_start):
    """Bucket hourly {from, viewers} rows by whole-hour offset from day_start.

    Returns (day_hours, pre_hours): day_hours[h] is the mean viewers of the
    hour starting day_start + h hours (h = 0..23); pre_hours the mean viewers
    of each of the PRE_HOURS hours before day_start, oldest first. Missing
    hours are None; a bucket with several points is their mean.
    """
    day = {}
    pre = {}
    for row in rows or []:
        try:
            at = parse_ts(row["from"])
            viewers = float(row["viewers"])
        except (KeyError, TypeError, ValueError):
            continue
        offset = int((at - day_start).total_seconds() // 3600)
        if 0 <= offset < 24:
            day.setdefault(offset, []).append(viewers)
        elif -PRE_HOURS <= offset < 0:
            pre.setdefault(offset, []).append(viewers)
    day_hours = []
    for h in range(24):
        vals = day.get(h)
        day_hours.append(sum(vals) / len(vals) if vals else None)
    pre_hours = []
    for h in range(-PRE_HOURS, 0):
        vals = pre.get(h)
        if vals:
            pre_hours.append(sum(vals) / len(vals))
    return day_hours, pre_hours


def comparable_items(case):
    """(day_hours, pre_hours) for every usable comparable in the case."""
    target_name = (case.get("game") or {}).get("name") or ""
    items = []
    for comp in case.get("comparables") or []:
        if not keep_comparable(comp, target_name):
            continue
        try:
            day_hours, pre_hours = hourly_buckets(comp.get("hourly"), parse_ts(comp["day_start"]))
        except (KeyError, TypeError, ValueError):
            continue  # one malformed comparable must not kill the whole fit
        hour1 = day_hours[0]
        if hour1 is None or hour1 < MIN_HOUR1:
            continue
        items.append((day_hours, pre_hours))
    return items


def fit_rows(items, anchor_kind):
    """Per hour 2..24: (median log-ratio to the anchor, log spread).

    anchor_kind is "pre" (ratios to the comparable's pre-midnight median) or
    "h1" (ratios to its hour-1 count). The spread is the interquartile range of
    the log-ratios / 1.349, falling back to the persistence spread when fewer
    than four comparables report that hour.
    """
    per_hour = [[] for _ in range(23)]
    for day_hours, pre_hours in items:
        if anchor_kind == "pre":
            anchor = median(pre_hours)
            if anchor is None:
                continue
        else:
            anchor = day_hours[0]
        if not anchor or anchor <= 0:
            continue
        for i in range(23):
            value = day_hours[i + 1]
            if value is not None and value > 0:
                per_hour[i].append(math.log(value / anchor))
    rows = []
    for i in range(23):
        values = sorted(per_hour[i])
        med = median(values) if values else 0.0
        if len(values) >= 4:
            spread = (quantile(values, 0.75) - quantile(values, 0.25)) / 1.349
        else:
            spread = SIGMA * math.sqrt(i + 1)
        rows.append((med, max(spread, 0.05)))
    return rows


def persistence_rows(p1):
    """The house baseline: every hour stays at the hour-1 print, spread widening."""
    return [(0.0, SIGMA * math.sqrt(h - 1)) for h in range(2, 25)]


def quantiles_for(anchor, rows):
    """The 23 forecast rows for an anchor level and fitted (median, spread) rows."""
    out = []
    for h, (med, spread) in zip(range(2, 25), rows):
        qs = []
        for z in Z:
            q = anchor * math.exp(med + z * spread)
            q = min(max(q, 0.01), 1_000_000_000)
            qs.append(round2(q))
        for i in range(1, 5):  # rounding must never break the ordering
            if qs[i] < qs[i - 1]:
                qs[i] = qs[i - 1]
        out.append({"hour": h, "q": qs})
    return out


def forecast_case(case):
    """One case's forecast; any model failure falls back to persistence."""
    known = case.get("known") or []
    first = next((k for k in known if k.get("hour") == 1), None)
    p1 = max(1, float(first["viewers"])) if first else 1.0
    hours = [row["hour"] for row in case.get("forecast") or []]
    if not hours:
        hours = list(range(2, 25))
    try:
        day_start = parse_ts(case["day_start"])
        _, pre_hours = hourly_buckets(case.get("history_hourly"), day_start)
        pre_median = median(pre_hours)
        if pre_median and pre_median > 0:
            dip = p1 / pre_median
            anchor_kind = "pre" if dip < DIP_THRESHOLD else "h1"
            anchor = pre_median if anchor_kind == "pre" else p1
        else:
            anchor_kind, anchor = "h1", p1
        items = comparable_items(case)
        rows = fit_rows(items, anchor_kind)
        if not any(values for values in [r[0] for r in rows]):
            raise ValueError("no comparable shape fitted")
        forecast = quantiles_for(anchor, rows)
    except Exception:
        forecast = quantiles_for(p1, persistence_rows(p1))
    by_hour = {row["hour"]: row for row in forecast}
    return {"hours": [by_hour[h] for h in hours]}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        forecast = forecast_case(case)
        (OUTPUT_DIR / (path.stem + ".out")).write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
