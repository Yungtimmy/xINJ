"""
Fetches weekly ecosystem metrics from Injective Explorer / Indexer APIs + Talis NFT.
"""

import os
import requests
from datetime import datetime, timedelta, timezone

EXPLORER_BASE = "https://explorer.injective.network/api/explorer"
INDEXER_BASE  = "https://sentry.lcd.injective.network"
TALIS_BASE    = "https://api.talis.art"

# Known Injective dapp subaccount / contract identifiers for volume lookup
DAPPS = {
    "Helix":        {"type": "exchange", "slug": "helix"},
    "Mito":         {"type": "contract", "slug": "mito"},
    "Hydro":        {"type": "contract", "slug": "hydro"},
    "DojoSwap":     {"type": "contract", "slug": "dojoswap"},
    "Black Panther":{"type": "contract", "slug": "blackpanther"},
    "Neptune":      {"type": "contract", "slug": "neptune"},
}


def _get(url: str, params: dict | None = None, headers: dict | None = None) -> dict | list:
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_tvl() -> float | None:
    try:
        for chain in _get("https://api.llama.fi/v2/chains"):
            if chain.get("name", "").lower() == "injective":
                return float(chain.get("tvl", 0))
    except Exception:
        return None


def fetch_weekly_txns(days: int = 7) -> int | None:
    """
    Sum daily tx counts from the explorer stats endpoint.
    The endpoint returns a list of {date, count} objects.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    params = {"startTime": int(start.timestamp()), "endTime": int(end.timestamp())}
    try:
        data = _get(f"{EXPLORER_BASE}/v1/txs/stats", params=params)
        # Handle both list-of-daily and single-object responses
        if isinstance(data, list):
            return sum(int(d.get("count", 0) or d.get("txCount", 0) or 0) for d in data)
        if isinstance(data, dict):
            # Try nested data key
            inner = data.get("data") or data.get("txs") or []
            if isinstance(inner, list):
                return sum(int(d.get("count", 0) or d.get("txCount", 0) or 0) for d in inner)
            return int(data.get("count") or data.get("total") or data.get("txCount") or 0) or None
    except Exception:
        return None


def fetch_active_addresses(days: int = 7) -> int | None:
    """
    Sum daily unique address counts from the explorer wallet stats endpoint.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    params = {"startTime": int(start.timestamp()), "endTime": int(end.timestamp())}
    try:
        data = _get(f"{EXPLORER_BASE}/v1/wallets/stats", params=params)
        if isinstance(data, list):
            # Sum daily unique counts — deduplicated total won't be available, use max as proxy
            return sum(int(d.get("newAddresses", d.get("count", 0)) or 0) for d in data)
        if isinstance(data, dict):
            inner = data.get("data") or data.get("wallets") or []
            if isinstance(inner, list):
                return sum(int(d.get("newAddresses", d.get("count", 0)) or 0) for d in inner)
            for key in ("uniqueAddresses", "activeAddresses", "total", "count"):
                v = data.get(key)
                if v:
                    return int(v)
    except Exception:
        return None


def fetch_dapp_volumes(days: int = 7) -> dict[str, float]:
    """
    Pull 7-day volume for top Injective dapps via DefiLlama dex volume API.
    Falls back to zeros for dapps not listed on DefiLlama.
    """
    results: dict[str, float] = {name: 0.0 for name in DAPPS}

    # DefiLlama dex overview — covers Helix, DojoSwap, Mito etc.
    try:
        data = _get("https://api.llama.fi/overview/dexs/injective?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyVolume")
        protocols = data.get("protocols", [])
        name_map = {
            "helix":       "Helix",
            "dojoswap":    "DojoSwap",
            "mito":        "Mito",
            "neptune":     "Neptune",
            "hydro":       "Hydro",
            "black panther":"Black Panther",
        }
        for p in protocols:
            slug = (p.get("name") or p.get("slug") or "").lower()
            for key, display in name_map.items():
                if key in slug:
                    # sum7d field gives 7-day total directly
                    vol = float(p.get("total7d") or p.get("totalVolume7d") or 0)
                    results[display] = max(results.get(display, 0), vol)
    except Exception:
        pass

    return results


def fetch_nft_volume_talis(days: int = 7) -> float | None:
    """
    Fetch 7-day NFT trading volume from Talis Protocol API.
    Set TALIS_API_KEY env var if the endpoint requires auth.
    """
    api_key = os.environ.get("TALIS_API_KEY", "")
    headers = {"x-api-key": api_key} if api_key else {}
    try:
        # Primary endpoint — adjust path if Talis updates their API
        data = _get(f"{TALIS_BASE}/v1/stats/volume", params={"period": "7d"}, headers=headers)
        for key in ("volume", "totalVolume", "total", "usdVolume"):
            if data.get(key) is not None:
                return float(data[key])
    except Exception:
        pass

    # Fallback: collection stats aggregation
    try:
        data = _get(f"{TALIS_BASE}/v1/collections/stats", headers=headers)
        collections = data if isinstance(data, list) else data.get("collections", [])
        total = sum(float(c.get("volume7d") or c.get("volumeWeek") or 0) for c in collections)
        return total if total > 0 else None
    except Exception:
        return None


def fetch_inj_price() -> float | None:
    try:
        data = _get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "injective-protocol", "vs_currencies": "usd"},
        )
        return float(data["injective-protocol"]["usd"])
    except Exception:
        return None


def collect_all_metrics() -> dict:
    return {
        "timestamp":        datetime.now(timezone.utc).isoformat(),
        "tvl_usd":          fetch_tvl(),
        "weekly_txns":      fetch_weekly_txns(),
        "active_addresses": fetch_active_addresses(),
        "dapp_volumes":     fetch_dapp_volumes(),
        "nft_volume_talis": fetch_nft_volume_talis(),
        "inj_price":        fetch_inj_price(),
    }
