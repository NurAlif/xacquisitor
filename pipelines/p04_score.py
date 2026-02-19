#!/usr/bin/env python3
"""
Pipeline 04: Score profiles using 6-component intelligence scoring.
- DeepSeek LLM Eval (0-35) — highest weight
- Semantic Relevance (0-20)
- Technical Density (0-15)
- Tweet Engagement (0-15)
- Link & URL Analysis (0-10)
- Profile Completeness (0-5)

Total: 0-100

Comprehensive LLM prompt with bio, posts, followers, links, shipping signals.
10s interval between DeepSeek API calls.
"""

import sys
import os
import json
import time
import re
import math
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Fix paths for standalone or package execution
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    PROFILES_FILTERED_FILE, PROFILES_SCORED_FILE, DATA_DIR,
    DEEPSEEK_KEY, DEEPSEEK_URL, DEEPSEEK_MODEL,
    SCORE_WEIGHTS, LLM_REQUEST_INTERVAL,
)
from state import PipelineState


class C:
    G = '\033[92m'; Y = '\033[93m'; R = '\033[91m'; B = '\033[94m'
    D = '\033[90m'; W = '\033[97m'; H = '\033[95m'
    BOLD = '\033[1m'; END = '\033[0m'


# --- Technical keyword tiers ---
TIER1_KEYWORDS = [
    "llm", "gpt", "transformer", "fine-tune", "fine-tuning",
    "rag", "vector database", "embedding", "langchain", "llamaindex",
    "diffusion", "stable diffusion", "midjourney", "comfyui",
    "pytorch", "tensorflow", "hugging face", "huggingface",
    "ai agent", "ai agents", "autonomous agent", "multi-agent",
    "neural network", "deep learning", "machine learning",
    "openai", "anthropic", "claude", "gemini", "mistral", "llama",
]

TIER2_KEYWORDS = [
    "api", "deployment", "inference", "gpu", "cuda",
    "docker", "kubernetes", "mlops", "model serving",
    "prompt engineering", "chain of thought", "few-shot",
    "retrieval", "knowledge graph", "chatbot",
    "nlp", "computer vision", "speech", "multimodal",
    "open source", "github", "npm", "pip install",
]

TIER3_KEYWORDS = [
    "python", "javascript", "typescript", "rust", "golang",
    "startup", "founder", "building", "shipped", "launched",
    "product", "saas", "platform", "tool", "framework",
    "data", "analytics", "pipeline", "automation",
]


def score_technical_density(profile: dict) -> tuple:
    """Score technical density (0-15) based on keyword matching."""
    text_parts = [profile.get("bio", "")]
    for post in profile.get("posts", []):
        text_parts.append(post.get("text", ""))
    full_text = " ".join(text_parts).lower()

    found_keywords = []
    score = 0

    # Tier 1: 3 points each, max 9
    t1_count = 0
    for kw in TIER1_KEYWORDS:
        if kw in full_text:
            found_keywords.append(kw)
            t1_count += 1
    score += min(t1_count * 3, 9)

    # Tier 2: 1.5 points each, max 4.5
    t2_count = 0
    for kw in TIER2_KEYWORDS:
        if kw in full_text:
            found_keywords.append(kw)
            t2_count += 1
    score += min(t2_count * 1.5, 4.5)

    # Tier 3: 0.5 points each, max 1.5
    t3_count = 0
    for kw in TIER3_KEYWORDS:
        if kw in full_text:
            found_keywords.append(kw)
            t3_count += 1
    score += min(t3_count * 0.5, 1.5)

    return min(score, 15), found_keywords


def score_links(profile: dict) -> tuple:
    """Score link & URL analysis (0-10)."""
    links = profile.get("extracted_links", [])
    score = 0
    details = []

    platforms_found = set()
    for link in links:
        platform = link.get("platform", "unknown")
        platforms_found.add(platform)
        details.append(link)

    # GitHub presence: 4 points
    if "github" in platforms_found:
        score += 4

    # Personal website: 2 points
    if "website" in platforms_found or profile.get("website"):
        score += 2

    # Product Hunt: 2 points
    if "product_hunt" in platforms_found:
        score += 2

    # Other platforms: 0.5 each, max 2
    other = platforms_found - {"github", "website", "product_hunt"}
    score += min(len(other) * 0.5, 2)

    return min(score, 10), details


def score_tweet_engagement(profile: dict) -> float:
    """Score tweet engagement (0-15) from enriched posts."""
    posts = profile.get("posts", [])
    if not posts:
        return 0

    total_likes = sum(p.get("like_count", 0) for p in posts)
    total_retweets = sum(p.get("retweet_count", 0) for p in posts)
    total_views = sum(p.get("view_count", 0) for p in posts)
    n = len(posts)

    # Average engagement per post
    avg_likes = total_likes / n
    avg_retweets = total_retweets / n

    score = 0

    # Likes scoring (log scale)
    if avg_likes >= 50:
        score += 5
    elif avg_likes >= 20:
        score += 3.5
    elif avg_likes >= 5:
        score += 2
    elif avg_likes >= 1:
        score += 1

    # Retweets scoring
    if avg_retweets >= 20:
        score += 4
    elif avg_retweets >= 5:
        score += 2.5
    elif avg_retweets >= 1:
        score += 1.5

    # Engagement rate (likes+retweets / views)
    if total_views > 0:
        rate = (total_likes + total_retweets) / total_views
        if rate > 0.05:
            score += 4
        elif rate > 0.02:
            score += 3
        elif rate > 0.01:
            score += 2
        elif rate > 0.005:
            score += 1

    # Post frequency bonus
    if n >= 8:
        score += 2
    elif n >= 5:
        score += 1

    return min(score, 15)


def score_profile_completeness(profile: dict) -> float:
    """Score profile completeness (0-5)."""
    score = 0

    if profile.get("bio") and len(profile["bio"]) > 20:
        score += 1.5
    elif profile.get("bio"):
        score += 0.5

    if profile.get("website"):
        score += 1

    if profile.get("location"):
        score += 0.5

    if profile.get("display_name"):
        score += 0.5

    if profile.get("profile_image_url"):
        score += 0.5

    if profile.get("posts") and len(profile["posts"]) >= 5:
        score += 1

    return min(score, 5)


def score_semantic_relevance(profile: dict) -> float:
    """
    Score semantic relevance (0-20).
    Uses keyword frequency and context analysis against AI builder reference.
    """
    text_parts = [profile.get("bio", "")]
    for post in profile.get("posts", []):
        text_parts.append(post.get("text", ""))
    full_text = " ".join(text_parts).lower()

    if not full_text.strip():
        return 0

    # AI builder reference concepts
    ai_concepts = [
        "artificial intelligence", "machine learning", "deep learning",
        "ai agent", "llm", "large language model", "foundation model",
        "neural network", "natural language processing", "computer vision",
        "generative ai", "gen ai", "ai startup", "ai tool", "ai infrastructure",
        "ai product", "ai platform", "ai framework", "ai research",
        "ml model", "ml pipeline", "ml ops", "model training", "model deployment",
        "fine-tuning", "prompt engineering", "rag", "retrieval augmented",
        "vector database", "semantic search", "embedding", "transformer",
        "diffusion model", "image generation", "text generation", "code generation",
    ]

    builder_concepts = [
        "building", "shipping", "launched", "deployed", "open source",
        "founder", "startup", "indie hacker", "solo dev", "co-founder",
        "seed", "pre-seed", "mvp", "prototype", "beta", "alpha",
        "built", "created", "developed", "released", "published",
    ]

    # Count matches
    ai_score = sum(1 for c in ai_concepts if c in full_text)
    builder_score = sum(1 for c in builder_concepts if c in full_text)

    # Normalize: weight AI concepts more heavily
    ai_normalized = min(ai_score * 2.0, 12)  # max 12 from AI
    builder_normalized = min(builder_score * 1.5, 8)  # max 8 from builder

    return min(ai_normalized + builder_normalized, 20)


def score_llm_eval(profile: dict) -> tuple:
    """
    Score using DeepSeek LLM (0-35).
    Comprehensive prompt with all available profile data.
    Returns (score, reasoning).
    """
    if not DEEPSEEK_KEY:
        return 0, "DeepSeek API key not set"

    # Build comprehensive context
    bio = profile.get("bio", "N/A")
    handle = profile.get("handle", "?")
    followers = profile.get("followers_count", "?")
    following = profile.get("following_count", "?")
    last_active = profile.get("last_active", "?")
    days_inactive = profile.get("days_since_active", "?")
    website = profile.get("website", "N/A")
    location = profile.get("location", "N/A")
    shipping_keywords = profile.get("shipping_keywords", [])
    links = profile.get("extracted_links", [])

    # Format posts
    posts_text = ""
    for i, post in enumerate(profile.get("posts", [])[:10], 1):
        text = post.get("text", "")[:300]
        likes = post.get("like_count", 0)
        rts = post.get("retweet_count", 0)
        views = post.get("view_count", 0)
        posts_text += f"\n  Post {i}: {text}\n    [likes={likes}, retweets={rts}, views={views}]\n"

    # Format links
    links_text = "\n".join([f"  - {l.get('platform', '?')}: {l.get('url', '?')}" for l in links]) if links else "None found"

    prompt = f"""You are an expert analyst identifying early-stage AI builders and founders.

Evaluate this X/Twitter profile for their potential as an early-stage AI builder, researcher, or operator.

PROFILE:
- Handle: @{handle}
- Bio: {bio}
- Followers: {followers}
- Following: {following}
- Website: {website}
- Location: {location}
- Last Active: {last_active} ({days_inactive} days ago)
- Shipping Signals: {', '.join(shipping_keywords) if shipping_keywords else 'None'}

EXTRACTED LINKS:
{links_text}

RECENT POSTS (up to 10):
{posts_text if posts_text.strip() else "No posts available"}

SCORING CRITERIA (0-35 points):
Score based on evidence of:
1. Actively building or shipping AI/ML products or tools (0-10)
2. Technical depth in AI/ML (specific models, frameworks, architectures) (0-8)
3. Entrepreneurial signals (founding, launching, user engagement) (0-7)
4. Community contribution (open source, tutorials, demos) (0-5)
5. Recency and consistency of activity (0-5)

RESPOND IN EXACTLY THIS JSON FORMAT:
{{"score": <0-35>, "reasoning": "<2-3 sentence justification>"}}

Be strict. Only high-quality, actively building profiles should score above 20."""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": "You are an expert tech talent scout. Output valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "stream": False,
    }

    try:
        resp = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        # Clean markdown wrapping
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        result = json.loads(content.strip())
        score = min(max(float(result.get("score", 0)), 0), 35)
        reasoning = result.get("reasoning", "No reasoning provided")
        return score, reasoning
    except Exception as e:
        return 0, f"LLM evaluation failed: {e}"


def run():
    state = PipelineState()

    if not PROFILES_FILTERED_FILE.exists():
        print(f"  {C.R}✗ No filtered profiles found. Run filter pipeline first.{C.END}")
        return

    filtered = json.loads(PROFILES_FILTERED_FILE.read_text())
    print(f"  {C.D}Filtered profiles: {len(filtered)}{C.END}")

    # Check for unprocessed
    unscored_handles = set()
    for p in filtered:
        if not state.is_processed(p["handle"], "scored"):
            unscored_handles.add(p["handle"])

    # Load existing scored
    existing_scored = {}
    if PROFILES_SCORED_FILE.exists():
        try:
            scored_data = json.loads(PROFILES_SCORED_FILE.read_text())
            existing_scored = {p["handle"]: p for p in scored_data}
        except Exception:
            pass

    profiles_to_score = [p for p in filtered if p["handle"] in unscored_handles]

    if not profiles_to_score:
        print(f"  {C.G}✓ All {len(filtered)} profiles already scored.{C.END}")
        print(f"  {C.D}Reset 'scored' stage to re-run.{C.END}")
        return

    print(f"  {C.W}Profiles to score: {len(profiles_to_score)}{C.END}")
    print(f"  {C.D}Estimated time: ~{len(profiles_to_score) * LLM_REQUEST_INTERVAL // 60 + 1} minutes{C.END}")
    print(f"\n  {C.BOLD}Options:{C.END}")
    print(f"  {C.B}a{C.END}  Score all {len(profiles_to_score)}")
    print(f"  {C.B}n{C.END}  Score specific number")
    print(f"  {C.B}0{C.END}  Cancel")
    choice = input(f"\n  {C.W}▸ {C.END}").strip().lower()

    if choice == "0":
        return

    if choice == "n":
        n = input(f"  How many? ").strip()
        n = int(n) if n.isdigit() else len(profiles_to_score)
        profiles_to_score = profiles_to_score[:n]

    print(f"\n  {C.H}Scoring {len(profiles_to_score)} profiles...{C.END}\n")

    for idx, profile in enumerate(profiles_to_score):
        handle = profile["handle"]
        print(f"  {C.B}[{idx+1}/{len(profiles_to_score)}]{C.END} @{handle}")

        # Display profile status
        followers = profile.get("followers_count", "?")
        days_inactive = profile.get("days_since_active", "?")
        post_count = len(profile.get("posts", []))
        shipping = profile.get("has_shipping_signals", False)
        print(f"    {C.D}followers={followers}, inactive={days_inactive}d, posts={post_count}, shipping={shipping}{C.END}")

        # --- Compute each component ---
        technical_score, tech_keywords = score_technical_density(profile)
        links_score, link_details = score_links(profile)
        engagement_score = score_tweet_engagement(profile)
        completeness_score = score_profile_completeness(profile)
        semantic_score = score_semantic_relevance(profile)
        llm_score, llm_reasoning = score_llm_eval(profile)

        # Total signal strength
        signal_strength = round(
            llm_score + semantic_score + technical_score +
            engagement_score + links_score + completeness_score, 2
        )

        # Add scoring data
        profile["signal_strength"] = signal_strength
        profile["score_breakdown"] = {
            "llm_eval": round(llm_score, 2),
            "llm_reasoning": llm_reasoning,
            "semantic": round(semantic_score, 2),
            "technical": round(technical_score, 2),
            "technical_keywords": tech_keywords[:15],
            "tweet_engagement": round(engagement_score, 2),
            "engagement_details": {
                "avg_likes": round(sum(p.get("like_count", 0) for p in profile.get("posts", [])) / max(1, post_count), 1),
                "avg_retweets": round(sum(p.get("retweet_count", 0) for p in profile.get("posts", [])) / max(1, post_count), 1),
            },
            "links": round(links_score, 2),
            "link_details": link_details,
            "profile_completeness": round(completeness_score, 2),
        }
        profile["scored_at"] = datetime.utcnow().isoformat()

        # Update state
        existing_scored[handle] = profile
        state.mark_processed(handle, "scored")

        # Display result
        sw = SCORE_WEIGHTS
        color = C.G if signal_strength >= 50 else C.Y if signal_strength >= 30 else C.R
        print(f"    {color}Score: {signal_strength}/100{C.END} "
              f"[LLM={llm_score:.0f}/{sw['llm_eval']}, Sem={semantic_score:.0f}/{sw['semantic']}, "
              f"Tech={technical_score:.0f}/{sw['technical']}, Eng={engagement_score:.0f}/{sw['tweet_engagement']}, "
              f"Links={links_score:.0f}/{sw['links']}, Prof={completeness_score:.0f}/{sw['profile_completeness']}]")
        print(f"    {C.D}Justification: {llm_reasoning}{C.END}")

        # Rate limit between API calls
        if idx < len(profiles_to_score) - 1:
            time.sleep(LLM_REQUEST_INTERVAL)

    # Save all scored profiles
    all_scored = list(existing_scored.values())
    # Sort by signal strength descending
    all_scored.sort(key=lambda p: p.get("signal_strength", 0), reverse=True)

    DATA_DIR.mkdir(exist_ok=True)
    with open(PROFILES_SCORED_FILE, "w") as f:
        json.dump(all_scored, f, indent=2, default=str)

    state.save()

    # Summary
    scores = [p.get("signal_strength", 0) for p in all_scored]
    avg_score = sum(scores) / max(1, len(scores))

    print(f"\n  {C.G}{'═' * 40}{C.END}")
    print(f"  {C.G}✓ Scoring complete{C.END}")
    print(f"    Scored:      {len(profiles_to_score)} profiles")
    print(f"    Total scored: {len(all_scored)} profiles")
    print(f"    Avg score:   {avg_score:.1f}/100")
    print(f"    Top scorer:  @{all_scored[0]['handle']} ({all_scored[0]['signal_strength']})" if all_scored else "")
    print(f"    Saved to: {PROFILES_SCORED_FILE}")


if __name__ == "__main__":
    run()
