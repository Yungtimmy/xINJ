"""
Post the weekly stats thread to X via Tweepy v4 (API v2).
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
    auth = tweepy.OAuth1UserHandler(
        os.environ["X_API_KEY"], os.environ["X_API_SECRET"],
        os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_SECRET"],
    )
    return tweepy.API(auth)


def _fmt(v: float | None, prefix: str = "$") -> str:
    if v is None:
        return "N/A"
    if v >= 1_000_000_000:
        return f"{prefix}{v / 1e9:.2f}B"
    if v >= 1_000_000:
        return f"{prefix}{v / 1e6:.2f}M"
    if v >= 1_000:
        return f"{prefix}{v / 1e3:.1f}K"
    return f"{prefix}{v:,.0f}"


def _arrow(cur: float | None, prv: float | None) -> str:
    if cur is None or prv is None or prv == 0:
        return ""
    p = round((cur - prv) / abs(prv) * 100, 1)
    return f" 📈 +{p:.1f}%" if p >= 0 else f" 📉 {p:.1f}%"


def build_thread(metrics: dict, prev: dict | None, week_label: str) -> list[str]:
    p = prev or {}

    price      = metrics.get("inj_price")
    prev_price = p.get("inj_price")
    price_str  = f"${price:.2f}" if price else "N/A"

    tvl        = metrics.get("tvl_usd")
    txns       = metrics.get("weekly_txns")
    addrs      = metrics.get("active_addresses")
    nft_vol    = metrics.get("nft_volume_talis")

    dapp_vols  = metrics.get("dapp_volumes") or {}
    prev_vols  = p.get("dapp_volumes") or {}

    # Tweet 1 — headline
    tweet1 = (
        f"🔥 Injective Weekly Ecosystem Stats — {week_label}\n\n"
        f"INJ Price: {price_str}{_arrow(price, prev_price)}\n"
        f"TVL: {_fmt(tvl)}{_arrow(tvl, p.get('tvl_usd'))}\n"
        f"NFT Vol (Talis 7D): {_fmt(nft_vol)}{_arrow(nft_vol, p.get('nft_volume_talis'))}\n\n"
        f"Full breakdown 👇 #Injective #INJ #DeFi"
    )

    # Tweet 2 — on-chain activity
    tweet2 = (
        f"📊 On-chain activity (7 days)\n\n"
        f"Active Addresses: {_fmt(addrs, '')}{_arrow(addrs, p.get('active_addresses'))}\n"
        f"Total Transactions: {_fmt(txns, '')}{_arrow(txns, p.get('weekly_txns'))}"
    )

    # Tweet 3 — dapp leaderboard
    sorted_dapps = sorted(dapp_vols.items(), key=lambda x: x[1], reverse=True)
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣"]
    lines = []
    for i, (name, vol) in enumerate(sorted_dapps[:6]):
        chg = _arrow(vol if vol else None, prev_vols.get(name))
        lines.append(f"{medals[i]} {name}: {_fmt(vol)}{chg}")

    tweet3 = "🏆 Top Dapps — 7D Volume\n\n" + "\n".join(lines) if lines else None

    thread = [tweet1, tweet2]
    if tweet3:
        thread.append(tweet3)
    return thread


def post_thread(thread: list[str], image_path: Path | None = None) -> None:
    client   = _client()
    api      = _api_v1()

    media_id = None
    if image_path and Path(image_path).exists():
        media_id = api.media_upload(str(image_path)).media_id_string

    reply_to = None
    for i, text in enumerate(thread):
        kwargs: dict = {"text": text}
        if i == 0 and media_id:
            kwargs["media_ids"] = [media_id]
        if reply_to:
            kwargs["in_reply_to_tweet_id"] = reply_to
        reply_to = client.create_tweet(**kwargs).data["id"]
