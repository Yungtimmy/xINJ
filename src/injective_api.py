"""
Fetches weekly ecosystem metrics from Injective Explorer / Indexer APIs.
"""

import requests
from datetime import datetime, timedelta, timezone

EXPLORER_BASE = "https://explorer.injective.network/api/explorer"
INDEXER_BASE = "https://sentry.lcd.injective.network"


def _get(url: str, params: dict | None = None) -> dict:
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_chain_stats() -> dict:
    """Return overall chain stats from the explorer summary endpoint."""
    data = _get(f"{EXPLORER_BASE}/v1/dashboard")
    return data


def fetch_tvl() -> float | None:
    """
    Pull TVL from DefiLlama's Injective chain endpoint — more reliable than
    scraping the explorer for this specific number.
    """
    try:
        data = _get("https://api.llama.fi/v2/chains")
        for chain in data:
            if chain.get("name", "").lower() == "injective":
                return float(chain.get("tvl", 0))
    except Exception:
        return None
    return None


def fetch_weekly_tx_volume(days: int = 7) -> dict:
    """Fetch transaction counts over the last `days` days."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    params = {
        "startTime": int(start.timestamp()),
        "endTime": int(end.timestamp()),
    }
    try:
        data = _get(f"{EXPLORER_BASE}/v1/txs/stats", params=params)
        return data
    except Exception:
        return {}


def fetch_active_addresses(days: int = 7) -> int | None:
    """Fetch unique active address count from explorer stats."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    params = {
        "startTime": int(start.timestamp()),
        "endTime": int(end.timestamp()),
    }
    try:
        data = _get(f"{EXPLORER_BASE}/v1/wallets/stats", params=params)
        return data.get("uniqueAddresses") or data.get("total")
    except Exception:
        return None


def fetch_top_dapps(limit: int = 5) -> list[dict]:
    """Fetch top dapps by volume via the Injective indexer."""
    try:
        data = _get(
            f"{INDEXER_BASE}/injective/exchange/v1beta1/spot/markets",
            params={"market_status": "active"},
        )
        markets = data.get("markets", [])
        # Sort by volume if available, otherwise return first `limit`
        sorted_markets = sorted(
            markets,
            key=lambda m: float(m.get("volume", 0)),
            reverse=True,
        )
        return sorted_markets[:limit]
    except Exception:
        return []


def fetch_new_contracts(days: int = 7) -> int | None:
    """Fetch number of new smart contracts deployed in the last `days` days."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    params = {
        "startTime": int(start.timestamp()),
        "endTime": int(end.timestamp()),
    }
    try:
        data = _get(f"{EXPLORER_BASE}/v1/contracts/stats", params=params)
        return data.get("count") or data.get("total")
    except Exception:
        return None


def fetch_inj_price() -> float | None:
    """Get current INJ price from CoinGecko."""
    try:
        data = _get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "injective-protocol", "vs_currencies": "usd"},
        )
        return float(data["injective-protocol"]["usd"])
    except Exception:
        return None


def collect_all_metrics() -> dict:
    """Collect every metric we need; None means the source was unavailable."""
    chain_stats = fetch_chain_stats()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tvl_usd": fetch_tvl(),
        "tx_volume": fetch_weekly_tx_volume(),
        "active_addresses": fetch_active_addresses(),
        "top_dapps": fetch_top_dapps(),
        "new_contracts": fetch_new_contracts(),
        "inj_price": fetch_inj_price(),
        "chain_stats": chain_stats,
    }
