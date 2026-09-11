"""Load bot settings from YAML plus optional environment overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path("config/futures_bot.yaml")


@dataclass(frozen=True)
class ScanSettings:
    top_n: int = 100
    interval: str = "4h"
    min_score: float = 5.0
    skip_confirmation: bool = False
    skip_social: bool = False
    skip_stocktwits: bool = False
    skip_reddit: bool = False
    self_test: bool = False
    limit: int | None = None


@dataclass(frozen=True)
class ApprovalSettings:
    min_score: float = 5.0
    min_conviction: str = "moderate"
    min_optimal_rr1: float = 1.5
    require_hard_filters: bool = True
    require_leverage_safe: bool = True
    require_confirmation: bool = False
    max_chase_pct: float = 0.8


@dataclass(frozen=True)
class RiskSettings:
    account_size: float = 1000.0
    risk_pct: float = 1.0
    intended_leverage: float = 3.0
    max_open_positions: int = 3
    max_daily_new_positions: int = 5


@dataclass(frozen=True)
class NotifySettings:
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""


@dataclass(frozen=True)
class BotConfig:
    scanner_url: str
    mode: str
    scan: ScanSettings
    approval: ApprovalSettings
    risk: RiskSettings
    notify: NotifySettings
    ledger_path: Path

    def scan_payload(self, *, self_test: bool | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "top_n": self.scan.top_n,
            "interval": self.scan.interval,
            "min_score": self.scan.min_score,
            "account_size": self.risk.account_size,
            "risk_pct": self.risk.risk_pct,
            "leverage": self.risk.intended_leverage,
            "skip_confirmation": self.scan.skip_confirmation,
            "skip_social": self.scan.skip_social,
            "skip_stocktwits": self.scan.skip_stocktwits,
            "skip_reddit": self.scan.skip_reddit,
            "self_test": self.scan.self_test if self_test is None else self_test,
        }
        if self.scan.limit is not None:
            payload["limit"] = self.scan.limit
        return payload

    def with_scan_overrides(
        self,
        *,
        limit: int | None = None,
        skip_confirmation: bool = False,
        skip_social: bool = False,
        self_test: bool = False,
    ) -> "BotConfig":
        updates: dict[str, Any] = {}
        if limit is not None:
            updates["limit"] = limit
        if skip_confirmation:
            updates["skip_confirmation"] = True
        if skip_social:
            updates["skip_social"] = True
        if self_test:
            updates["self_test"] = True
        if not updates:
            return self
        return replace(self, scan=replace(self.scan, **updates))


def _section(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key) or {}
    if not isinstance(value, dict):
        raise ValueError(f"config.{key} must be a mapping")
    return value


def load_config(path: str | Path | None = None) -> BotConfig:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    raw = yaml.safe_load(config_path.read_text()) or {}
    if not isinstance(raw, dict):
        raise ValueError("config root must be a mapping")

    scan = _section(raw, "scan")
    approval = _section(raw, "approval")
    risk = _section(raw, "risk")
    notify = _section(raw, "notify")

    token = os.environ.get("TELEGRAM_BOT_TOKEN", notify.get("telegram_bot_token") or "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", notify.get("telegram_chat_id") or "")
    scanner_url = os.environ.get("SCANNER_URL", raw.get("scanner_url") or "").rstrip("/")
    if not scanner_url:
        raise ValueError("scanner_url is required")

    mode = str(raw.get("mode") or "paper").strip().lower()
    if mode != "paper":
        raise ValueError("only mode: paper is supported in this version")

    limit = scan.get("limit")
    return BotConfig(
        scanner_url=scanner_url,
        mode=mode,
        scan=ScanSettings(
            top_n=int(scan.get("top_n", 100)),
            interval=str(scan.get("interval", "4h")),
            min_score=float(scan.get("min_score", 5.0)),
            skip_confirmation=bool(scan.get("skip_confirmation", False)),
            skip_social=bool(scan.get("skip_social", False)),
            skip_stocktwits=bool(scan.get("skip_stocktwits", False)),
            skip_reddit=bool(scan.get("skip_reddit", False)),
            self_test=bool(scan.get("self_test", False)),
            limit=int(limit) if limit not in (None, "", 0) else None,
        ),
        approval=ApprovalSettings(
            min_score=float(approval.get("min_score", 5.0)),
            min_conviction=str(approval.get("min_conviction", "moderate")),
            min_optimal_rr1=float(approval.get("min_optimal_rr1", 1.5)),
            require_hard_filters=bool(approval.get("require_hard_filters", True)),
            require_leverage_safe=bool(approval.get("require_leverage_safe", True)),
            require_confirmation=bool(approval.get("require_confirmation", False)),
            max_chase_pct=float(approval.get("max_chase_pct", 0.8)),
        ),
        risk=RiskSettings(
            account_size=float(risk.get("account_size", 1000)),
            risk_pct=float(risk.get("risk_pct", 1.0)),
            intended_leverage=float(risk.get("intended_leverage", 3)),
            max_open_positions=int(risk.get("max_open_positions", 3)),
            max_daily_new_positions=int(risk.get("max_daily_new_positions", 5)),
        ),
        notify=NotifySettings(
            telegram_enabled=bool(notify.get("telegram_enabled", False)),
            telegram_bot_token=str(token or ""),
            telegram_chat_id=str(chat_id or ""),
        ),
        ledger_path=Path(raw.get("ledger_path") or "data/futures_paper.json"),
    )
