#!/usr/bin/env python3
"""
Mention reply bot entry point.

Usage:
    python mention_reply.py           # live run
    python mention_reply.py --dry-run # print replies without posting
"""

import argparse
from src.mention_bot import run_mention_bot

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run_mention_bot(dry_run=args.dry_run)
