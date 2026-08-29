"""Agent-run daily pick — user never touches code or config."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from value_scanner.calculator import value_percentage
from value_scanner.models.basketball import away_win_probability, home_win_probability
from value_scanner.models.poisson import calculate_probabilities, estimate_lambdas, fair_odds
from value_scanner.bankroll import load_bankroll
from value_scanner.pick_store import get_or_create_today_pick, load_current_pick, save_current_pick
from value_scanner.professional import MIN_ODDS, pick_preference_bonus, required_edge_pct
from value_scanner.scrapers.espn import ESPN_SPORTS, EspnEvent, fetch_espn_events, fetch_team_win_rate
from value_scanner.scrapers.fotmob import fetch_fixtures_for_dates

# Leagues typically listed on Novibet Greece (football focus).
NOVIBET_COUNTRY_CODES = {"ENG", "ESP", "GER", "ITA", "FRA", "NED", "POR", "GRE", "SCO", "BEL", "INT", "USA"}
NOVIBET_LEAGUE_HINTS = (
    "premier league",
    "laliga",
    "bundesliga",
    "serie a",
    "ligue 1",
    "eredivisie",
    "liga portugal",
    "super league 1",
    "championship",
    "champions league",
    "europa league",
    "conference league",
    "nba",
    "euroleague",
    "copa",
    "mls",
)

EXCLUDE_LEAGUE_HINTS = (
    "egypt",
    "ukraine",
    "belarus",
    "tanzania",
    "northern super",
    "wales cymru",
    "premier league canada",
)


@dataclass(frozen=True)
class DailyPick:
    sport: str
    league: str
    home: str
    away: str
    kickoff_utc: str
    market: str
    selection: str
    model_probability: float
    fair_odds: float
    expected_goals: str | None
    novibet_path: str

    def summary_greek(self) -> str:
        sport_label = {
            "football": "Ποδόσφαιρο",
            "basketball": "Μπάσκετ",
        }.get(self.sport, self.sport)
        return (
            f"{sport_label} — {self.league}\n"
            f"Αγώνας: {self.home} vs {self.away}\n"
            f"Market: {self.market} → {self.selection}\n"
            f"Fair odds (μοντέλο): {self.fair_odds:.2f} ({self.model_probability:.1f}%)\n"
            f"Novibet: {self.novibet_path}\n"
            f"Ώρα (UTC): {self.kickoff_utc}"
        )


@dataclass(frozen=True)
class OddsVerdict:
    novibet_odds: float
    value_pct: float
    should_play: bool
    reason: str
    anchored_probability: float | None = None
    model_probability: float | None = None
    anchor_note: str = ""


MARKET_ROWS = [
    ("Over/Under", "Over 2.5", "over_25", "over_25"),
    ("Over/Under", "Under 2.5", "under_25", "under_25"),
    ("BTTS", "Yes", "btts_yes", "btts_yes"),
    ("BTTS", "No", "btts_no", "btts_no"),
    ("1X2", "Home Win", "home_win", "home_win"),
    ("1X2", "Away Win", "away_win", "away_win"),
    ("Double Chance", "1X", "dc_1x", "dc_1x"),
    ("Double Chance", "X2", "dc_x2", "dc_x2"),
]

NOVIBET_PATHS = {
    ("BTTS", "Yes"): "Και οι δύο ομάδες να σκοράρουν → Ναι",
    ("BTTS", "No"): "Και οι δύο ομάδες να σκοράρουν → Όχι",
    ("Over/Under", "Over 2.5"): "Σύνολο γκολ → Over 2.5",
    ("Over/Under", "Under 2.5"): "Σύνολο γκολ → Under 2.5",
    ("1X2", "Home Win"): "Τελικό αποτέλεσμα → 1 (εντός)",
    ("1X2", "Away Win"): "Τελικό αποτέλεσμα → 2 (εκτός)",
    ("Double Chance", "1X"): "Διπλή ευκαιρία → 1X",
    ("Double Chance", "X2"): "Διπλή ευκαιρία → X2",
    ("Moneyline", "Home Win"): "Νικητής → Εντός",
    ("Moneyline", "Away Win"): "Νικητής → Εκτός",
}

ESPN_LEAGUE_PATH = {name: (sport, league) for sport, league, name in ESPN_SPORTS}


def _is_novibet_likely(league: str, league_code: str) -> bool:
    low = league.lower()
    if any(ex in low for ex in EXCLUDE_LEAGUE_HINTS):
        return False

    strict_pairs = [
        ("ENG", "premier league"),
        ("ESP", "laliga"),
        ("GER", "bundesliga"),
        ("ITA", "serie a"),
        ("FRA", "ligue 1"),
        ("NED", "eredivisie"),
        ("POR", "liga portugal"),
        ("GRE", "super league"),
    ]
    for code, hint in strict_pairs:
        if league_code == code and hint in low:
            return True

    if league_code == "INT" and any(x in low for x in ("champions", "europa", "conference")):
        return True

    if league_code == "ENG" and "championship" in low:
        return True

    return False


def _league_tier(league: str) -> int:
    low = league.lower()
    if "2. bundesliga" in low or "2. laliga" in low or "serie b" in low:
        return 3
    if "premier league" in low and "championship" not in low and "scotland" not in low:
        return 10
    if "champions league" in low:
        return 9
    if low == "bundesliga" or ( "bundesliga" in low and "2." not in low ):
        return 8
    if "laliga" in low and "2." not in low:
        return 8
    if "serie a" in low and "serie b" not in low:
        return 8
    if "ligue 1" in low and "ligue 2" not in low:
        return 7
    if "eredivisie" in low:
        return 7
    if "super league 1" in low or "greek" in low:
        return 7
    if "europa league" in low or "conference league" in low:
        return 6
    if "championship" in low:
        return 5
    if "liga portugal" in low:
        return 4
    return 0


def _pick_score(model_prob: float, league: str, fair: float) -> float:
    return model_prob + _league_tier(league) * 0.005 + pick_preference_bonus(fair)


def _find_football_pick(
    scan_date: date,
    min_odds: float,
    min_form_matches: int,
    scan_days: int,
) -> tuple[float, DailyPick] | None:
    fixtures = fetch_fixtures_for_dates(
        scan_date,
        days=scan_days,
        major_only=True,
        form_limit=5,
    )

    best: tuple[float, DailyPick] | None = None

    for enriched in fixtures:
        if not _is_novibet_likely(enriched.league, enriched.league_code):
            continue
        if enriched.home_form.matches_used < min_form_matches:
            continue
        if enriched.away_form.matches_used < min_form_matches:
            continue

        lambda_home, lambda_away = estimate_lambdas(
            enriched.home_form.scored,
            enriched.home_form.conceded,
            enriched.away_form.scored,
            enriched.away_form.conceded,
        )
        probabilities = calculate_probabilities(lambda_home, lambda_away)

        for market, selection, prob_attr, _ in MARKET_ROWS:
            model_prob = float(getattr(probabilities, prob_attr))
            fair = fair_odds(model_prob)
            if fair is None or fair < min_odds:
                continue

            pick = DailyPick(
                sport="football",
                league=enriched.league,
                home=enriched.home_name,
                away=enriched.away_name,
                kickoff_utc=enriched.kickoff_utc,
                market=market,
                selection=selection,
                model_probability=round(model_prob * 100, 1),
                fair_odds=float(fair),
                expected_goals=f"{lambda_home:.2f} - {lambda_away:.2f}",
                novibet_path=NOVIBET_PATHS.get((market, selection), f"{market} / {selection}"),
            )

            score = _pick_score(model_prob, enriched.league, float(fair))
            if best is None or score > best[0]:
                best = (score, pick)

    return best


def _find_basketball_pick(
    scan_date: date,
    min_odds: float,
) -> tuple[float, DailyPick] | None:
    best: tuple[float, DailyPick] | None = None

    for event in fetch_espn_events(scan_date):
        paths = ESPN_LEAGUE_PATH.get(event.league)
        if not paths:
            continue
        sport_path, league_path = paths

        home_rate = fetch_team_win_rate(sport_path, league_path, event.home_id)
        away_rate = fetch_team_win_rate(sport_path, league_path, event.away_id)
        if home_rate is None or away_rate is None:
            continue

        for selection, prob_fn in [
            ("Home Win", home_win_probability),
            ("Away Win", away_win_probability),
        ]:
            model_prob = float(prob_fn(home_rate, away_rate))
            fair = fair_odds(model_prob)
            if fair is None or fair < min_odds:
                continue

            market = "Moneyline"
            pick = DailyPick(
                sport="basketball",
                league=event.league,
                home=event.home,
                away=event.away,
                kickoff_utc=event.kickoff_utc,
                market=market,
                selection=selection,
                model_probability=round(model_prob * 100, 1),
                fair_odds=float(fair),
                expected_goals=f"win% {home_rate:.0%}-{away_rate:.0%}",
                novibet_path=NOVIBET_PATHS.get((market, selection), f"Νικητής → {selection}"),
            )
            score = model_prob + 0.02  # slight bias to include basketball when strong
            if best is None or score > best[0]:
                best = (score, pick)

    return best


def find_daily_pick(
    scan_date: date | None = None,
    min_odds: float = MIN_ODDS,
    min_form_matches: int = 3,
    scan_days: int = 2,
    persist: bool = True,
) -> DailyPick | None:
    scan_date = scan_date or date.today()

    candidates: list[tuple[float, DailyPick]] = []
    football = _find_football_pick(scan_date, min_odds, min_form_matches, scan_days)
    if football:
        candidates.append(football)

    basketball = _find_basketball_pick(scan_date, min_odds)
    if basketball:
        candidates.append(basketball)

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    pick = candidates[0][1]

    if persist:
        save_current_pick(pick, scan_date)

    return pick


def get_active_pick() -> DailyPick | None:
    return load_current_pick()


def get_today_pick() -> DailyPick | None:
    return get_or_create_today_pick(find_daily_pick)


def evaluate_novibet_odds(
    pick: DailyPick,
    novibet_odds: float,
    min_value_pct: float | None = None,
    min_odds: float = MIN_ODDS,
    market_probability: float | None = None,
    market_odds_full: list[float] | None = None,
    selection_index: int = 0,
) -> OddsVerdict:
    from value_scanner.market_anchor import evaluate_anchored_edge

    model_prob = pick.model_probability / 100.0
    raw_value = value_percentage(model_prob, novibet_odds)

    if novibet_odds < min_odds:
        return OddsVerdict(
            novibet_odds=novibet_odds,
            value_pct=round(raw_value, 1),
            should_play=False,
            reason=f"SKIP — απόδοση {novibet_odds} κάτω από {min_odds} (βαρύ φαβορί, αδύναμο edge).",
            model_probability=pick.model_probability,
        )

    should_play, value_pct, anchor, reason = evaluate_anchored_edge(
        model_prob,
        novibet_odds,
        market=pick.market,
        market_probability=market_probability,
        market_odds_full=market_odds_full,
        selection_index=selection_index,
        min_edge_pct=min_value_pct,
    )

    return OddsVerdict(
        novibet_odds=novibet_odds,
        value_pct=value_pct,
        should_play=should_play,
        reason=reason,
        anchored_probability=round(anchor.anchored_probability * 100, 1),
        model_probability=pick.model_probability,
        anchor_note=anchor.note,
    )


def parse_odds_from_text(text: str) -> float | None:
    import re

    match = re.search(r"(\d+[.,]\d+)", text.replace(",", "."))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def handle_user_message(text: str) -> str:
    """Agent entry point: odds number → verdict, otherwise today's pick."""
    low = text.strip().lower()
    if any(k in low for k in ("καβα", "καβά", "bankroll", "στοιχηματα", "στοιχήματα")):
        return load_bankroll().summary_greek()

    odds = parse_odds_from_text(text.strip())
    if odds is not None and len(text.strip()) < 20:
        pick = get_today_pick()
        if pick is None:
            return "Δεν υπάρχει ενεργό pick. Ρώτα «σημερινό pick»."
        verdict = evaluate_novibet_odds(pick, odds)
        lines = [
            f"{pick.home} vs {pick.away}",
            f"{pick.market} / {pick.selection}",
            verdict.reason,
            f"Anchored value: {verdict.value_pct:+.1f}%",
        ]
        if verdict.anchored_probability is not None:
            lines.append(
                f"Μοντέλο {verdict.model_probability}% → anchored {verdict.anchored_probability}%"
            )
        if verdict.anchor_note:
            lines.append(verdict.anchor_note)
        return "\n".join(lines)

    pick = get_today_pick()
    if pick is None:
        return "Δεν βρέθηκε pick σήμερα. Δοκίμασε αύριο."
    return (
        f"ΣΗΜΕΡΙΝΟ PICK\n\n{pick.summary_greek()}\n\n"
        f"Τσέκαρε Novibet και στείλε μου την απόδοση (π.χ. 1.80).\n"
        f"Παίξε αν ≥ {pick.fair_odds:.2f} και value ≥ +3%."
    )
