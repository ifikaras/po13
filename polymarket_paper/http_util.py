"""Minimal HTTP helpers for paper simulators."""

from __future__ import annotations

import json
import urllib.request
from typing import Any

USER_AGENT = "polymarket-paper-sim/1.0"


def get_json(url: str, timeout: int = 25) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())
