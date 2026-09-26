"""
Reconcile GDELT + Yahoo headlines into one press opinion and news_delta.

Conflict rule (plan): bullish vs bearish → neutral, news_delta=0.
"""

from __future__ import annotations

from typing import Any

from src import MISSING_STR

BULLISH_KW = (
    "partnership",
    "listing",
    "lists",
    "upgrade",
    "adoption",
    "etf approved",
    "etf approval",
    "rally",
    "surge",
    "record high",
    "all-time high",
    "bullish",
    "integrates",
    "integration",
    "launch",
    "launches",
    "funding",
    "raises",
    "institutional",
)

BEARISH_KW = (
    "hack",
    "hacked",
    "exploit",
    "sec ",
    "lawsuit",
    "sues",
    "sued",
    "ban",
    "banned",
    "crackdown",
    "fraud",
    "probe",
    "investigation",
    "collapse",
    "crash",
    "bearish",
    "outage",
    "breach",
    "fine",
    "charged",
    "indictment",
)


def title_relevant(title: str, symbol: str, display_name: str) -> bool:
    """Drop unrelated Yahoo/GDELT noise (e.g. Rupee headlines on BTC feed)."""
    t = title.lower()
    sym = symbol.lower().strip()
    name = display_name.lower().strip()
    if sym and (f"${sym}" in t or f"{sym}-usd" in t or f" {sym} " in f" {t} "):
        return True
    if name and len(name) >= 3 and name in t:
        return True
    aliases = {
        "btc": ("bitcoin",),
        "eth": ("ethereum",),
        "doge": ("dogecoin", "doge"),
        "xrp": ("ripple", "xrp"),
        "sol": ("solana",),
        "ada": ("cardano",),
        "avax": ("avalanche",),
        "dot": ("polkadot",),
        "link": ("chainlink",),
        "ltc": ("litecoin",),
        "uni": ("uniswap",),
        "arb": ("arbitrum",),
        "near": ("near protocol", "near"),
        "aave": ("aave",),
        "pepe": ("pepe",),
    }
    for a in aliases.get(sym, ()):
        if a in t:
            return True
    return False


def filter_relevant(
    headlines: list[str], symbol: str, display_name: str
) -> list[str]:
    return [h for h in headlines if title_relevant(h, symbol, display_name)]


def stance_from_headlines(headlines: list[str]) -> str:
    """Return bullish | bearish | neutral | none."""
    if not headlines:
        return "none"
    text = " ".join(headlines).lower()
    bull = sum(1 for k in BULLISH_KW if k in text)
    bear = sum(1 for k in BEARISH_KW if k in text)
    if bull == 0 and bear == 0:
        return "neutral"
    if bull > bear:
        return "bullish"
    if bear > bull:
        return "bearish"
    return "neutral"


def _join_headlines(headlines: list[str]) -> str:
    cleaned = [" ".join(h.split()) for h in headlines if h and h.strip()]
    if not cleaned:
        return MISSING_STR
    return " | ".join(cleaned[:12])


def reconcile_press(
    gdelt_headlines: list[str],
    yahoo_headlines: list[str],
) -> dict[str, Any]:
    """
    Compare sources and emit team opinion + news_delta in {-5, 0, +5}.

    Returns keys: press_gdelt, press_yahoo, press_release, press_opinion,
    press_conflict, news_delta, news_count_10d, gdelt_stance, yahoo_stance.
    """
    g_text = _join_headlines(gdelt_headlines)
    y_text = _join_headlines(yahoo_headlines)
    g_stance = stance_from_headlines(gdelt_headlines)
    y_stance = stance_from_headlines(yahoo_headlines)

    merged: list[str] = []
    seen: set[str] = set()
    for h in gdelt_headlines + yahoo_headlines:
        key = h.strip().lower()
        if key and key not in seen:
            seen.add(key)
            merged.append(h.strip())

    press_release = _join_headlines(merged)
    count = len(merged)

    if g_stance == "none" and y_stance == "none":
        return {
            "press_gdelt": MISSING_STR,
            "press_yahoo": MISSING_STR,
            "press_release": MISSING_STR,
            "press_opinion": "none",
            "press_conflict": "none",
            "news_delta": 0,
            "news_count_10d": 0,
            "gdelt_stance": g_stance,
            "yahoo_stance": y_stance,
        }

    if g_stance == "none" or y_stance == "none":
        opinion = y_stance if g_stance == "none" else g_stance
        delta = 5 if opinion == "bullish" else (-5 if opinion == "bearish" else 0)
        return {
            "press_gdelt": g_text,
            "press_yahoo": y_text,
            "press_release": press_release,
            "press_opinion": opinion,
            "press_conflict": "none",
            "news_delta": delta,
            "news_count_10d": count,
            "gdelt_stance": g_stance,
            "yahoo_stance": y_stance,
        }

    if g_stance == y_stance:
        opinion = g_stance
        delta = 5 if opinion == "bullish" else (-5 if opinion == "bearish" else 0)
        conflict = "agree"
    elif {g_stance, y_stance} == {"bullish", "bearish"}:
        opinion = "neutral"
        delta = 0
        conflict = "disagree"
    else:
        if "bullish" in (g_stance, y_stance):
            opinion = "bullish"
            delta = 5
        elif "bearish" in (g_stance, y_stance):
            opinion = "bearish"
            delta = -5
        else:
            opinion = "neutral"
            delta = 0
        conflict = "agree"

    return {
        "press_gdelt": g_text,
        "press_yahoo": y_text,
        "press_release": press_release,
        "press_opinion": opinion,
        "press_conflict": conflict,
        "news_delta": delta,
        "news_count_10d": count,
        "gdelt_stance": g_stance,
        "yahoo_stance": y_stance,
    }
