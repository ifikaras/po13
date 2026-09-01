"""Track open bets and bankroll for the user's Novibet workflow."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Literal

BANKROLL_PATH = Path("data/bankroll.json")

BetStatus = Literal["open", "won", "lost", "void"]


@dataclass
class Bet:
    id: str
    placed_date: str
    match: str
    league: str
    market: str
    selection: str
    odds: float
    stake: float
    kickoff_utc: str
    status: BetStatus = "open"
    profit: float = 0.0

    @property
    def potential_return(self) -> float:
        return round(self.stake * self.odds, 2)

    def settle(self, won: bool) -> float:
        if won:
            self.status = "won"
            self.profit = round(self.stake * (self.odds - 1), 2)
        else:
            self.status = "lost"
            self.profit = -self.stake
        return self.profit


@dataclass
class BankrollState:
    currency: str = "EUR"
    starting_bankroll: float = 100.0
    current_bankroll: float = 100.0
    open_bets: list[Bet] = None
    settled_bets: list[Bet] = None

    def __post_init__(self) -> None:
        if self.open_bets is None:
            self.open_bets = []
        if self.settled_bets is None:
            self.settled_bets = []

    @property
    def open_stake_total(self) -> float:
        return sum(b.stake for b in self.open_bets)

    @property
    def available_cash(self) -> float:
        return round(self.current_bankroll, 2)

    def summary_greek(self) -> str:
        lines = [
            f"Διαθέσιμα μετρητά: €{self.current_bankroll:.2f}",
            f"Αρχική καβά: €{self.starting_bankroll:.2f}",
            f"Σε ανοιχτά στοιχήματα: €{self.open_stake_total:.2f}",
        ]
        if self.open_bets:
            lines.append("")
            lines.append("ΕΝΕΡΓΑ ΣΤΟΙΧΗΜΑΤΑ:")
            for b in self.open_bets:
                kick = ""
                if b.kickoff_utc:
                    kick = f" ({b.kickoff_utc[:10]})"
                lines.append(
                    f"• {b.match}{kick} — {b.market} {b.selection} "
                    f"€{b.stake:.2f} @ {b.odds} (επιστροφή €{b.potential_return:.2f})"
                )
        if self.settled_bets:
            lines.append("")
            lines.append("ΚΛΕΙΣΜΕΝΑ:")
            for b in self.settled_bets[-5:]:
                sign = f"+€{b.profit:.2f}" if b.profit >= 0 else f"-€{abs(b.profit):.2f}"
                lines.append(f"• {b.match} {b.selection} → {b.status.upper()} ({sign})")
        return "\n".join(lines)


def _bet_from_dict(data: dict) -> Bet:
    return Bet(
        id=data["id"],
        placed_date=data["placed_date"],
        match=data["match"],
        league=data["league"],
        market=data["market"],
        selection=data["selection"],
        odds=float(data["odds"]),
        stake=float(data["stake"]),
        kickoff_utc=data.get("kickoff_utc", ""),
        status=data.get("status", "open"),
        profit=float(data.get("profit", 0)),
    )


def load_bankroll() -> BankrollState:
    if not BANKROLL_PATH.exists():
        return BankrollState()
    data = json.loads(BANKROLL_PATH.read_text(encoding="utf-8"))
    return BankrollState(
        currency=data.get("currency", "EUR"),
        starting_bankroll=float(data.get("starting_bankroll", 100)),
        current_bankroll=float(data.get("current_bankroll", 100)),
        open_bets=[_bet_from_dict(b) for b in data.get("open_bets", [])],
        settled_bets=[_bet_from_dict(b) for b in data.get("settled_bets", [])],
    )


def save_bankroll(state: BankrollState) -> Path:
    BANKROLL_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "currency": state.currency,
        "starting_bankroll": state.starting_bankroll,
        "current_bankroll": state.current_bankroll,
        "open_bets": [asdict(b) for b in state.open_bets],
        "settled_bets": [asdict(b) for b in state.settled_bets],
    }
    BANKROLL_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return BANKROLL_PATH


def add_bet(
    match: str,
    league: str,
    market: str,
    selection: str,
    odds: float,
    stake: float,
    kickoff_utc: str = "",
    placed_date: date | None = None,
) -> Bet:
    state = load_bankroll()
    placed = (placed_date or date.today()).isoformat()
    bet_id = f"bet-{placed}-{len(state.open_bets) + len(state.settled_bets) + 1}"
    bet = Bet(
        id=bet_id,
        placed_date=placed,
        match=match,
        league=league,
        market=market,
        selection=selection,
        odds=odds,
        stake=stake,
        kickoff_utc=kickoff_utc,
    )
    state.current_bankroll = round(state.current_bankroll - stake, 2)
    state.open_bets.append(bet)
    save_bankroll(state)
    return bet


def settle_bet(bet_id: str, won: bool) -> Bet | None:
    state = load_bankroll()
    for i, bet in enumerate(state.open_bets):
        if bet.id == bet_id:
            profit = bet.settle(won)
            if won:
                state.current_bankroll = round(state.current_bankroll + bet.potential_return, 2)
            state.settled_bets.append(bet)
            state.open_bets.pop(i)
            save_bankroll(state)
            return bet
    return None


def settle_all_by_match(match_substring: str, won: bool) -> list[Bet]:
    state = load_bankroll()
    settled: list[Bet] = []
    low = match_substring.lower()
    for bet in list(state.open_bets):
        if low in bet.match.lower():
            settled.append(settle_bet(bet.id, won) or bet)
    return settled
