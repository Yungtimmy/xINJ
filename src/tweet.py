"""
Post the weekly stats thread to X (Twitter) via Tweepy v4 (API v2).
"""

from __future__ import annotations

import os
from pathlib import Path

import tweepy


def _client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
    )


def _api_v1() -> tweepy.API:
    """v1.1 auth needed for media upload."""
    auth = tweepy.OAuth1UserHandler(
        os.environ["X_API_KEY"],
        os.environ["X_API_SECRET"],
        os.environ["X_ACCESS_TOKEN"],
        os.environ["X_ACCESS_SECRET"],
    )
    return tweepy.API(auth)


def _fmt_large(value: float | None, prefix: str = "$") -> str:
    if value is None:
        return "N/A"
    if value >= 1_000_000_000:
        return f"{prefix}{value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{prefix}{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{prefix}{value / 1_000:.1f}K"
    return f"{prefix}{value:,.0f}"


def _pct_arrow(pct: float | None) -> str:
    if pct is None:
        return ""
    arrow = "📈" if pct >= 0 else "📉"
    sign = "+" if pct >= 0 else ""
    return f" {arrow} {sign}{pct:.1f}%"


def build_thread(metrics: dict, prev: dict | None, week_label: str) -> list[str]:
    def pct(key: str) -> float | None:
        from src.history import pct_change
        return pct_change(metrics.get(key), (prev or {}).get(key))

    def tx_count(m: dict | None) -> int | None:
        if not m:
            return None
        vol = m.get("tx_volume")
        if isinstance(vol, dict):
            return vol.get("count") or vol.get("total")
        return None

    price = metrics.get("inj_price")
    price_str = f"${price:.2f}" if price else "N/A"
    price_pct = _pct_arrow(
        None if not prev or not price or not prev.get("inj_price")
        else round((price - prev["inj_price"]) / prev["inj_price"] * 100, 1)
    )

    tvl = _fmt_large(metrics.get("tvl_usd"))
    tvl_pct = _pct_arrow(pct("tvl_usd"))

    addrs = _fmt_large(metrics.get("active_addresses"), prefix="")
    addrs_pct = _pct_arrow(pct("active_addresses"))

    txns = _fmt_large(tx_count(metrics), prefix="")
    prev_tx = tx_count(prev) if prev else None
    cur_tx = tx_count(metrics)
    txns_pct = _pct_arrow(
        None if cur_tx is None or prev_tx is None or prev_tx == 0
        else round((cur_tx - prev_tx) / prev_tx * 100, 1)
    )

    contracts = _fmt_large(metrics.get("new_contracts"), prefix="")
    contracts_pct = _pct_arrow(pct("new_contracts"))

    top_dapps = metrics.get("top_dapps", [])

    tweet1 = (
        f"🔥 Injective Weekly Ecosystem Stats — {week_label}\n\n"
        f"INJ Price: {price_str}{price_pct}\n"
        f"TVL: {tvl}{tvl_pct}\n\n"
        f"Full breakdown 👇 #Injective #INJ #DeFi"
    )

    tweet2 = (
        f"📊 On-chain activity (7 days)\n\n"
        f"Active Addresses: {addrs}{addrs_pct}\n"
        f"Total Transactions: {txns}{txns_pct}\n"
        f"New Smart Contracts: {contracts}{contracts_pct}"
    )

    dapp_lines = []
    for i, d in enumerate(top_dapps[:5], 1):
        name = d.get("ticker") or d.get("market_id", "")[:12]
        vol = _fmt_large(float(d.get("volume", 0) or 0))
        dapp_lines.append(f"{i}. {name} — {vol} vol")

    tweet3 = "🏆 Top Markets by Volume\n\n" + "\n".join(dapp_lines) if dapp_lines else None

    thread = [tweet1, tweet2]
    if tweet3:
        thread.append(tweet3)

    return thread


def post_thread(thread: list[str], image_path: Path | None = None) -> None:
    client = _client()
    api = _api_v1()

    media_id = None
    if image_path and image_path.exists():
        media = api.media_upload(str(image_path))
        media_id = media.media_id_string

    reply_to = None
    for i, text in enumerate(thread):
        kwargs: dict = {"text": text}
        if i == 0 and media_id:
            kwargs["media_ids"] = [media_id]
        if reply_to:
            kwargs["in_reply_to_tweet_id"] = reply_to

        resp = client.create_tweet(**kwargs)
        reply_to = resp.data["id"]
