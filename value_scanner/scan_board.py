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
from value_scanner.market_anchor import multiplicative_devig
from value_scanner.models.poisson import calculate_probabilities, estimate_lambdas, fair_odds
from value_scanner.professional import MIN_ODDS
from value_scanner.scrapers.espn import fetch_espn_events, fetch_team_win_rate, league_config_for
from value_scanner.scrapers.fotmob import fetch_fixtures_for_dates
from value_scanner.scrapers.pinnacle import fetch_pinnapi_prematch
from value_scanner.sports_config import (
    MAX_PER_SPORT,
    SPORT_BASEBALL,
    SPORT_BASKETBALL,
    SPORT_EMOJI,
    SPORT_HOCKEY,
    SPORT_LABELS_GREEK,
    SPORT_TENNIS,
    TENNIS_LEAGUE_HINTS,
)


@dataclass(frozen=True)
class ScanCandidate:
    index: int
    sport: str
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


def _home_advantage_for(sport: str) -> float:
    from value_scanner.models import basketball as bb

    if sport == "basketball":
        return bb.HOME_COURT_BOOST
    if sport == "american_football":
        return 0.04
    if sport == "hockey":
        return 0.05
    if sport == "baseball":
        return 0.04
    return 0.05


def _two_way_probs(home_rate: float, away_rate: float, sport: str) -> tuple[float, float]:
    boost = _home_advantage_for(sport)
    home_p = max(home_rate, 0.15) + boost
    away_p = max(away_rate, 0.15)
    p_home = home_p / (home_p + away_p)
    return p_home, 1.0 - p_home


def _build_football_candidates(now: datetime, scan_date: date, days: int) -> list[tuple[float, ScanCandidate]]:
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
        raw.append(
            (
                best_score,
                ScanCandidate(
                    index=0,
                    sport="football",
                    home=f.home_name,
                    away=f.away_name,
                    league=f.league,
                    kickoff_utc=f.kickoff_utc,
                    status=_kickoff_status(f.kickoff_utc, now),
                    market=market,
                    selection=selection,
                    model_probability=round(p * 100, 1),
                    fair_odds=fair,
                    expected_goals=f"{lh:.2f} - {la:.2f}",
                    novibet_path=NOVIBET_PATHS.get((market, selection), f"{market} → {selection}"),
                ),
            )
        )
    return raw


def _build_espn_candidates(now: datetime) -> list[tuple[float, ScanCandidate]]:
    raw: list[tuple[float, ScanCandidate]] = []

    for event in fetch_espn_events():
        cfg = league_config_for(event)
        if cfg is None:
            continue

        home_rate = fetch_team_win_rate(event.sport_path, event.league_path, event.home_id)
        away_rate = fetch_team_win_rate(event.sport_path, event.league_path, event.away_id)
        if home_rate is None or away_rate is None:
            continue

        p_home, p_away = _two_way_probs(home_rate, away_rate, event.sport)
        best_side = ("Home Win", p_home) if p_home >= p_away else ("Away Win", p_away)
        selection, prob = best_side
        fair = fair_odds(prob)
        if fair is None or fair < MIN_ODDS:
            continue

        market = "Moneyline"
        score = prob + 0.01
        raw.append(
            (
                score,
                ScanCandidate(
                    index=0,
                    sport=event.sport,
                    home=event.home,
                    away=event.away,
                    league=event.league,
                    kickoff_utc=event.kickoff_utc,
                    status=_kickoff_status(event.kickoff_utc, now),
                    market=market,
                    selection=selection,
                    model_probability=round(prob * 100, 1),
                    fair_odds=float(fair),
                    expected_goals=f"win% {home_rate:.0%}-{away_rate:.0%}",
                    novibet_path=NOVIBET_PATHS.get((market, selection), f"Νικητής → {selection}"),
                ),
            )
        )
    return raw


def _is_major_tennis(league: str) -> bool:
    low = league.lower()
    return any(h in low for h in TENNIS_LEAGUE_HINTS)


def _build_tennis_candidates(now: datetime) -> list[tuple[float, ScanCandidate]]:
    raw: list[tuple[float, ScanCandidate]] = []
    lines = fetch_pinnapi_prematch(SPORT_TENNIS, "tennis")

    for line in lines:
        if not _is_major_tennis(line.league):
            continue
        board = line.moneyline_board()
        if not board or len(board) != 2:
            continue

        fair_probs = multiplicative_devig(board)
        if len(fair_probs) != 2:
            continue

        if fair_probs[0] >= fair_probs[1]:
            selection, prob = "Home Win", fair_probs[0]
        else:
            selection, prob = "Away Win", fair_probs[1]

        fair = fair_odds(prob)
        if fair is None or fair < MIN_ODDS:
            continue

        market = "Moneyline"
        raw.append(
            (
                prob,
                ScanCandidate(
                    index=0,
                    sport="tennis",
                    home=line.home,
                    away=line.away,
                    league=line.league,
                    kickoff_utc=line.kickoff,
                    status=_kickoff_status(line.kickoff, now),
                    market=market,
                    selection=selection,
                    model_probability=round(prob * 100, 1),
                    fair_odds=float(fair),
                    expected_goals=f"Pinnacle ML {board[0]:.2f}/{board[1]:.2f}",
                    novibet_path=NOVIBET_PATHS.get((market, selection), f"Νικητής → {selection}"),
                ),
            )
        )
    return raw


def _build_pinnacle_team_candidates(
    now: datetime,
    sport_key: str,
    sport_id: int,
) -> list[tuple[float, ScanCandidate]]:
    """NBA/NHL/MLB/NFL when ESPN has no games — use Pinnacle board."""
    raw: list[tuple[float, ScanCandidate]] = []
    lines = fetch_pinnapi_prematch(sport_id, sport_key)

    for line in lines:
        board = line.moneyline_board()
        if not board or len(board) != 2:
            continue
        fair_probs = multiplicative_devig(board)
        if len(fair_probs) != 2:
            continue

        if fair_probs[0] >= fair_probs[1]:
            selection, prob = "Home Win", fair_probs[0]
        else:
            selection, prob = "Away Win", fair_probs[1]

        fair = fair_odds(prob)
        if fair is None or fair < MIN_ODDS:
            continue

        market = "Moneyline"
        raw.append(
            (
                prob,
                ScanCandidate(
                    index=0,
                    sport=sport_key,
                    home=line.home,
                    away=line.away,
                    league=line.league,
                    kickoff_utc=line.kickoff,
                    status=_kickoff_status(line.kickoff, now),
                    market=market,
                    selection=selection,
                    model_probability=round(prob * 100, 1),
                    fair_odds=float(fair),
                    expected_goals=f"Pinnacle ML {board[0]:.2f}/{board[1]:.2f}",
                    novibet_path=NOVIBET_PATHS.get((market, selection), f"Νικητής → {selection}"),
                ),
            )
        )
    return raw


def _cap_per_sport(candidates: list[ScanCandidate], sport: str, limit: int) -> list[ScanCandidate]:
    sport_rows = [c for c in candidates if c.sport == sport and c.status == "ΕΠΟΜΕΝΟ"]
    other = [c for c in candidates if c.sport != sport]
    sport_rows.sort(key=lambda c: c.kickoff_utc)
    return other + sport_rows[:limit]


def build_scan_board(scan_date: date | None = None, days: int = 1) -> list[ScanCandidate]:
    scan_date = scan_date or date.today()
    now = datetime.now(timezone.utc)

    merged: list[tuple[float, ScanCandidate]] = []
    merged.extend(_build_football_candidates(now, scan_date, days))
    merged.extend(_build_espn_candidates(now))
    merged.extend(_build_tennis_candidates(now))

    from value_scanner.sports_config import SPORT_BASEBALL, SPORT_BASKETBALL, SPORT_HOCKEY

    espn_sports = {c.sport for c in [x[1] for x in merged if x[1].sport != "football"]}
    if "basketball" not in espn_sports:
        merged.extend(_build_pinnacle_team_candidates(now, "basketball", SPORT_BASKETBALL))
    if "hockey" not in espn_sports:
        merged.extend(_build_pinnacle_team_candidates(now, "hockey", SPORT_HOCKEY))
    if "baseball" not in espn_sports:
        merged.extend(_build_pinnacle_team_candidates(now, "baseball", SPORT_BASEBALL))
    if "american_football" not in espn_sports:
        merged.extend(_build_pinnacle_team_candidates(now, "american_football", SPORT_BASEBALL))

    merged.sort(key=lambda item: (0 if item[1].status == "ΕΠΟΜΕΝΟ" else 1, item[1].kickoff_utc))
    candidates = [c for _, c in merged]

    for sport in ("tennis", "basketball", "hockey", "baseball", "american_football"):
        candidates = _cap_per_sport(candidates, sport, MAX_PER_SPORT)

    candidates.sort(key=lambda c: (0 if c.status == "ΕΠΟΜΕΝΟ" else 1, c.kickoff_utc))
    return [
        ScanCandidate(
            index=i,
            sport=c.sport,
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
        for i, c in enumerate(candidates, start=1)
    ]


def format_scan_board_greek(candidates: list[ScanCandidate], scan_date: date | None = None) -> str:
    scan_date = scan_date or date.today()
    upcoming = [c for c in candidates if c.status == "ΕΠΟΜΕΝΟ"]

    sport_counts: dict[str, int] = {}
    for c in upcoming:
        sport_counts[c.sport] = sport_counts.get(c.sport, 0) + 1
    breakdown = ", ".join(
        f"{SPORT_LABELS_GREEK.get(s, s)} {n}"
        for s, n in sorted(sport_counts.items(), key=lambda x: -x[1])
    )

    lines = [
        f"ΣΚΑΝ {scan_date.isoformat()} — {len(upcoming)} αγώνες ({breakdown})",
        "",
        "Ροή: εγώ σκανάρω → εσύ στέλνεις αποδόσεις Novibet → ΠΑΙΞΕ/SKIP",
        "Μορφή: «#5 BTTS Όχι 2.03» ή screenshot",
        "",
    ]
    for c in candidates:
        if c.status != "ΕΠΟΜΕΝΟ":
            continue
        emoji = SPORT_EMOJI.get(c.sport, "•")
        sport_label = SPORT_LABELS_GREEK.get(c.sport, c.sport)
        try:
            kick = datetime.fromisoformat(c.kickoff_utc.replace("Z", "+00:00"))
            hour_gr = kick.strftime("%H:%M UTC")
        except ValueError:
            hour_gr = (c.kickoff_utc or "")[:16]
        lines.append(f"#{c.index} {emoji} {c.home} — {c.away} ({sport_label}: {c.league}) ~{hour_gr}")
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
        "board_version": BOARD_VERSION,
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
    candidates = []
    for row in data.get("candidates", []):
        row.setdefault("sport", "football")
        candidates.append(ScanCandidate(**row))
    return scan_date, candidates


BOARD_VERSION = 2


def get_or_build_today_board(force_rebuild: bool = False) -> list[ScanCandidate]:
    saved_date, saved = load_scan_board()
    if not force_rebuild and saved_date == date.today() and saved:
        try:
            data = json.loads(SCAN_BOARD_PATH.read_text(encoding="utf-8"))
            if data.get("board_version") == BOARD_VERSION:
                return saved
        except (json.JSONDecodeError, OSError):
            pass
    board = build_scan_board()
    save_scan_board(board)
    return board
