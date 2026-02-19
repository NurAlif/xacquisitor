#!/usr/bin/env python3
"""
Pipeline 05: Classify profiles using dual approach.
1. LLM Classification — DeepSeek prompt with full context
2. Semantic Classification — Cosine similarity scoring per category

Categories: Early-stage founder, AI researcher, AI operator, Angel investor, Noise/others

10s interval between DeepSeek API calls.
Saves to data/profiles_classified.json
"""

import sys
import os
import json
import time
import math
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
from collections import Counter

# Fix paths for standalone or package execution
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    PROFILES_SCORED_FILE, PROFILES_CLASSIFIED_FILE, DATA_DIR,
    DEEPSEEK_KEY, DEEPSEEK_URL, DEEPSEEK_MODEL,
    CLASSIFICATION_CATEGORIES, LLM_REQUEST_INTERVAL,
)
from state import PipelineState


class C:
    G = '\033[92m'; Y = '\033[93m'; R = '\033[91m'; B = '\033[94m'
    D = '\033[90m'; W = '\033[97m'; H = '\033[95m'
    BOLD = '\033[1m'; END = '\033[0m'


# --- Semantic Classification Reference Embeddings ---
# Keyword clusters for each category (used for cosine-similarity-style scoring)
CATEGORY_KEYWORDS = {
    "Early-stage founder": {
        "high": [
            "founder", "co-founder", "ceo", "cto", "startup", "founding",
            "bootstrapping", "building in public", "pre-seed", "seed round",
            "mvp", "launched", "shipped", "revenue", "users", "customers",
            "yc", "y combinator", "techstars", "accelerator",
            "indie hacker", "solo founder", "first hire",
        ],
        "medium": [
            "product", "saas", "b2b", "b2c", "market", "pivot",
            "traction", "growth", "acquisition", "monetize",
            "pricing", "beta", "alpha", "waitlist", "early access",
            "building", "shipping", "deployed", "live",
        ],
        "low": [
            "team", "hiring", "culture", "vision", "mission",
            "innovation", "disrupt", "scale",
        ],
    },
    "AI researcher": {
        "high": [
            "phd", "research", "paper", "arxiv", "icml", "neurips", "aaai",
            "iclr", "cvpr", "acl", "publication", "cite", "thesis",
            "postdoc", "professor", "lab", "university",
            "novel architecture", "attention mechanism", "benchmark",
            "state-of-the-art", "sota", "ablation",
        ],
        "medium": [
            "experiment", "hypothesis", "model architecture", "training",
            "fine-tuning", "dataset", "evaluation", "metrics",
            "transformer", "diffusion", "reinforcement learning",
            "representation learning", "self-supervised",
            "generalization", "robustness", "interpretability",
        ],
        "low": [
            "deep learning", "machine learning", "neural network",
            "artificial intelligence", "compute", "gpu",
        ],
    },
    "AI operator": {
        "high": [
            "ml engineer", "ai engineer", "data scientist",
            "mlops", "model deployment", "inference", "serving",
            "production ml", "ml pipeline", "feature store",
            "monitoring", "a/b testing", "data pipeline",
            "vp engineering", "head of ai", "staff engineer",
        ],
        "medium": [
            "kubernetes", "docker", "aws", "gcp", "azure",
            "terraform", "ci/cd", "microservices",
            "api", "backend", "infrastructure", "devops",
            "scaling", "optimization", "latency", "throughput",
            "platform", "tooling", "sdk",
        ],
        "low": [
            "engineering", "software", "developer", "programmer",
            "code", "system", "architecture",
        ],
    },
    "Angel investor": {
        "high": [
            "angel investor", "angel", "investing in", "backed",
            "portfolio", "check size", "deal flow", "due diligence",
            "syndicate", "spv", "fund", "lp", "gp", "vc",
            "invested in", "announcing investment", "pre-seed investor",
        ],
        "medium": [
            "advisor", "board member", "mentor",
            "ecosystem", "community", "network",
            "exits", "ipo", "acquisition", "valuation",
            "term sheet", "cap table", "dilution",
        ],
        "low": [
            "business", "strategy", "growth", "market",
            "opportunity", "thesis",
        ],
    },
    "Noise/others": {
        "high": [
            "crypto", "nft", "web3", "blockchain", "memecoin",
            "forex", "trading", "pump", "airdrop",
            "follow back", "follow for follow", "f4f",
            "dm for collab", "promo", "giveaway",
        ],
        "medium": [
            "influencer", "coach", "guru", "masterclass",
            "passive income", "affiliate", "clickbait",
            "motivational", "hustle", "grind",
        ],
        "low": [],
    },
}


def classify_semantic(profile: dict) -> Dict[str, float]:
    """
    Semantic classification: score profile against each category.
    Returns dict of {category: score (0-100)}.
    """
    # Build full text from profile
    text_parts = [profile.get("bio", "")]
    for post in profile.get("posts", []):
        text_parts.append(post.get("text", ""))
    full_text = " ".join(text_parts).lower()

    if not full_text.strip():
        return {cat: 0.0 for cat in CLASSIFICATION_CATEGORIES}

    scores = {}

    for category, tiers in CATEGORY_KEYWORDS.items():
        score = 0
        high_matches = sum(1 for kw in tiers.get("high", []) if kw in full_text)
        medium_matches = sum(1 for kw in tiers.get("medium", []) if kw in full_text)
        low_matches = sum(1 for kw in tiers.get("low", []) if kw in full_text)

        # Weighted scoring
        score = (high_matches * 5) + (medium_matches * 2) + (low_matches * 0.5)

        # Normalize to 0-100
        max_possible = (
            len(tiers.get("high", [])) * 5 +
            len(tiers.get("medium", [])) * 2 +
            len(tiers.get("low", [])) * 0.5
        )
        normalized = (score / max(max_possible, 1)) * 100
        scores[category] = round(min(normalized, 100), 2)

    return scores


def classify_llm(profile: dict) -> Tuple[str, float, str]:
    """
    LLM classification using DeepSeek.
    Returns (category, confidence (0-1), reasoning).
    """
    if not DEEPSEEK_KEY:
        return "Noise/others", 0.0, "DeepSeek API key not set"

    # Build comprehensive context
    bio = profile.get("bio", "N/A")
    handle = profile.get("handle", "?")
    followers = profile.get("followers_count", "?")
    days_inactive = profile.get("days_since_active", "?")
    website = profile.get("website", "N/A")
    shipping_keywords = profile.get("shipping_keywords", [])
    links = profile.get("extracted_links", [])
    llm_eval = profile.get("score_breakdown", {}).get("llm_reasoning", "N/A")

    # Format posts
    posts_text = ""
    for i, post in enumerate(profile.get("posts", [])[:10], 1):
        text = post.get("text", "")[:300]
        likes = post.get("like_count", 0)
        posts_text += f"\n  Post {i}: {text}\n    [likes={likes}]\n"

    links_text = "\n".join([f"  - {l.get('platform', '?')}: {l.get('url', '?')}" for l in links]) if links else "None"

    categories_str = "\n".join([f"  {i}. {c}" for i, c in enumerate(CLASSIFICATION_CATEGORIES, 1)])

    prompt = f"""Classify this X/Twitter profile into exactly ONE of these categories:

{categories_str}

PROFILE:
- Handle: @{handle}
- Bio: {bio}
- Followers: {followers}
- Last Active: {days_inactive} days ago
- Website: {website}
- Shipping Signals: {', '.join(shipping_keywords) if shipping_keywords else 'None'}

EXTRACTED LINKS:
{links_text}

RECENT POSTS:
{posts_text if posts_text.strip() else "No posts available"}

PREVIOUS EVALUATION:
{llm_eval}

INSTRUCTIONS:
- Consider ALL available data: bio, posts content, links, shipping signals, engagement patterns
- Early-stage founder = actively building a product/startup, shipping code, has users
- AI researcher = publishing papers, academic work, novel research
- AI operator = engineering role, deploying/maintaining ML systems at a company
- Angel investor = investing in startups, portfolio management
- Noise/others = not a meaningful signal, spam, crypto-only, generic influencer

RESPOND IN EXACTLY THIS JSON FORMAT:
{{"category": "<exact category name>", "confidence": <0.0-1.0>, "reasoning": "<2-3 sentence justification>"}}"""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": "You are an expert tech profile classifier. Output valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "stream": False,
    }

    try:
        resp = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        # Clean markdown
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        result = json.loads(content.strip())
        category = result.get("category", "Noise/others")
        confidence = min(max(float(result.get("confidence", 0)), 0), 1)
        reasoning = result.get("reasoning", "No reasoning provided")

        # Validate category
        if category not in CLASSIFICATION_CATEGORIES:
            # Try fuzzy match
            for valid_cat in CLASSIFICATION_CATEGORIES:
                if valid_cat.lower() in category.lower() or category.lower() in valid_cat.lower():
                    category = valid_cat
                    break
            else:
                category = "Noise/others"

        return category, confidence, reasoning
    except Exception as e:
        return "Noise/others", 0.0, f"LLM classification failed: {e}"


def run():
    state = PipelineState()

    if not PROFILES_SCORED_FILE.exists():
        print(f"  {C.R}✗ No scored profiles found. Run scoring pipeline first.{C.END}")
        return

    scored = json.loads(PROFILES_SCORED_FILE.read_text())
    print(f"  {C.D}Scored profiles: {len(scored)}{C.END}")

    # Check for unprocessed
    unclassified = [p for p in scored if not state.is_processed(p["handle"], "classified")]

    # Load existing
    existing_classified = {}
    if PROFILES_CLASSIFIED_FILE.exists():
        try:
            classified_data = json.loads(PROFILES_CLASSIFIED_FILE.read_text())
            existing_classified = {p["handle"]: p for p in classified_data}
        except Exception:
            pass

    if not unclassified:
        print(f"  {C.G}✓ All {len(scored)} profiles already classified.{C.END}")
        print(f"  {C.D}Reset 'classified' stage to re-run.{C.END}")
        return

    print(f"  {C.W}Profiles to classify: {len(unclassified)}{C.END}")
    print(f"  {C.D}Estimated time: ~{len(unclassified) * LLM_REQUEST_INTERVAL // 60 + 1} minutes{C.END}")

    print(f"\n  {C.BOLD}Options:{C.END}")
    print(f"  {C.B}a{C.END}  Classify all {len(unclassified)}")
    print(f"  {C.B}n{C.END}  Classify specific number")
    print(f"  {C.B}0{C.END}  Cancel")
    choice = input(f"\n  {C.W}▸ {C.END}").strip().lower()

    if choice == "0":
        return

    profiles_to_classify = unclassified
    if choice == "n":
        n = input(f"  How many? ").strip()
        n = int(n) if n.isdigit() else len(unclassified)
        profiles_to_classify = unclassified[:n]

    print(f"\n  {C.H}Classifying {len(profiles_to_classify)} profiles...{C.END}\n")

    category_counter = Counter()

    for idx, profile in enumerate(profiles_to_classify):
        handle = profile["handle"]
        print(f"  {C.B}[{idx+1}/{len(profiles_to_classify)}]{C.END} @{handle} (score: {profile.get('signal_strength', '?')})")

        # 1. Semantic classification
        semantic_scores = classify_semantic(profile)
        semantic_top = max(semantic_scores, key=semantic_scores.get) if semantic_scores else "Noise/others"

        # 2. LLM classification
        llm_category, llm_confidence, llm_reasoning = classify_llm(profile)

        # Store classification
        profile["classification"] = {
            "llm_category": llm_category,
            "llm_confidence": round(llm_confidence, 3),
            "llm_reasoning": llm_reasoning,
            "semantic_scores": semantic_scores,
            "semantic_top_category": semantic_top,
        }
        profile["classified_at"] = datetime.utcnow().isoformat()

        existing_classified[handle] = profile
        state.mark_processed(handle, "classified")
        category_counter[llm_category] += 1

        # Display
        cat_color = {
            "Early-stage founder": C.G,
            "AI researcher": C.B,
            "AI operator": C.Y,
            "Angel investor": C.H,
            "Noise/others": C.D,
        }.get(llm_category, C.W)

        print(f"    LLM: {cat_color}{llm_category}{C.END} (conf={llm_confidence:.0%})")
        print(f"    {C.D}Justification: {llm_reasoning}{C.END}")
        print(f"    Semantic: {semantic_top} | scores: {', '.join(f'{k[:8]}={v:.0f}' for k, v in sorted(semantic_scores.items(), key=lambda x: x[1], reverse=True)[:3])}")

        # Rate limit
        if idx < len(profiles_to_classify) - 1:
            time.sleep(LLM_REQUEST_INTERVAL)

    # Save all classified profiles
    all_classified = list(existing_classified.values())
    all_classified.sort(key=lambda p: p.get("signal_strength", 0), reverse=True)

    DATA_DIR.mkdir(exist_ok=True)
    with open(PROFILES_CLASSIFIED_FILE, "w") as f:
        json.dump(all_classified, f, indent=2, default=str)

    state.save()

    # Summary
    print(f"\n  {C.G}{'═' * 40}{C.END}")
    print(f"  {C.G}✓ Classification complete{C.END}")
    print(f"    Classified: {len(profiles_to_classify)} profiles")
    print(f"\n  {C.BOLD}Distribution:{C.END}")
    for cat, count in category_counter.most_common():
        bar = "█" * min(30, count * 3)
        print(f"    {cat:<22} {count:>3}  {bar}")
    print(f"\n    Saved to: {PROFILES_CLASSIFIED_FILE}")


if __name__ == "__main__":
    run()
