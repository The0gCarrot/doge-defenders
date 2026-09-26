"""GDELT Doc API client — free press/web article search by token query."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from src import write_json

GDELT_DOC = "https://api.gdeltproject.org/api/v2/doc/doc"


def _parse_seendate(raw: str) -> datetime | None:
    """GDELT seendate: YYYYMMDDHHMMSS or 20260706T064500Z."""
    s = str(raw).strip()
    if not s:
        return None
    if "T" in s:
        try:
            core = s.replace("Z", "").replace("+00:00", "")
            if len(core) >= 15 and core[8] == "T":
                return datetime.strptime(core[:15], "%Y%m%dT%H%M%S").replace(
                    tzinfo=timezone.utc
                )
        except ValueError:
            pass
    digits = "".join(c for c in s if c.isdigit())
    if len(digits) >= 14:
        try:
            return datetime.strptime(digits[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    if len(digits) >= 8:
        try:
            return datetime.strptime(digits[:8], "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _loads_gdelt(text: str) -> dict[str, Any]:
    """Parse GDELT JSON; tolerate illegal backslash escapes in titles/URLs."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        fixed = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", text)
        return json.loads(fixed)


def _normalize_articles(
    raw_articles: list[Any],
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for a in raw_articles:
        if not isinstance(a, dict):
            continue
        title = str(a.get("title") or "").strip()
        if not title:
            continue
        ts = _parse_seendate(str(a.get("seendate") or ""))
        if start is not None and end is not None and ts is not None:
            if not (start <= ts <= end):
                continue
        out.append(
            {
                "title": title,
                "url": a.get("url") or "",
                "seendate": a.get("seendate") or "",
                "source": a.get("domain") or a.get("sourceCommonName") or "gdelt",
            }
        )
    return out


class GdeltClient:
    def __init__(self, rate_limit_seconds: float = 6.0, cache_dir: Path | None = None) -> None:
        self.rate_limit_seconds = rate_limit_seconds
        self.cache_dir = cache_dir
        self._last_call = 0.0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "DogeDefenders/1.0 (school project)"

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        wait = self.rate_limit_seconds - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def _get_json(self, params: dict[str, str], retries: int = 2) -> tuple[dict[str, Any], str]:
        last_err = ""
        for attempt in range(retries):
            self._throttle()
            try:
                resp = self.session.get(GDELT_DOC, params=params, timeout=90)
                if resp.status_code == 429:
                    last_err = "429 Too Many Requests"
                    time.sleep(8.0 * (attempt + 1))
                    continue
                text = resp.text.strip()
                if text.lower().startswith("please limit"):
                    last_err = "rate limit message"
                    time.sleep(8.0 * (attempt + 1))
                    continue
                if not text or text.startswith("<"):
                    last_err = "empty/html body"
                    continue
                resp.raise_for_status()
                return _loads_gdelt(text), ""
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)
                time.sleep(6.0 * (attempt + 1))
        return {}, last_err

    def search_range(
        self,
        query: str,
        start: datetime,
        end: datetime,
        *,
        maxrecords: int = 250,
        cache_key: str | None = None,
        retries: int = 2,
    ) -> list[dict[str, Any]]:
        """
        Prefer timespan query (reliable), filter client-side to [start, end].
        Falls back to STARTDATETIME range once if timespan yields nothing in-window.
        """
        cache_path: Path | None = None
        if self.cache_dir and cache_key:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in cache_key)[:120]
            cache_path = self.cache_dir / f"gdelt_{safe}.json"
            if cache_path.exists():
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
                if "error" not in payload and payload.get("articles") is not None:
                    return list(payload.get("articles") or [])

        days = max(30, int((end - start).total_seconds() // 86400) + 10)
        days = min(days, 120)
        last_err = ""

        # 1) Timespan first (works under load; date-range often 429s)
        data, err = self._get_json(
            {
                "query": query,
                "mode": "ArtList",
                "maxrecords": str(maxrecords),
                "format": "json",
                "sort": "DateDesc",
                "timespan": f"{days}d",
            },
            retries=retries,
        )
        last_err = err
        articles = _normalize_articles(list(data.get("articles") or []), start, end)

        # If timespan returned hits but all outside window, keep unfiltered for cache
        # and still try date-range once for the historical window.
        if not articles:
            data2, err2 = self._get_json(
                {
                    "query": query,
                    "mode": "ArtList",
                    "maxrecords": str(maxrecords),
                    "format": "json",
                    "sort": "DateDesc",
                    "STARTDATETIME": start.strftime("%Y%m%d%H%M%S"),
                    "ENDDATETIME": end.strftime("%Y%m%d%H%M%S"),
                },
                retries=1,
            )
            last_err = err2 or last_err
            articles = _normalize_articles(list(data2.get("articles") or []), start, end)

        if cache_path:
            payload: dict[str, Any] = {"articles": articles, "query": query}
            if last_err and not articles:
                payload["error"] = last_err
            write_json(cache_path, payload)
        return articles

    def headlines_in_window(
        self,
        articles: list[dict[str, Any]],
        report_day: datetime,
        lookback_days: int,
    ) -> list[str]:
        start = report_day - timedelta(days=lookback_days)
        end = report_day + timedelta(days=1)
        titles: list[str] = []
        for a in articles:
            ts = _parse_seendate(str(a.get("seendate") or ""))
            if ts is None:
                continue
            if start <= ts <= end:
                titles.append(str(a["title"])[:240])
        return titles[:12]


def default_gdelt_query(display_name: str, symbol: str) -> str:
    """Build a GDELT query biased toward the crypto asset."""
    name = display_name.strip()
    sym = symbol.strip().upper()
    if name.lower() == "bitcoin" or sym == "BTC":
        return "Bitcoin"
    if name.lower() == "ethereum" or sym == "ETH":
        return "Ethereum"
    return f"{name} crypto"
