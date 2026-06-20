#!/usr/bin/env python3
"""
Entry point for the weekly Injective stats bot.

Usage:
    python main.py              # full run: fetch → card → tweet → save
    python main.py --dry-run    # fetch + card but skip tweeting
    python main.py --card-only  # only generate the image, no tweet
"""

import argparse
import sys
from datetime import datetime, timezone

from src.history import last_snapshot, save_snapshot
from src.injective_api import collect_all_metrics
from src.stats_card import generate_card
from src.tweet import build_thread, post_thread


def week_label() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%b %d, %Y")


def main(dry_run: bool = False, card_only: bool = False) -> None:
    print("Fetching Injective metrics…")
    metrics = collect_all_metrics()

    prev = last_snapshot()
    label = week_label()

    print("Generating stats card…")
    card_path = generate_card(metrics, prev, label)
    print(f"Card saved: {card_path}")

    if card_only:
        print("--card-only mode: skipping tweet and history save.")
        return

    thread = build_thread(metrics, prev, label)

    if dry_run:
        print("\n--- DRY RUN: would post the following thread ---")
        for i, t in enumerate(thread, 1):
            print(f"\n[Tweet {i}]\n{t}")
        print(f"\n[Image] {card_path}")
        print("--- end dry run ---")
        return

    print("Posting to X…")
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
