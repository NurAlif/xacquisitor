#!/usr/bin/env python3
"""
Pipeline 03: Filter profiles.
- Drop profiles with >= 10,000 followers
- Drop profiles inactive > 25 days
- Logs dropped profiles with reasons
- Saves passing profiles to data/profiles_filtered.json
"""

import sys
import os
import json
from pathlib import Path

# Fix paths for standalone or package execution
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    PROFILES_ENRICHED_FILE, PROFILES_FILTERED_FILE,
    MAX_FOLLOWERS, MAX_INACTIVE_DAYS, DATA_DIR,
)
from state import PipelineState


class C:
    G = '\033[92m'; Y = '\033[93m'; R = '\033[91m'; B = '\033[94m'
    D = '\033[90m'; W = '\033[97m'; BOLD = '\033[1m'; END = '\033[0m'


def apply_filters(profiles: list) -> tuple:
    """
    Apply filtering rules. Returns (passed, dropped_with_reasons).
    """
    passed = []
    dropped = []

    for p in profiles:
        handle = p.get("handle", "?")
        reasons = []

        # Check followers
        followers = p.get("followers_count")
        if followers is not None and followers >= MAX_FOLLOWERS:
            reasons.append(f"followers={followers} (max {MAX_FOLLOWERS})")

        # Check activity
        days_inactive = p.get("days_since_active")
        if days_inactive is not None and days_inactive > MAX_INACTIVE_DAYS:
            reasons.append(f"inactive {days_inactive}d (max {MAX_INACTIVE_DAYS}d)")
        elif days_inactive is None:
            # If we have no activity data, check if we have posts
            if not p.get("posts"):
                reasons.append("no posts/activity data")

        if reasons:
            dropped.append({"handle": handle, "reasons": reasons})
        else:
            passed.append(p)

    return passed, dropped


def run():
    state = PipelineState()

    if not PROFILES_ENRICHED_FILE.exists():
        print(f"  {C.R}✗ No enriched profiles found. Run enrichment pipeline first.{C.END}")
        return

    enriched = json.loads(PROFILES_ENRICHED_FILE.read_text())
    print(f"  {C.D}Enriched profiles: {len(enriched)}{C.END}")

    print(f"\n  {C.BOLD}Filter criteria:{C.END}")
    print(f"    • Drop if followers >= {MAX_FOLLOWERS:,}")
    print(f"    • Drop if inactive > {MAX_INACTIVE_DAYS} days")
    print(f"    • Drop if no posts/activity data")

    # Apply filters
    passed, dropped = apply_filters(enriched)

    # Print dropped profiles
    if dropped:
        print(f"\n  {C.R}Dropped ({len(dropped)}):{C.END}")
        for d in dropped:
            print(f"    ✗ @{d['handle']}: {', '.join(d['reasons'])}")

    # Update state
    for p in passed:
        state.mark_processed(p["handle"], "filtered")

    # Save
    DATA_DIR.mkdir(exist_ok=True)
    with open(PROFILES_FILTERED_FILE, "w") as f:
        json.dump(passed, f, indent=2, default=str)

    state.save()

    print(f"\n  {C.G}{'═' * 40}{C.END}")
    print(f"  {C.G}✓ Filtering complete{C.END}")
    print(f"    Input:   {len(enriched)} profiles")
    print(f"    Passed:  {C.G}{len(passed)}{C.END}")
    print(f"    Dropped: {C.R}{len(dropped)}{C.END}")
    print(f"    Saved to: {PROFILES_FILTERED_FILE}")


if __name__ == "__main__":
    run()
