#!/usr/bin/env python3
"""
Pipeline 06: Export results.
- Reads classified profiles
- Generates data/results.json (clean, formatted)
- Generates data/results.csv (flat table)
- Prints CLI summary with statistics
"""

import sys
import os
import json
import csv
from pathlib import Path
from datetime import datetime
from collections import Counter

# Fix paths for standalone or package execution
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    PROFILES_CLASSIFIED_FILE, PROFILES_SCORED_FILE,
    RESULTS_JSON_FILE, RESULTS_CSV_FILE, DATA_DIR,
)
from state import PipelineState


class C:
    G = '\033[92m'; Y = '\033[93m'; R = '\033[91m'; B = '\033[94m'
    D = '\033[90m'; W = '\033[97m'; H = '\033[95m'
    BOLD = '\033[1m'; END = '\033[0m'


def run():
    state = PipelineState()

    # Try classified first, fall back to scored
    source_file = PROFILES_CLASSIFIED_FILE
    if not source_file.exists():
        source_file = PROFILES_SCORED_FILE
        if not source_file.exists():
            print(f"  {C.R}✗ No scored or classified profiles found.{C.END}")
            return

    profiles = json.loads(source_file.read_text())
    print(f"  {C.D}Source: {source_file.name} ({len(profiles)} profiles){C.END}")

    # Sort by signal strength
    profiles.sort(key=lambda p: p.get("signal_strength", 0), reverse=True)

    # --- Generate results.json ---
    results = []
    for p in profiles:
        score_breakdown = p.get("score_breakdown", {})
        classification = p.get("classification", {})

        result = {
            "rank": len(results) + 1,
            "handle": p.get("handle"),
            "display_name": p.get("display_name"),
            "bio": p.get("bio"),
            "profile_url": p.get("profile_url"),
            "followers_count": p.get("followers_count"),
            "following_count": p.get("following_count"),
            "tweet_count": p.get("tweet_count"),
            "verified": p.get("verified"),
            "location": p.get("location"),
            "website": p.get("website"),
            "last_active": p.get("last_active"),
            "last_active_str": p.get("last_active_str"),
            "days_since_active": p.get("days_since_active"),
            "signal_strength": p.get("signal_strength", 0),
            "score_breakdown": {
                "llm_eval": score_breakdown.get("llm_eval", 0),
                "llm_reasoning": score_breakdown.get("llm_reasoning", ""),
                "semantic": score_breakdown.get("semantic", 0),
                "technical": score_breakdown.get("technical", 0),
                "technical_keywords": score_breakdown.get("technical_keywords", []),
                "tweet_engagement": score_breakdown.get("tweet_engagement", 0),
                "links": score_breakdown.get("links", 0),
                "profile_completeness": score_breakdown.get("profile_completeness", 0),
            },
            "classification": {
                "llm_category": classification.get("llm_category", "Unknown"),
                "llm_confidence": classification.get("llm_confidence", 0),
                "llm_reasoning": classification.get("llm_reasoning", ""),
                "semantic_top_category": classification.get("semantic_top_category", "Unknown"),
                "semantic_scores": classification.get("semantic_scores", {}),
            },
            "posts_count": len(p.get("posts", [])),
            "has_shipping_signals": p.get("has_shipping_signals", False),
            "shipping_keywords": p.get("shipping_keywords", []),
            "extracted_links": p.get("extracted_links", []),
            "discovered_at": p.get("discovered_at"),
            "source_topic": p.get("source_topic"),
        }
        results.append(result)

    # Save JSON
    DATA_DIR.mkdir(exist_ok=True)
    with open(RESULTS_JSON_FILE, "w") as f:
        json.dump({
            "generated_at": datetime.utcnow().isoformat(),
            "total_profiles": len(results),
            "profiles": results,
        }, f, indent=2, default=str)

    # --- Generate results.csv ---
    csv_headers = [
        "rank", "handle", "display_name", "signal_strength",
        "llm_category", "llm_confidence", "semantic_top_category",
        "followers_count", "following_count", "days_since_active", "last_active_str",
        "llm_eval_score", "semantic_score", "technical_score",
        "tweet_engagement_score", "links_score", "profile_completeness_score",
        "bio", "website", "location", "posts_count",
        "has_shipping_signals", "shipping_keywords",
        "extracted_links_count", "profile_url",
        "llm_reasoning", "source_topic",
    ]

    with open(RESULTS_CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers)
        writer.writeheader()

        for r in results:
            sb = r.get("score_breakdown", {})
            cl = r.get("classification", {})
            writer.writerow({
                "rank": r["rank"],
                "handle": r["handle"],
                "display_name": r.get("display_name", ""),
                "signal_strength": r.get("signal_strength", 0),
                "llm_category": cl.get("llm_category", ""),
                "llm_confidence": cl.get("llm_confidence", 0),
                "semantic_top_category": cl.get("semantic_top_category", ""),
                "followers_count": r.get("followers_count", ""),
                "following_count": r.get("following_count", ""),
                "days_since_active": r.get("days_since_active", ""),
                "last_active_str": r.get("last_active_str", ""),
                "llm_eval_score": sb.get("llm_eval", 0),
                "semantic_score": sb.get("semantic", 0),
                "technical_score": sb.get("technical", 0),
                "tweet_engagement_score": sb.get("tweet_engagement", 0),
                "links_score": sb.get("links", 0),
                "profile_completeness_score": sb.get("profile_completeness", 0),
                "bio": (r.get("bio", "") or "")[:200],
                "website": r.get("website", ""),
                "location": r.get("location", ""),
                "posts_count": r.get("posts_count", 0),
                "has_shipping_signals": r.get("has_shipping_signals", False),
                "shipping_keywords": ", ".join(r.get("shipping_keywords", [])),
                "extracted_links_count": len(r.get("extracted_links", [])),
                "profile_url": r.get("profile_url", ""),
                "llm_reasoning": sb.get("llm_reasoning", ""),
                "source_topic": r.get("source_topic", ""),
            })

    # Mark as exported
    for p in profiles:
        state.mark_processed(p["handle"], "exported")
    state.save()

    # --- Print Summary ---
    scores = [r["signal_strength"] for r in results]
    avg_score = sum(scores) / max(1, len(scores))

    category_dist = Counter(r["classification"]["llm_category"] for r in results)

    print(f"\n  {C.G}{'═' * 50}{C.END}")
    print(f"  {C.G}✓ Export complete{C.END}")
    print(f"    Total profiles: {len(results)}")
    print(f"    Avg score:      {avg_score:.1f}/100")
    if scores:
        print(f"    Score range:    {min(scores):.1f} – {max(scores):.1f}")

    print(f"\n  {C.BOLD}Classification Distribution:{C.END}")
    for cat, count in category_dist.most_common():
        pct = count / max(1, len(results)) * 100
        bar = "█" * min(30, int(pct / 3))
        print(f"    {cat:<22} {count:>3} ({pct:.0f}%)  {bar}")

    print(f"\n  {C.BOLD}Top 10 Profiles:{C.END}")
    for r in results[:10]:
        cat = r["classification"]["llm_category"]
        cat_short = {
            "Early-stage founder": f"{C.G}FOUNDER{C.END}",
            "AI researcher": f"{C.B}RESEARCHER{C.END}",
            "AI operator": f"{C.Y}OPERATOR{C.END}",
            "Angel investor": f"{C.H}INVESTOR{C.END}",
            "Noise/others": f"{C.D}NOISE{C.END}",
        }.get(cat, cat)
        print(f"    #{r['rank']:>2}  @{r['handle']:<20} Score: {r['signal_strength']:>5.1f}  {cat_short}")

    print(f"\n  {C.W}Files:{C.END}")
    print(f"    JSON: {RESULTS_JSON_FILE}")
    print(f"    CSV:  {RESULTS_CSV_FILE}")


if __name__ == "__main__":
    run()
