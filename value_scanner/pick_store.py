"""Persist active daily pick for odds follow-up."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from value_scanner.daily_pick import DailyPick

PICK_PATH = Path("data/current_pick.json")


def save_current_pick(pick: DailyPick, scan_date: date | None = None) -> Path:
    PICK_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(pick)
    payload["scan_date"] = (scan_date or date.today()).isoformat()
    PICK_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return PICK_PATH


def load_current_pick() -> DailyPick | None:
    from value_scanner.daily_pick import DailyPick

    if not PICK_PATH.exists():
        return None
    try:
        data = json.loads(PICK_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    return DailyPick(
        sport=data.get("sport", "football"),
        league=data.get("league", ""),
        home=data.get("home", ""),
        away=data.get("away", ""),
        kickoff_utc=data.get("kickoff_utc", ""),
        market=data.get("market", ""),
        selection=data.get("selection", ""),
        model_probability=float(data.get("model_probability", 0)),
        fair_odds=float(data.get("fair_odds", 0)),
        expected_goals=data.get("expected_goals"),
        novibet_path=data.get("novibet_path", ""),
    )
