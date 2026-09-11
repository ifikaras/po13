"""HTTP client for the remote Crypto Futures Signal Scanner."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any


class ScannerError(RuntimeError):
    pass


class ScannerClient:
    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ScannerError(f"{method} {path} failed: HTTP {exc.code} {detail[:400]}") from exc
        except urllib.error.URLError as exc:
            raise ScannerError(f"{method} {path} failed: {exc.reason}") from exc

    def start_scan(self, payload: dict[str, Any]) -> str:
        body = self._request("POST", "/api/scan", payload)
        job_id = body.get("job_id")
        if not job_id:
            raise ScannerError(f"scan did not return job_id: {body}")
        return str(job_id)

    def job_status(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/scan/{job_id}/status")

    def wait_for_scan(self, job_id: str, timeout: float = 180.0, poll: float = 1.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last = self.job_status(job_id)
            status = last.get("status")
            if status == "done":
                return last
            if status in {"failed", "error"}:
                raise ScannerError(last.get("message") or f"scan {job_id} failed")
            time.sleep(poll)
        raise ScannerError(f"scan {job_id} timed out after {timeout:.0f}s (last={last.get('status')})")

    def scan(self, payload: dict[str, Any], timeout: float = 180.0) -> dict[str, Any]:
        job_id = self.start_scan(payload)
        return self.wait_for_scan(job_id, timeout=timeout)
