#!/usr/bin/env python3
"""
Weekly Injective stats bot entry point.

Usage:
    python main.py              # full run: fetch -> card -> tweet -> save
    python main.py --dry-run    # fetch + card but skip tweeting
    python main.py --card-only  # generate image only
"""

import argparse
from datetime import datetime, timezone

from src.history import last_snapshot, save_snapshot
from src.injective_api import collect_all_metrics
from src.stats_card import generate_card
from src.tweet import build_thread, post_thread


def week_label() -> str:
    return datetime.now(timezone.utc).strftime("%b %d, %Y")


def main(dry_run: bool = False, card_only: bool = False) -> None:
    print("Fetching Injective metrics...")
    metrics = collect_all_metrics()

    print(f"  INJ Price:        {metrics.get('inj_price')}")
    print(f"  TVL:              {metrics.get('tvl_usd')}")
    print(f"  7D Txns:          {metrics.get('weekly_txns')}")
    print(f"  Active Addresses: {metrics.get('active_addresses')}")
    print(f"  NFT Vol (Talis):  {metrics.get('nft_volume_talis')}")
    print(f"  Dapp volumes:     {metrics.get('dapp_volumes')}")

    prev  = last_snapshot()
    label = week_label()

    print("\nGenerating stats card...")
    card_path = generate_card(metrics, prev, label)
    print(f"Card saved: {card_path}")

    if card_only:
        return

    thread = build_thread(metrics, prev, label)

    if dry_run:
        print("\n--- DRY RUN ---")
        for i, t in enumerate(thread, 1):
            print(f"\n[Tweet {i}]\n{t}")
        print(f"\n[Image] {card_path}")
        return

    print("\nPosting to X...")
    post_thread(thread, image_path=card_path)
    print("Posted successfully.")

    save_snapshot(metrics)
    print("Snapshot saved to history.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--card-only", action="store_true")
    args = parser.parse_args()
    main(dry_run=args.dry_run, card_only=args.card_only)
