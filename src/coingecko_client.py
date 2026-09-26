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

    def simple_prices(
        self,
        coin_ids: list[str],
        *,
        include_24hr_change: bool = True,
    ) -> dict[str, dict[str, float]]:
        """Batch live USD prices (one call). Values: {usd, usd_24h_change?}."""
        if not coin_ids:
            return {}
        params: dict[str, Any] = {"ids": ",".join(coin_ids), "vs_currencies": "usd"}
        if include_24hr_change:
            params["include_24hr_change"] = "true"
        data = self.get("simple/price", params)
        out: dict[str, dict[str, float]] = {}
        for cid in coin_ids:
            row = data.get(cid) or {}
            if "usd" not in row:
                continue
            entry: dict[str, float] = {"usd": float(row["usd"])}
            if "usd_24h_change" in row and row["usd_24h_change"] is not None:
                entry["usd_24h_change"] = float(row["usd_24h_change"])
            out[cid] = entry
        return out

    def markets_live(self, coin_ids: list[str]) -> dict[str, dict[str, Any]]:
        """
        Live market snapshot for scoring + paper (one call).
        Fields: price_usd, volume_24h_usd, market_cap_usd, return_24h, momentum_30d_pct.
        """
        if not coin_ids:
            return {}
        data = self.get(
            "coins/markets",
            {
                "vs_currency": "usd",
                "ids": ",".join(coin_ids),
                "order": "market_cap_desc",
                "per_page": len(coin_ids),
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "24h,30d",
            },
        )
        out: dict[str, dict[str, Any]] = {}
        if not isinstance(data, list):
            return out
        for row in data:
            cid = str(row.get("id") or "")
            if not cid:
                continue
            out[cid] = {
                "price_usd": float(row["current_price"])
                if row.get("current_price") is not None
                else None,
                "volume_24h_usd": float(row["total_volume"])
                if row.get("total_volume") is not None
                else None,
                "market_cap_usd": float(row["market_cap"])
                if row.get("market_cap") is not None
                else None,
                "return_24h": float(row["price_change_percentage_24h"])
                if row.get("price_change_percentage_24h") is not None
                else (
                    float(row["price_change_percentage_24h_in_currency"])
                    if row.get("price_change_percentage_24h_in_currency") is not None
                    else None
                ),
                "momentum_30d_pct": float(row["price_change_percentage_30d_in_currency"])
                if row.get("price_change_percentage_30d_in_currency") is not None
                else None,
            }
        return out

    def status_updates(self, coin_id: str, per_page: int = 50) -> Any:
        """Public project status updates / headlines for a coin (may be empty)."""
        return self.get(
            f"coins/{coin_id}/status_updates",
            {"per_page": per_page, "page": 1},
        )
