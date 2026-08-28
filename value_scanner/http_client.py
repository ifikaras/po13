"""HTTP client helpers."""

from __future__ import annotations

from curl_cffi import requests


def get_json(url: str, timeout: int = 20) -> dict | list:
    response = requests.get(url, impersonate="chrome120", timeout=timeout)
    response.raise_for_status()
    return response.json()
