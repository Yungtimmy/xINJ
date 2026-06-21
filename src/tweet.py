"""
Post the weekly stats thread to X via Tweepy v4 (API v2).
"""

from __future__ import annotations
import os
from pathlib import Path
import tweepy

DAPP_ORDER = ["Helix", "Mito", "Hydro", "DojoSwap", "Black Panther", "Neptune", "Choice"]


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
    p          = prev or {}
    price      = metrics.get("inj_price")
    tvl        = metrics.get("tvl_usd")
    dex_vol    = metrics.get("dex_volume_7d")
    fees       = metrics.get("chain_fees_7d")
    revenue    = metrics.get("chain_revenue_7d")
    txns       = metrics.get("weekly_txns")
    addrs      = metrics.get("active_addresses")
    nft_vol    = metrics.get("nft_volume")
    dapp_stats = metrics.get("dapp_stats") or {}
    prev_dapps = p.get("dapp_stats") or {}

    # ── Tweet 1: Headline numbers ─────────────────────────────────────────────
    head_lines = [
        f"INJ Price: {'$' + f'{price:.2f}' if price else 'N/A'}{_arrow(price, p.get('inj_price'))}",
        f"TVL: {_fmt(tvl)}{_arrow(tvl, p.get('tvl_usd'))}",
        f"DEX Vol (7D): {_fmt(dex_vol)}{_arrow(dex_vol, p.get('dex_volume_7d'))}",
    ]
    if nft_vol is not None:
        head_lines.append(f"NFT Vol (7D): {_fmt(nft_vol)}{_arrow(nft_vol, p.get('nft_volume'))}")
    tweet1 = (
        f"🔥 Injective Weekly Ecosystem Stats — {week_label}\n\n"
        + "\n".join(head_lines)
        + "\n\nFull breakdown 👇 #Injective #INJ #DeFi"
    )

    # ── Tweet 2: DeFi activity (only lines we actually have data for) ──────────
    act_lines = [
        f"💸 Chain Fees: {_fmt(fees)}{_arrow(fees, p.get('chain_fees_7d'))}",
        f"🔥 Revenue (burn): {_fmt(revenue)}{_arrow(revenue, p.get('chain_revenue_7d'))}",
    ]
    if txns is not None:
        act_lines.append(f"🔁 Transactions: {_fmt(txns, '')}{_arrow(txns, p.get('weekly_txns'))}")
    if addrs is not None:
        act_lines.append(f"👛 Active Addresses: {_fmt(addrs, '')}{_arrow(addrs, p.get('active_addresses'))}")
    tweet2 = "📊 DeFi Activity (7 days)\n\n" + "\n".join(act_lines)

    # ── Tweet 3: Dapp leaderboard (ranked by TVL) ─────────────────────────────
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣"]
    ranked = sorted(
        DAPP_ORDER,
        key=lambda n: (dapp_stats.get(n) or {}).get("tvl", 0),
        reverse=True,
    )
    lines = []
    for i, name in enumerate(ranked[:7]):
        s        = dapp_stats.get(name) or {}
        tvl_v    = s.get("tvl", 0)
        prev_tvl = (prev_dapps.get(name) or {}).get("tvl")
        # Show volume in parentheses when the dapp actually has DEX volume
        vol_v    = s.get("volume_7d", 0)
        extra    = f" · vol {_fmt(vol_v)}" if vol_v else ""
        chg      = _arrow(tvl_v if tvl_v else None, prev_tvl)
        label    = _fmt(tvl_v) if tvl_v else "–"
        lines.append(f"{medals[i]} {name}: {label} TVL{extra}{chg}")

    tweet3 = "🏆 Top Dapps by TVL (7D Δ)\n\n" + "\n".join(lines)

    return [tweet1, tweet2, tweet3]


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
