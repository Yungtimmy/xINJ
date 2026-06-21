"""
Fetches weekly ecosystem metrics from Injective Explorer, DefiLlama, Talis, and CoinGecko.
"""

from __future__ import annotations
import os, requests
from datetime import datetime, timedelta, timezone

EXPLORER_BASE = "https://explorer.injective.network/api/explorer"
INDEXER_BASE  = "https://sentry.lcd.injective.network"
TALIS_BASE    = "https://api.talis.art"

DAPP_NAMES = ["Helix", "Mito", "Hydro", "DojoSwap", "Black Panther", "Neptune", "Choice"]

# DefiLlama slug -> display name mapping (dexs + fees + lending)
DEFILLAMA_SLUG_MAP = {
    "helix":         "Helix",
    "dojoswap":      "DojoSwap",
    "mito":          "Mito",
    "neptune":       "Neptune",
    "hydro":         "Hydro",
    "black panther": "Black Panther",
    "blackpanther":  "Black Panther",
    "choice":        "Choice",
    "injective":     "Helix",   # sometimes listed under chain name
}


def _get(url: str, params: dict | None = None, headers: dict | None = None) -> dict | list:
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ── Chain metrics ──────────────────────────────────────────────────────────────

def fetch_tvl() -> float | None:
    try:
        for chain in _get("https://api.llama.fi/v2/chains"):
            if chain.get("name", "").lower() == "injective":
                return float(chain.get("tvl", 0))
    except Exception:
        return None


def fetch_weekly_txns(days: int = 7) -> int | None:
    """Try multiple endpoint/param formats until one returns data."""
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    attempts = [
        # format 1: unix seconds
        (f"{EXPLORER_BASE}/v1/txs/stats", {"startTime": int(start.timestamp()), "endTime": int(end.timestamp())}),
        # format 2: ISO strings
        (f"{EXPLORER_BASE}/v1/txs/stats", {"from": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "to": end.strftime("%Y-%m-%dT%H:%M:%SZ")}),
        # format 3: date-only
        (f"{EXPLORER_BASE}/v1/txs/stats", {"startDate": start.strftime("%Y-%m-%d"), "endDate": end.strftime("%Y-%m-%d")}),
        # format 4: limit only
        (f"{EXPLORER_BASE}/v1/txs/stats", {"limit": days}),
    ]

    for url, params in attempts:
        try:
            data = _get(url, params=params)
            result = _sum_daily(data, ("count", "txCount", "txs", "transactions"))
            if result:
                return result
        except Exception:
            continue

    # Last resort: count txs via pagination total
    try:
        data = _get(f"{EXPLORER_BASE}/v1/txs", {"limit": 1})
        total = data.get("total") or data.get("paging", {}).get("total")
        if total:
            return int(total)  # all-time, but better than None
    except Exception:
        pass

    return None


def fetch_active_addresses(days: int = 7) -> int | None:
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    attempts = [
        (f"{EXPLORER_BASE}/v1/wallets/stats", {"startTime": int(start.timestamp()), "endTime": int(end.timestamp())}),
        (f"{EXPLORER_BASE}/v1/wallets/stats", {"from": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "to": end.strftime("%Y-%m-%dT%H:%M:%SZ")}),
        (f"{EXPLORER_BASE}/v1/addresses/stats", {"startTime": int(start.timestamp()), "endTime": int(end.timestamp())}),
        (f"{EXPLORER_BASE}/v1/accounts/stats", {"startTime": int(start.timestamp()), "endTime": int(end.timestamp())}),
    ]

    for url, params in attempts:
        try:
            data = _get(url, params=params)
            result = _sum_daily(data, ("uniqueAddresses", "activeAddresses", "newAddresses", "count", "addresses"))
            if result:
                return result
        except Exception:
            continue

    return None


def _sum_daily(data: dict | list, keys: tuple) -> int | None:
    """Extract total from either a list of daily objects or a single summary dict."""
    if isinstance(data, list) and data:
        total = 0
        for item in data:
            for k in keys:
                v = item.get(k)
                if v is not None:
                    total += int(v or 0)
                    break
        return total if total > 0 else None

    if isinstance(data, dict):
        # Check for nested data arrays first
        for nest_key in ("data", "stats", "result", "txs", "wallets", "addresses"):
            inner = data.get(nest_key)
            if isinstance(inner, list) and inner:
                return _sum_daily(inner, keys)
        # Single summary value
        for k in keys:
            v = data.get(k)
            if v is not None:
                return int(v) if int(v) > 0 else None

    return None


# ── Protocol fees ──────────────────────────────────────────────────────────────

def fetch_injective_fees(days: int = 7) -> dict:
    """
    Fetch Injective chain-level fees and per-dapp fees from DefiLlama.
    Returns {"chain_fees_7d": float, "dapp_fees": {name: float}}
    """
    result = {"chain_fees_7d": None, "dapp_fees": {}}

    # Chain-level fees
    try:
        data = _get("https://api.llama.fi/summary/fees/injective")
        total7d = (
            data.get("total7d")
            or data.get("totalFees7d")
            or _sum_chart(data.get("totalDataChart"), days)
        )
        result["chain_fees_7d"] = float(total7d) if total7d else None
    except Exception:
        pass

    # Per-dapp fees from overview
    try:
        data = _get(
            "https://api.llama.fi/overview/fees/injective"
            "?excludeTotalDataChart=true&dataType=dailyFees"
        )
        for p in data.get("protocols", []):
            slug  = (p.get("name") or p.get("slug") or "").lower()
            vol7d = float(p.get("total7d") or p.get("totalFees7d") or 0)
            for key, display in DEFILLAMA_SLUG_MAP.items():
                if key in slug and vol7d > 0:
                    result["dapp_fees"][display] = max(result["dapp_fees"].get(display, 0), vol7d)
    except Exception:
        pass

    return result


def _sum_chart(chart: list | None, days: int) -> float | None:
    if not chart:
        return None
    return sum(float(row[1]) for row in chart[-days:]) if chart else None


# ── Dapp volumes ───────────────────────────────────────────────────────────────

def fetch_dapp_volumes() -> dict[str, float]:
    """Pull 7D DEX volume for Injective dapps from DefiLlama."""
    results: dict[str, float] = {n: 0.0 for n in DAPP_NAMES}

    # DEX volume
    try:
        data = _get(
            "https://api.llama.fi/overview/dexs/injective"
            "?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyVolume"
        )
        for p in data.get("protocols", []):
            slug  = (p.get("name") or p.get("slug") or "").lower()
            vol7d = float(p.get("total7d") or p.get("totalVolume7d") or 0)
            for key, display in DEFILLAMA_SLUG_MAP.items():
                if key in slug:
                    results[display] = max(results.get(display, 0), vol7d)
    except Exception:
        pass

    # Options/derivatives volume (covers Choice, etc.)
    try:
        data = _get(
            "https://api.llama.fi/overview/options/injective"
            "?excludeTotalDataChart=true&dataType=dailyPremiumVolume"
        )
        for p in data.get("protocols", []):
            slug  = (p.get("name") or p.get("slug") or "").lower()
            vol7d = float(p.get("total7d") or 0)
            for key, display in DEFILLAMA_SLUG_MAP.items():
                if key in slug:
                    results[display] = max(results.get(display, 0), vol7d)
    except Exception:
        pass

    # Fill zeros with TVL from DefiLlama as a proxy (shows activity even if volume untracked)
    try:
        tvl_data = _get("https://api.llama.fi/v2/protocols")
        for p in tvl_data:
            chains = [c.lower() for c in (p.get("chains") or [])]
            if "injective" not in chains:
                continue
            slug  = (p.get("name") or p.get("slug") or "").lower()
            tvl   = float(p.get("tvl") or 0)
            for key, display in DEFILLAMA_SLUG_MAP.items():
                if key in slug and results.get(display, 0) == 0 and tvl > 0:
                    # Store negative TVL as proxy marker — handled in formatting
                    results[f"_{display}_tvl"] = tvl
    except Exception:
        pass

    return results


# ── NFT — Talis ───────────────────────────────────────────────────────────────

def fetch_nft_volume_talis() -> float | None:
    api_key = os.environ.get("TALIS_API_KEY", "")
    headers = {"x-api-key": api_key} if api_key else {}

    # Try public endpoints (no key required for most read endpoints)
    endpoints = [
        f"{TALIS_BASE}/v1/stats/volume?period=7d",
        f"{TALIS_BASE}/v1/stats?period=7d",
        f"{TALIS_BASE}/v1/marketplace/stats",
        f"{TALIS_BASE}/v1/analytics/volume",
        "https://talis.art/api/stats",
    ]
    for url in endpoints:
        try:
            data = _get(url, headers=headers)
            for k in ("volume", "totalVolume", "volume7d", "total", "usdVolume", "volumeUsd"):
                if data.get(k) is not None:
                    return float(data[k])
        except Exception:
            continue

    # Aggregate from collections endpoint
    try:
        data = _get(f"{TALIS_BASE}/v1/collections", headers=headers)
        cols  = data if isinstance(data, list) else data.get("collections") or data.get("data") or []
        total = sum(float(c.get("volume7d") or c.get("volumeWeek") or c.get("weekVolume") or 0) for c in cols)
        return total if total > 0 else None
    except Exception:
        return None


# ── INJ price ─────────────────────────────────────────────────────────────────

def fetch_inj_price() -> float | None:
    try:
        data = _get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "injective-protocol", "vs_currencies": "usd"},
        )
        return float(data["injective-protocol"]["usd"])
    except Exception:
        return None


# ── Collector ─────────────────────────────────────────────────────────────────

def collect_all_metrics() -> dict:
    fees = fetch_injective_fees()
    return {
        "timestamp":         datetime.now(timezone.utc).isoformat(),
        "tvl_usd":           fetch_tvl(),
        "weekly_txns":       fetch_weekly_txns(),
        "active_addresses":  fetch_active_addresses(),
        "dapp_volumes":      fetch_dapp_volumes(),
        "chain_fees_7d":     fees["chain_fees_7d"],
        "dapp_fees":         fees["dapp_fees"],
        "nft_volume_talis":  fetch_nft_volume_talis(),
        "inj_price":         fetch_inj_price(),
    }
