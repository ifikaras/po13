"""External tools the agent can call — the only way it touches the world."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Callable

from value_scanner.bankroll import add_bet, load_bankroll, settle_all_by_match, settle_bet
from value_scanner.daily_pick import (
    DailyPick,
    evaluate_novibet_odds,
    find_daily_pick,
    get_today_pick,
    parse_odds_from_text,
)
from value_scanner.scan_board import (
    find_candidate_by_index,
    format_scan_board_greek,
    get_or_build_today_board,
    parse_user_odds_reply,
)


def _ok(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def tool_scan_matches(force_rebuild: bool = False) -> str:
    """Scan upcoming Novibet-likely matches and return the numbered Greek board."""
    board = get_or_build_today_board(force_rebuild=force_rebuild)
    return format_scan_board_greek(board)


def tool_get_daily_pick(persist: bool = True) -> str:
    """Return today's single best model pick (or build one)."""
    pick = get_today_pick()
    if pick is None:
        pick = find_daily_pick(persist=persist)
    if pick is None:
        return _ok({"status": "no_pick", "message": "Δεν βρέθηκε pick σήμερα."})
    return _ok(
        {
            "status": "ok",
            "summary": pick.summary_greek(),
            "play_if_odds_at_least": round(pick.fair_odds, 2),
            "pick": asdict(pick),
        }
    )


def tool_evaluate_odds(user_text: str) -> str:
    """
    Evaluate Novibet odds from user text like '#5 BTTS Όχι 2.03' or '2.10'.
    Returns PLAY / SKIP style verdict with anchored edge.
    """
    text = (user_text or "").strip()
    if not text:
        return _ok({"error": "empty_text", "hint": "Στείλε π.χ. «#5 2.03»"})

    board = get_or_build_today_board()
    idx, odds = parse_user_odds_reply(text)
    if idx is not None and odds is not None:
        candidate = find_candidate_by_index(board, idx)
        if candidate is None:
            return _ok({"error": "unknown_index", "index": idx, "hint": "Κάλεσε scan_matches."})
        pick = DailyPick(
            sport=candidate.sport,
            league=candidate.league,
            home=candidate.home,
            away=candidate.away,
            kickoff_utc=candidate.kickoff_utc,
            market=candidate.market,
            selection=candidate.selection,
            model_probability=candidate.model_probability,
            fair_odds=candidate.fair_odds,
            expected_goals=candidate.expected_goals,
            novibet_path=candidate.novibet_path,
        )
        verdict = evaluate_novibet_odds(pick, odds)
        return _ok(
            {
                "index": idx,
                "match": candidate.match_label,
                "market": candidate.market,
                "selection": candidate.selection,
                "novibet_odds": odds,
                "should_play": verdict.should_play,
                "verdict": "ΠΑΙΞΕ" if verdict.should_play else "SKIP",
                "reason": verdict.reason,
                "anchored_value_pct": verdict.value_pct,
                "anchor_note": verdict.anchor_note,
            }
        )

    odds_only = parse_odds_from_text(text)
    if odds_only is None:
        return _ok(
            {
                "error": "unparseable",
                "hint": "Χρησιμοποίησε μορφή «#5 2.03» ή απλή απόδοση αν υπάρχει ένα μόνο ματς.",
            }
        )

    upcoming = [c for c in board if c.status == "ΕΠΟΜΕΝΟ"]
    if len(upcoming) == 1:
        return tool_evaluate_odds(f"{upcoming[0].index} {odds_only}")

    pick = get_today_pick()
    if pick is None:
        return _ok(
            {
                "error": "need_index",
                "odds": odds_only,
                "hint": f"Πες και αριθμό ματς, π.χ. «5 {odds_only}».",
            }
        )
    verdict = evaluate_novibet_odds(pick, odds_only)
    return _ok(
        {
            "match": f"{pick.home} vs {pick.away}",
            "market": pick.market,
            "selection": pick.selection,
            "novibet_odds": odds_only,
            "should_play": verdict.should_play,
            "verdict": "ΠΑΙΞΕ" if verdict.should_play else "SKIP",
            "reason": verdict.reason,
            "anchored_value_pct": verdict.value_pct,
            "anchor_note": verdict.anchor_note,
        }
    )


def tool_get_bankroll() -> str:
    """Return Greek bankroll / open bets summary (καβά)."""
    return load_bankroll().summary_greek()


def tool_place_bet(
    match: str,
    league: str,
    market: str,
    selection: str,
    odds: float,
    stake: float,
    kickoff_utc: str = "",
) -> str:
    """Record a placed Novibet bet and debit bankroll."""
    if odds <= 1.0 or stake <= 0:
        return _ok({"error": "invalid_odds_or_stake"})
    bet = add_bet(
        match=match,
        league=league,
        market=market,
        selection=selection,
        odds=float(odds),
        stake=float(stake),
        kickoff_utc=kickoff_utc or "",
    )
    return _ok({"status": "placed", "bet": asdict(bet), "bankroll": load_bankroll().summary_greek()})


def tool_settle_bet(bet_id: str = "", match_substring: str = "", won: bool = False) -> str:
    """Settle an open bet by id or match substring."""
    if bet_id:
        bet = settle_bet(bet_id, won=won)
        if bet is None:
            return _ok({"error": "bet_not_found", "bet_id": bet_id})
        return _ok({"status": bet.status, "bet": asdict(bet), "bankroll": load_bankroll().summary_greek()})
    if match_substring:
        settled = settle_all_by_match(match_substring, won=won)
        if not settled:
            return _ok({"error": "no_match", "match_substring": match_substring})
        return _ok(
            {
                "status": "settled",
                "count": len(settled),
                "bets": [asdict(b) for b in settled],
                "bankroll": load_bankroll().summary_greek(),
            }
        )
    return _ok({"error": "need_bet_id_or_match_substring"})


def tool_pinnacle_status() -> str:
    """Report whether Pinnacle/pinnapi sharp feed is configured."""
    from value_scanner.scrapers.pinnacle import status_report

    return status_report()


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "scan_matches",
            "description": (
                "Scan upcoming matches likely on Novibet and return a numbered Greek list. "
                "Call this when the user asks for today's board, σκαν, or available games."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "force_rebuild": {
                        "type": "boolean",
                        "description": "If true, rebuild the board even if today's cache exists.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_pick",
            "description": "Get the single best model pick for today.",
            "parameters": {
                "type": "object",
                "properties": {
                    "persist": {
                        "type": "boolean",
                        "description": "Save the pick for follow-up odds checks.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "evaluate_odds",
            "description": (
                "Evaluate Novibet odds the user reported. Input examples: '#5 2.03', "
                "'5 BTTS Όχι 2.03', or a bare odds number when only one match is active. "
                "Returns ΠΑΙΞΕ or SKIP with anchored edge."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_text": {
                        "type": "string",
                        "description": "Raw user odds message.",
                    }
                },
                "required": ["user_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_bankroll",
            "description": "Show bankroll (καβά), open bets, and recent settled bets.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "place_bet",
            "description": "Record that the user placed a bet on Novibet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "match": {"type": "string"},
                    "league": {"type": "string"},
                    "market": {"type": "string"},
                    "selection": {"type": "string"},
                    "odds": {"type": "number"},
                    "stake": {"type": "number"},
                    "kickoff_utc": {"type": "string"},
                },
                "required": ["match", "league", "market", "selection", "odds", "stake"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "settle_bet",
            "description": "Settle an open bet as won or lost.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bet_id": {"type": "string"},
                    "match_substring": {"type": "string"},
                    "won": {"type": "boolean"},
                },
                "required": ["won"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pinnacle_status",
            "description": "Check Pinnacle / pinnapi sharp-line configuration.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


TOOL_HANDLERS: dict[str, Callable[..., str]] = {
    "scan_matches": tool_scan_matches,
    "get_daily_pick": tool_get_daily_pick,
    "evaluate_odds": tool_evaluate_odds,
    "get_bankroll": tool_get_bankroll,
    "place_bet": tool_place_bet,
    "settle_bet": tool_settle_bet,
    "pinnacle_status": tool_pinnacle_status,
}


def execute_tool(name: str, arguments: dict[str, Any] | None = None) -> str:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return _ok({"error": "unknown_tool", "name": name})
    args = arguments or {}
    try:
        return handler(**args)
    except TypeError as exc:
        return _ok({"error": "bad_arguments", "detail": str(exc), "arguments": args})
    except Exception as exc:  # noqa: BLE001 — surface tool failures to the model
        return _ok({"error": "tool_failed", "detail": str(exc)})
