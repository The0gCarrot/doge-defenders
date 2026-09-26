"""Yahoo Finance RSS headlines for crypto USD tickers."""

from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import requests

from src import write_json

YAHOO_RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline"


class YahooRssClient:
    def __init__(self, rate_limit_seconds: float = 1.0, cache_dir: Path | None = None) -> None:
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

    def fetch_feed(self, yahoo_symbol: str) -> list[dict[str, Any]]:
        cache_path: Path | None = None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            safe = yahoo_symbol.replace("/", "_")
            cache_path = self.cache_dir / f"yahoo_{safe}.json"
            if cache_path.exists():
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
                return list(payload.get("items") or [])

        self._throttle()
        url = f"{YAHOO_RSS}?s={yahoo_symbol}&region=US&lang=en-US"
        try:
            resp = self.session.get(url, timeout=45)
            resp.raise_for_status()
            items = _parse_rss(resp.text)
        except Exception as exc:  # noqa: BLE001
            items = []
            if cache_path:
                write_json(cache_path, {"items": [], "error": str(exc), "symbol": yahoo_symbol})
                return items

        if cache_path:
            write_json(cache_path, {"items": items, "symbol": yahoo_symbol})
        return items

    def headlines_in_window(
        self,
        yahoo_symbol: str,
        report_day: datetime,
        lookback_days: int,
    ) -> list[str]:
        items = self.fetch_feed(yahoo_symbol)
        start = report_day - timedelta(days=lookback_days)
        end = report_day + timedelta(days=1)
        titles: list[str] = []
        for it in items:
            ts = it.get("published")
            if not isinstance(ts, str) or not ts:
                continue
            try:
                pub = datetime.fromisoformat(ts)
            except ValueError:
                continue
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            if start <= pub <= end:
                titles.append(str(it.get("title") or "")[:240])
        return [t for t in titles if t][:12]


def _parse_rss(xml_text: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        pub_raw = item.findtext("pubDate") or ""
        published = ""
        if pub_raw:
            try:
                published = parsedate_to_datetime(pub_raw).astimezone(timezone.utc).isoformat()
            except (TypeError, ValueError, IndexError):
                published = ""
        link = (item.findtext("link") or "").strip()
        items.append({"title": title, "url": link, "published": published})
    return items
