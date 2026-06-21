#!/usr/bin/env python3
"""
Diagnostic probe — run in an environment WITH network access (your Codespace).

    python probe.py

It hits every candidate endpoint and prints status + key structure so we can
lock in the working ones for txns, active addresses, dapp stats and NFT volume.
Nothing is posted anywhere; this is read-only.
"""

import json
import requests
from datetime import datetime, timedelta, timezone

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) xINJ-probe/1.0"}
end   = datetime.now(timezone.utc)
start = end - timedelta(days=7)
S, E  = int(start.timestamp()), int(end.timestamp())


def probe(label, url, params=None, headers=None, show_keys=True, max_chars=600):
    hdrs = {**UA, **(headers or {})}
    print(f"\n{'='*70}\n{label}\n{url}\n  params={params}")
    try:
        r = requests.get(url, params=params, headers=hdrs, timeout=20)
        print(f"  HTTP {r.status_code}  ({len(r.content)} bytes)")
        if r.status_code != 200:
            print(f"  body: {r.text[:200]}")
            return
        try:
            data = r.json()
        except Exception:
            print(f"  non-JSON: {r.text[:200]}")
            return
        if isinstance(data, list):
            print(f"  -> list of {len(data)} items")
            if data:
                print(f"  first item keys: {list(data[0].keys()) if isinstance(data[0], dict) else type(data[0])}")
                print(f"  sample: {json.dumps(data[0])[:max_chars]}")
        elif isinstance(data, dict):
            print(f"  top-level keys: {list(data.keys())}")
            print(f"  sample: {json.dumps(data)[:max_chars]}")
    except Exception as e:
        print(f"  ERROR: {e}")


print("\n########## INJECTIVE EXPLORER — TXNS ##########")
for params in (
    {"startTime": S, "endTime": E},
    {"from": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "to": end.strftime("%Y-%m-%dT%H:%M:%SZ")},
    {"resolution": "1D"},
    None,
):
    probe("txs/stats", "https://explorer.injective.network/api/explorer/v1/txs/stats", params)
probe("txs (paging total)", "https://explorer.injective.network/api/explorer/v1/txs", {"limit": 1})

print("\n########## INJECTIVE EXPLORER — ADDRESSES ##########")
for path in ("wallets/stats", "addresses/stats", "accounts/stats", "bank/stats"):
    probe(path, f"https://explorer.injective.network/api/explorer/v1/{path}", {"startTime": S, "endTime": E})

print("\n########## INJSCAN / ALT EXPLORERS ##########")
probe("injscan summary", "https://injscan.com/api/v1/summary")
probe("blockscout stats", "https://blockscout.injective.network/api/v2/stats")

print("\n########## DEFILLAMA — DAPP TVL + VOLUME + FEES ##########")
probe("all protocols (filter Injective client-side)", "https://api.llama.fi/protocols")
probe("dexs overview", "https://api.llama.fi/overview/dexs/injective",
      {"excludeTotalDataChart": "true", "excludeTotalDataChartBreakdown": "true"})
probe("fees overview", "https://api.llama.fi/overview/fees/injective",
      {"excludeTotalDataChart": "true", "excludeTotalDataChartBreakdown": "true"})
probe("chain fees summary", "https://api.llama.fi/summary/fees/injective", {"dataType": "dailyFees"})

print("\n########## NFT — RARIBLE + TALIS ##########")
probe("rarible collections (INJECTIVE)", "https://api.rarible.org/v0.1/data/collections/all",
      {"blockchain": "INJECTIVE", "size": 5})
probe("talis stats/volume", "https://api.talis.art/v1/stats/volume", {"period": "7d"})
probe("talis marketplace stats", "https://api.talis.art/v1/marketplace/stats")
probe("talis collections", "https://api.talis.art/v1/collections")

print("\n\nDONE. Paste the full output back so the endpoints can be finalized.")
