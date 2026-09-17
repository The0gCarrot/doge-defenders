"""Rate-limited CoinGecko REST client."""

from __future__ import annotations

import os
import time
from typing import Any

import requests


class CoinGeckoClient:
    def __init__(self, base_url: str, rate_limit_seconds: float = 6.5) -> None:
        self.base_url = base_url.rstrip("/")
        self.rate_limit_seconds = rate_limit_seconds
        self._last_call = 0.0
        self.session = requests.Session()
        api_key = os.environ.get("COINGECKO_API_KEY", "").strip()
        if api_key:
            # Demo/Pro header; harmless if unused on public tier.
            self.session.headers["x-cg-demo-api-key"] = api_key

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        wait = self.rate_limit_seconds - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def get(self, path: str, params: dict[str, Any] | None = None, retries: int = 5) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        last_exc: Exception | None = None
        for attempt in range(retries):
            self._throttle()
            resp = self.session.get(url, params=params or {}, timeout=60)
            if resp.status_code == 429:
                retry_after = float(
                    resp.headers.get("Retry-After", self.rate_limit_seconds * (attempt + 2))
                )
                time.sleep(retry_after)
                self._last_call = time.monotonic()
                last_exc = requests.HTTPError(f"429 rate limit on {url}", response=resp)
                continue
            if resp.status_code >= 400:
                # range endpoint is paid-only on free tier; callers should use market_chart.
                resp.raise_for_status()
            return resp.json()
        if last_exc:
            raise last_exc
        raise RuntimeError(f"Failed GET {url}")

    def coin_detail(self, coin_id: str) -> Any:
        return self.get(
            f"coins/{coin_id}",
            {
                "localization": "false",
                "tickers": "true",
                "market_data": "false",
                "community_data": "false",
                "developer_data": "false",
            },
        )

    def market_chart(self, coin_id: str, days: str | int = "max") -> Any:
        """Public free-tier chart. Prefer this over /market_chart/range (paid)."""
        return self.get(
            f"coins/{coin_id}/market_chart",
            {"vs_currency": "usd", "days": days},
        )
