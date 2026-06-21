"""
Polls X mentions and auto-replies to Injective-related tweets.
Run via GitHub Actions every 30 minutes.
"""

from __future__ import annotations
import json, os, re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import tweepy

LAST_SEEN_FILE = Path(os.environ.get("LAST_SEEN_FILE", "data/last_seen_id.txt"))

INJ_KEYWORDS = re.compile(
    r"\b(injective|inj\b|helix|mito|hydro|dojoswap|talis|neptune|"
    r"black\s?panther|choice\s?(dapp|market)|dojo|xinj)\b",
    re.IGNORECASE,
)

QUICK_STATS_KEYWORDS = re.compile(
    r"\b(price|tvl|volume|stats|apy|fees|txns?|transactions?|how much|wen|pump|bullish)\b",
    re.IGNORECASE,
)


def _client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
        wait_on_rate_limit=True,
    )


def _load_last_seen() -> str | None:
    if LAST_SEEN_FILE.exists():
        return LAST_SEEN_FILE.read_text().strip() or None
    return None


def _save_last_seen(tweet_id: str) -> None:
    LAST_SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_SEEN_FILE.write_text(tweet_id)


def _get_bot_user_id(client: tweepy.Client) -> str:
    me = client.get_me()
    return str(me.data.id)


def _build_reply(tweet_text: str, author_name: str, metrics: dict | None) -> str | None:
    """Return a reply string or None if we should skip this mention."""
    if not INJ_KEYWORDS.search(tweet_text):
        return None

    # If they're asking about stats/price, give a quick snapshot
    if QUICK_STATS_KEYWORDS.search(tweet_text) and metrics:
        price   = metrics.get("inj_price")
        tvl     = metrics.get("tvl_usd")
        fees    = metrics.get("chain_fees_7d")
        p_str   = f"${price:.2f}" if price else "N/A"
        tvl_str = _fmt(tvl)
        fee_str = _fmt(fees)

        return (
            f"Here's a quick Injective snapshot 📊\n\n"
            f"INJ: {p_str}\n"
            f"TVL: {tvl_str}\n"
            f"Chain Fees (7D): {fee_str}\n\n"
            f"Full weekly stats drop every Monday 🔥 #Injective"
        )

    # Generic Injective engagement reply
    return (
        f"Injective is cooking 🔥 "
        f"Follow for weekly on-chain stats every Monday — "
        f"TVL, volume, top dapps & more. #Injective #INJ"
    )


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


def _load_latest_metrics() -> dict | None:
    history_file = Path(os.environ.get("HISTORY_FILE", "data/history.json"))
    if not history_file.exists():
        return None
    try:
        records = json.loads(history_file.read_text())
        return records[-1] if records else None
    except Exception:
        return None


def run_mention_bot(dry_run: bool = False) -> None:
    client      = _client()
    bot_user_id = _get_bot_user_id(client)
    last_seen   = _load_last_seen()
    metrics     = _load_latest_metrics()

    # Fetch recent mentions (up to 100, since last seen ID)
    kwargs: dict = {
        "id": bot_user_id,
        "max_results": 100,
        "tweet_fields": ["author_id", "text", "created_at", "conversation_id"],
        "expansions": ["author_id"],
        "user_fields": ["username", "name"],
    }
    if last_seen:
        kwargs["since_id"] = last_seen

    try:
        response = client.get_users_mentions(**kwargs)
    except tweepy.TweepyException as e:
        print(f"Error fetching mentions: {e}")
        return

    if not response.data:
        print("No new mentions.")
        return

    # Build a user lookup from expansions
    users = {str(u.id): u for u in (response.includes or {}).get("users", [])}

    newest_id = str(response.data[0].id)
    replied   = 0

    for tweet in reversed(response.data):  # oldest first
        author    = users.get(str(tweet.author_id))
        author_name = author.username if author else "there"

        # Don't reply to ourselves
        if str(tweet.author_id) == bot_user_id:
            continue

        reply_text = _build_reply(tweet.text, author_name, metrics)
        if not reply_text:
            print(f"Skipping (not INJ-related): {tweet.text[:60]}")
            continue

        full_reply = f"@{author_name} {reply_text}"

        if dry_run:
            print(f"\n[DRY RUN] Would reply to @{author_name}:\n{full_reply}\n")
        else:
            try:
                client.create_tweet(
                    text=full_reply,
                    in_reply_to_tweet_id=str(tweet.id),
                )
                print(f"Replied to @{author_name}: {full_reply[:80]}...")
                replied += 1
            except tweepy.TweepyException as e:
                print(f"Failed to reply to @{author_name}: {e}")

    if not dry_run:
        _save_last_seen(newest_id)

    print(f"\nDone. {replied} replies sent. Latest mention ID: {newest_id}")
