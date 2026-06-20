"""
Persist weekly snapshots to a JSON log so we can compute week-over-week % change.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

HISTORY_FILE = Path(os.environ.get("HISTORY_FILE", "data/history.json"))


def _load() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    with HISTORY_FILE.open() as f:
        return json.load(f)


def _save(records: list[dict]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("w") as f:
        json.dump(records, f, indent=2)


def save_snapshot(metrics: dict) -> None:
    records = _load()
    records.append(metrics)
    _save(records)


def last_snapshot() -> dict | None:
    records = _load()
    if len(records) < 2:
        return None
    return records[-2]  # second-to-last = previous week


def pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100, 1)
