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

# Match DefiLlama protocol names (lowercased) -> our display name.
# DefiLlama tracks these under different categories (DEX, Liquid Staking,
# Yield, Lending) so TVL is the one metric available for ALL of them.
DEFILLAMA_NAME_MATCH = {
    "helix":         "Helix",
    "dojoswap":      "DojoSwap",
    "mito":          "Mito",
    "neptune":       "Neptune",
    "hydro":         "Hydro",
    "black panther": "Black Panther",
    "blackpanther":  "Black Panther",
    "choice":        "Choice",
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


# ── Per-dapp stats: TVL (all dapps) + fees + volume where available ─────────────

def fetch_dapp_stats() -> dict[str, dict]:
    """
    Build per-dapp stats from DefiLlama's /protocols endpoint (TVL is the one
    metric tracked for ALL of them) and enrich with DEX volume + fees where
    DefiLlama has an adapter.

    Returns {display_name: {"tvl": float, "volume_7d": float, "fees_7d": float}}
    """
    stats: dict[str, dict] = {
        n: {"tvl": 0.0, "volume_7d": 0.0, "fees_7d": 0.0} for n in DAPP_NAMES
    }

    # 1. TVL for every Injective protocol — works for Hydro, Mito, DojoSwap, etc.
    try:
        protocols = _get("https://api.llama.fi/protocols")
        for p in protocols:
            chains = [c.lower() for c in (p.get("chains") or [])]
            if "injective" not in chains:
                continue
            name = (p.get("name") or "").lower()
            for key, display in DEFILLAMA_NAME_MATCH.items():
                if key in name:
                    # chainTvls.Injective is the Injective-specific slice; fall back to total tvl
                    inj_tvl = (p.get("chainTvls") or {}).get("Injective")
                    tvl = float(inj_tvl if inj_tvl is not None else (p.get("tvl") or 0))
                    stats[display]["tvl"] = max(stats[display]["tvl"], tvl)
    except Exception:
        pass

    # 2. DEX volume overview — only DEXs (Helix, DojoSwap) appear here
    try:
        data = _get(
            "https://api.llama.fi/overview/dexs/injective"
            "?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true"
        )
        for p in data.get("protocols", []):
            name  = (p.get("name") or "").lower()
            vol7d = float(p.get("total7d") or 0)
            for key, display in DEFILLAMA_NAME_MATCH.items():
                if key in name:
                    stats[display]["volume_7d"] = max(stats[display]["volume_7d"], vol7d)
    except Exception:
        pass

    # 3. Fees overview — covers more dapps (lending/yield earn fees)
    try:
        data = _get(
            "https://api.llama.fi/overview/fees/injective"
            "?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true"
        )
        for p in data.get("protocols", []):
            name  = (p.get("name") or "").lower()
            fee7d = float(p.get("total7d") or 0)
            for key, display in DEFILLAMA_NAME_MATCH.items():
                if key in name:
                    stats[display]["fees_7d"] = max(stats[display]["fees_7d"], fee7d)
    except Exception:
        pass

    return stats


def fetch_chain_fees(days: int = 7) -> float | None:
    """Injective chain-level 7D fees from DefiLlama."""
    for url in (
        "https://api.llama.fi/summary/fees/injective?dataType=dailyFees",
        "https://api.llama.fi/overview/fees/injective?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true",
    ):
        try:
            data = _get(url)
            total7d = data.get("total7d") or data.get("totalFees7d")
            if total7d:
                return float(total7d)
            chart = data.get("totalDataChart")
            if chart:
                return sum(float(row[1]) for row in chart[-days:])
        except Exception:
            continue
    return None


# ── NFT volume — Rarible (primary) + Talis (fallback) ───────────────────────────

def fetch_nft_volume(days: int = 7) -> float | None:
    """
    NFT 7D volume on Injective. Rarible has a documented multichain API
    (blockchain=INJECTIVE); Talis is tried as a fallback.
    """
    # Rarible — sum 7D volume across Injective collections
    rarible_key = os.environ.get("RARIBLE_API_KEY", "")
    r_headers   = {"X-API-KEY": rarible_key} if rarible_key else {}
    try:
        data = _get(
            "https://api.rarible.org/v0.1/data/collections/all",
            params={"blockchain": "INJECTIVE", "size": 50},
            headers=r_headers,
        )
        collections = data.get("collections") or data.get("data") or []
        total = 0.0
        for c in collections:
            cid = c.get("id") or c.get("address")
            if not cid:
                continue
            try:
                s = _get(
                    f"https://api.rarible.org/v0.1/data/collections/{cid}/statistics",
                    params={"currency": "USD"},
                    headers=r_headers,
                )
                vol = (s.get("volume") or {})
                total += float(vol.get("value7d") or vol.get("value") or 0)
            except Exception:
                continue
        if total > 0:
            return total
    except Exception:
        pass

    # Talis fallback (public read endpoints)
    talis_key = os.environ.get("TALIS_API_KEY", "")
    t_headers = {"x-api-key": talis_key} if talis_key else {}
    for url in (
        f"{TALIS_BASE}/v1/stats/volume?period=7d",
        f"{TALIS_BASE}/v1/marketplace/stats",
        "https://talis.art/api/stats",
    ):
        try:
            data = _get(url, headers=t_headers)
            for k in ("volume7d", "volume", "totalVolume", "usdVolume"):
                if data.get(k) is not None:
                    return float(data[k])
        except Exception:
            continue

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
    return {
        "timestamp":         datetime.now(timezone.utc).isoformat(),
        "tvl_usd":           fetch_tvl(),
        "weekly_txns":       fetch_weekly_txns(),
        "active_addresses":  fetch_active_addresses(),
        "dapp_stats":        fetch_dapp_stats(),
        "chain_fees_7d":     fetch_chain_fees(),
        "nft_volume":        fetch_nft_volume(),
        "inj_price":         fetch_inj_price(),
    }
