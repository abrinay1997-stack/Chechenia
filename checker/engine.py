from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional
from urllib.parse import urlparse

import httpx

EMAIL_RE = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)

# This tool only talks to *your* API. These hosts are rejected on purpose.
BLOCKED_HOSTS = {
    "spotify.com",
    "www.spotify.com",
    "accounts.spotify.com",
    "spclient.wg.spotify.com",
    "api.spotify.com",
    "netflix.com",
    "www.netflix.com",
    "instagram.com",
    "www.instagram.com",
    "facebook.com",
    "www.facebook.com",
    "google.com",
    "accounts.google.com",
    "apple.com",
    "icloud.com",
    "amazon.com",
    "discord.com",
    "twitter.com",
    "x.com",
    "tiktok.com",
}


@dataclass
class CheckResult:
    raw: str
    email: str
    status: str  # registered | available | invalid | error | blocked
    detail: str = ""
    ms: int = 0


@dataclass
class RunStats:
    total: int = 0
    registered: int = 0
    available: int = 0
    invalid: int = 0
    errors: int = 0
    blocked: int = 0
    started_at: float = field(default_factory=time.time)

    def apply(self, result: CheckResult) -> None:
        if result.status == "registered":
            self.registered += 1
        elif result.status == "available":
            self.available += 1
        elif result.status == "invalid":
            self.invalid += 1
        elif result.status == "blocked":
            self.blocked += 1
        else:
            self.errors += 1


ProgressCb = Callable[[CheckResult, RunStats], None]


def load_emails(path: str | Path) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # If someone pastes email:pass, only the email is used. Passwords are ignored.
        email = line.split(":", 1)[0].strip().lower()
        if email and email not in seen:
            seen.add(email)
            lines.append(email)
    return lines


def load_config(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        "api_base_url": str(data.get("api_base_url", "http://127.0.0.1:8787")).rstrip("/"),
        "exists_path": str(data.get("exists_path", "/admin/users/exists")),
        "admin_key": str(data.get("admin_key", "")),
        "timeout_sec": float(data.get("timeout_sec", 12)),
        "workers": max(1, min(32, int(data.get("workers", 8)))),
        "delay_ms": max(0, int(data.get("delay_ms", 0))),
    }


def _host_blocked(url: str) -> Optional[str]:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return "invalid_host"
    if host in BLOCKED_HOSTS:
        return host
    for blocked in BLOCKED_HOSTS:
        if host.endswith("." + blocked):
            return blocked
    return None


def check_one(email: str, cfg: dict, client: httpx.Client) -> CheckResult:
    raw = email
    if not EMAIL_RE.match(email):
        return CheckResult(raw=raw, email=email, status="invalid", detail="bad_format")

    base = cfg["api_base_url"]
    blocked = _host_blocked(base)
    if blocked:
        return CheckResult(
            raw=raw,
            email=email,
            status="blocked",
            detail=f"host_not_allowed:{blocked}",
        )

    url = base + cfg["exists_path"]
    headers = {"X-Admin-Key": cfg["admin_key"], "Accept": "application/json"}
    t0 = time.perf_counter()
    try:
        response = client.get(
            url,
            params={"email": email},
            headers=headers,
            timeout=cfg["timeout_sec"],
        )
        ms = int((time.perf_counter() - t0) * 1000)
        if response.status_code == 401:
            return CheckResult(raw, email, "error", "unauthorized_admin_key", ms)
        if response.status_code >= 400:
            return CheckResult(raw, email, "error", f"http_{response.status_code}", ms)

        try:
            payload = response.json()
        except ValueError:
            return CheckResult(raw, email, "error", "response_not_json", ms)

        if not isinstance(payload, dict) or "registered" not in payload:
            return CheckResult(raw, email, "error", "unexpected_schema", ms)

        if payload.get("valid_format") is False:
            return CheckResult(raw, email, "invalid", "api_invalid_format", ms)

        registered = bool(payload.get("registered"))
        return CheckResult(
            raw,
            email,
            "registered" if registered else "available",
            "ok",
            ms,
        )
    except httpx.TimeoutException:
        return CheckResult(raw, email, "error", "timeout", int((time.perf_counter() - t0) * 1000))
    except httpx.RequestError as exc:
        return CheckResult(raw, email, "error", f"network:{exc.__class__.__name__}", int((time.perf_counter() - t0) * 1000))


def run_checks(
    emails: Iterable[str],
    cfg: dict,
    on_progress: Optional[ProgressCb] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> tuple[list[CheckResult], RunStats]:
    items = list(emails)
    stats = RunStats(total=len(items))
    results: list[CheckResult] = []

    with httpx.Client(follow_redirects=False) as client:
        with ThreadPoolExecutor(max_workers=cfg["workers"]) as pool:
            futures = {}
            for email in items:
                if should_stop and should_stop():
                    break
                futures[pool.submit(check_one, email, cfg, client)] = email
                if cfg["delay_ms"]:
                    time.sleep(cfg["delay_ms"] / 1000)

            for future in as_completed(futures):
                if should_stop and should_stop():
                    break
                result = future.result()
                results.append(result)
                stats.apply(result)
                if on_progress:
                    on_progress(result, stats)
    return results, stats


def write_results(results: list[CheckResult], folder: str | Path) -> dict[str, Path]:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    buckets = {
        "registered": folder / "registered.txt",
        "available": folder / "available.txt",
        "invalid": folder / "invalid.txt",
        "errors": folder / "errors.txt",
    }
    grouped: dict[str, list[str]] = {k: [] for k in buckets}
    for item in results:
        key = "errors" if item.status in {"error", "blocked"} else item.status
        line = item.email if item.status in {"registered", "available", "invalid"} else f"{item.email}\t{item.status}\t{item.detail}"
        grouped[key].append(line)
    for key, path in buckets.items():
        path.write_text("\n".join(grouped[key]) + ("\n" if grouped[key] else ""), encoding="utf-8")
    summary = folder / "summary.json"
    summary.write_text(
        json.dumps(
            {
                "total": len(results),
                "registered": sum(1 for r in results if r.status == "registered"),
                "available": sum(1 for r in results if r.status == "available"),
                "invalid": sum(1 for r in results if r.status == "invalid"),
                "errors": sum(1 for r in results if r.status in {"error", "blocked"}),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return buckets
