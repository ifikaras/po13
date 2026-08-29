"""Daily scan board — agent lists all matches; user sends Novibet odds."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from value_scanner.daily_pick import (
    MARKET_ROWS,
    NOVIBET_PATHS,
    _is_novibet_likely,
    _league_tier,
)
from value_scanner.models.poisson import calculate_probabilities, estimate_lambdas, fair_odds
from value_scanner.professional import MIN_ODDS
from value_scanner.scrapers.fotmob import fetch_fixtures_for_dates


@dataclass(frozen=True)
class ScanCandidate:
    index: int
    home: str
    away: str
    league: str
    kickoff_utc: str
    status: str  # ΕΠΟΜΕΝΟ | LIVE
    market: str
    selection: str
    model_probability: float
    fair_odds: float
    expected_goals: str
    novibet_path: str

    @property
    def match_label(self) -> str:
        return f"{self.home} vs {self.away}"


def _kickoff_status(kickoff_utc: str, now: datetime) -> str:
    try:
        kick = datetime.fromisoformat(kickoff_utc.replace("Z", "+00:00"))
        if kick < now:
            return "LIVE/ΤΕΛΟΣ"
        return "ΕΠΟΜΕΝΟ"
    except (ValueError, TypeError):
        return "ΕΠΟΜΕΝΟ"


def build_scan_board(scan_date: date | None = None, days: int = 1) -> list[ScanCandidate]:
    scan_date = scan_date or date.today()
    now = datetime.now(timezone.utc)
    fixtures = fetch_fixtures_for_dates(
        scan_date, days=days, major_only=True, form_limit=5
    )

    raw: list[tuple[float, ScanCandidate]] = []

    for f in fixtures:
        if not _is_novibet_likely(f.league, f.league_code):
            continue
        if f.home_form.matches_used < 3 or f.away_form.matches_used < 3:
            continue

        lh, la = estimate_lambdas(
            f.home_form.scored,
            f.home_form.conceded,
            f.away_form.scored,
            f.away_form.conceded,
        )
        probs = calculate_probabilities(lh, la)

        best_score = -1.0
        best_row: tuple[str, str, float, float] | None = None
        for market, selection, attr, _ in MARKET_ROWS:
            p = float(getattr(probs, attr))
            fair = fair_odds(p)
            if fair is None or fair < MIN_ODDS:
                continue
            score = p + _league_tier(f.league) * 0.005
            if score > best_score:
                best_score = score
                best_row = (market, selection, p, float(fair))

        if best_row is None:
            continue

        market, selection, p, fair = best_row
        status = _kickoff_status(f.kickoff_utc, now)
        candidate = ScanCandidate(
            index=0,
            home=f.home_name,
            away=f.away_name,
            league=f.league,
            kickoff_utc=f.kickoff_utc,
            status=status,
            market=market,
            selection=selection,
            model_probability=round(p * 100, 1),
            fair_odds=fair,
            expected_goals=f"{lh:.2f} - {la:.2f}",
            novibet_path=NOVIBET_PATHS.get((market, selection), f"{market} → {selection}"),
        )
        raw.append((best_score, candidate))

    raw.sort(key=lambda item: (0 if item[1].status == "ΕΠΟΜΕΝΟ" else 1, item[1].kickoff_utc))
    return [
        ScanCandidate(
            index=i,
            home=c.home,
            away=c.away,
            league=c.league,
            kickoff_utc=c.kickoff_utc,
            status=c.status,
            market=c.market,
            selection=c.selection,
            model_probability=c.model_probability,
            fair_odds=c.fair_odds,
            expected_goals=c.expected_goals,
            novibet_path=c.novibet_path,
        )
        for i, (_, c) in enumerate(raw, start=1)
    ]


def format_scan_board_greek(candidates: list[ScanCandidate], scan_date: date | None = None) -> str:
    scan_date = scan_date or date.today()
    upcoming = [c for c in candidates if c.status == "ΕΠΟΜΕΝΟ"]
    lines = [
        f"ΣΚΑΝ {scan_date.isoformat()} — {len(upcoming)} αγώνες (Novibet leagues)",
        "",
        "Ροή: εγώ σκανάρω → εσύ στέλνεις αποδόσεις Novibet → ΠΑΙΞΕ/SKIP",
        "Μορφή απάντησης: «3 BTTS Όχι 2.03» ή screenshot",
        "",
    ]
    for c in candidates:
        if c.status != "ΕΠΟΜΕΝΟ":
            continue
        try:
            kick = datetime.fromisoformat(c.kickoff_utc.replace("Z", "+00:00"))
            hour_gr = kick.astimezone(timezone.utc).strftime("%H:%M UTC")
        except ValueError:
            hour_gr = c.kickoff_utc[:16]
        lines.append(f"#{c.index} {c.home} — {c.away} ({c.league}) ~{hour_gr}")
        lines.append(f"   Τσέκαρε: {c.novibet_path}")
        lines.append(f"   Μοντέλο: {c.selection} fair ~{c.fair_odds:.2f} ({c.model_probability}%)")
        lines.append("")
    if not upcoming:
        lines.append("Δεν υπάρχουν επερχόμενα ματς — δοκίμασε αύριο.")
    return "\n".join(lines).strip()


def find_candidate_by_index(candidates: list[ScanCandidate], index: int) -> ScanCandidate | None:
    for c in candidates:
        if c.index == index:
            return c
    return None


def parse_user_odds_reply(text: str) -> tuple[int | None, float | None]:
    """Parse '3 2.03' or '3 BTTS No 2.03'."""
    import re

    parts = text.strip().replace(",", ".")
    m = re.match(r"^\s*#?(\d+)\s+(?:.*?\s+)?(\d+\.\d+)\s*$", parts, re.I)
    if m:
        return int(m.group(1)), float(m.group(2))
    return None, None


SCAN_BOARD_PATH = Path("data/scan_board.json")


def save_scan_board(candidates: list[ScanCandidate], scan_date: date | None = None) -> None:
    from dataclasses import asdict

    SCAN_BOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "scan_date": (scan_date or date.today()).isoformat(),
        "candidates": [asdict(c) for c in candidates],
    }
    SCAN_BOARD_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_scan_board() -> tuple[date | None, list[ScanCandidate]]:
    if not SCAN_BOARD_PATH.exists():
        return None, []
    try:
        data = json.loads(SCAN_BOARD_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, []
    scan_date = date.fromisoformat(data["scan_date"]) if data.get("scan_date") else None
    candidates = [ScanCandidate(**row) for row in data.get("candidates", [])]
    return scan_date, candidates


def get_or_build_today_board() -> list[ScanCandidate]:
    saved_date, saved = load_scan_board()
    if saved_date == date.today() and saved:
        return saved
    board = build_scan_board()
    save_scan_board(board)
    return board
