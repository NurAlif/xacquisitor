#!/usr/bin/env python3
"""
Pipeline 01: Mine profiles from topics.
- Interactive CLI: enter topics manually or generate via DeepSeek
- Search via Tavily API to find X profile handles
- Anti-duplication: skips existing profiles
- Saves to data/profiles_raw.json
"""

import sys
import os
import json
import time
import re
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Fix paths for standalone or package execution
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    DEEPSEEK_KEY, DEEPSEEK_URL, DEEPSEEK_MODEL,
    PROFILES_RAW_FILE, DATA_DIR, LLM_REQUEST_INTERVAL,
)
from state import PipelineState


class C:
    G = '\033[92m'; Y = '\033[93m'; R = '\033[91m'; B = '\033[94m'
    D = '\033[90m'; W = '\033[97m'; BOLD = '\033[1m'; END = '\033[0m'


def generate_topics_llm(count: int = 5) -> List[str]:
    """Generate profile search ideas or queries using DeepSeek LLM."""
    if not DEEPSEEK_KEY:
        print(f"  {C.R}✗ DeepSeek API key not set — cannot generate ideas.{C.END}")
        return []

    prompt = f"""Generate exactly {count} short descriptions of early-stage AI builders on X/Twitter to look for.
These should define specific technical personas.

Focus on builders who:
- Ship code and products (not just commentators)
- Work on AI agents, LLM tools, fine-tuning, indie hackers
- Share technical progress publicly

Return ONLY a JSON array of strings. No other text.
Example: ["indie AI agent builder", "LLM infra startup founder"]"""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": "You generate target personas for research. Output only JSON arrays."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "stream": False,
    }

    try:
        resp = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        topics = json.loads(content.strip())
        return topics if isinstance(topics, list) else []
    except Exception as e:
        print(f"  {C.R}✗ Generation failed: {e}{C.END}")
        return []


def search_x_api_v2(query: str, max_results: int = 10) -> List[Dict]:
    """Search X API v2 for users who recently tweeted about a topic."""
    from config import X_BEARER_TOKEN
    if not X_BEARER_TOKEN:
        print(f"  {C.R}✗ X_BEARER_TOKEN not set.{C.END}")
        return []

    # Search for recent tweets matching the query
    # We want authors, so we'll expand author_id
    url = "https://api.twitter.com/2/tweets/search/recent"
    params = {
        "query": f"{query} -is:retweet -is:reply lang:en",
        "max_results": min(100, max(10, max_results)),
        "expansions": "author_id",
        "user.fields": "username,name,description,public_metrics,verified,location,url,profile_image_url",
    }
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        users = data.get("includes", {}).get("users", [])
        profiles = []
        for u in users:
            handle = u["username"].lower()
            profiles.append({
                "handle": handle,
                "display_name": u.get("name"),
                "bio": u.get("description"),
                "platform_id": u.get("id"),
                "platform": "x",
                "followers_count": u.get("public_metrics", {}).get("followers_count"),
                "following_count": u.get("public_metrics", {}).get("following_count"),
                "tweet_count": u.get("public_metrics", {}).get("tweet_count"),
                "verified": u.get("verified", False),
                "profile_url": f"https://x.com/{handle}",
                "profile_image_url": u.get("profile_image_url"),
                "location": u.get("location"),
                "website": u.get("url"),
                "account_created_at": None,
                "source_topic": None, 
                "found_via_tweet": None, # Search results don't easily map back to a specific tweet here without more work
                "discovered_at": datetime.utcnow().isoformat(),
            })
        return profiles
    except Exception as e:
        print(f"  {C.R}✗ X API search failed: {e}{C.END}")
        return []


def run(selected_topics: List[str] = None):
    state = PipelineState()
    existing_handles = state.get_all_handles()

    # Load existing profiles
    existing_profiles = []
    if PROFILES_RAW_FILE.exists():
        try:
            existing_profiles = json.loads(PROFILES_RAW_FILE.read_text())
            existing_handles.update(p["handle"] for p in existing_profiles)
        except Exception:
            pass

    topics_to_process = []
    is_manual = True

    if selected_topics:
        topics_to_process = selected_topics
        print(f"  {C.B}Adding handles to {len(topics_to_process)} selected categories...{C.END}")
    else:
        print(f"  {C.D}Existing profiles: {len(existing_handles)}{C.END}")
        print(f"\n  {C.BOLD}How would you like to proceed?{C.END}")
        print(f"  {C.B}1{C.END}  Add handles to a new topic")
        print(f"  {C.B}2{C.END}  Generate topic ideas using AI")
        print(f"  {C.B}3{C.END}  Search X via API v2 (find users by topic)")
        choice = input(f"\n  {C.W}▸ {C.END}").strip()

        if choice == "2":
            count = input(f"  How many ideas to generate? (default 5): ").strip()
            count = int(count) if count.isdigit() else 5
            ideas = generate_topics_llm(count)
            if ideas:
                for idea in ideas:
                    state.add_topic(idea)
                print(f"  {C.G}✓ Added {len(ideas)} ideas to Topic Management.{C.END}")
            return

        if choice == "3":
            topic = input(f"  Enter search topic: ").strip()
            if topic:
                topics_to_process = [topic]
                is_manual = False
            else:
                return
        elif choice == "1":
            topic = input(f"  Enter topic/category name: ").strip()
            if topic:
                topics_to_process = [topic]
                is_manual = True
        else:
            return

    if not topics_to_process:
        return

    new_profiles = []
    for topic in topics_to_process:
        state.add_topic(topic)
        print(f"\n  {C.BOLD}Category/Topic: {topic}{C.END}")
        
        found_profiles = []
        if not is_manual:
            print(f"  {C.D}Searching X API v2...{C.END}")
            found_profiles = search_x_api_v2(topic, max_results=20)
            print(f"    Found {len(found_profiles)} potential profiles via search.")
        else:
            print(f"  Enter handles (one per line, empty to finish):")
            while True:
                raw_input = input(f"  {C.W}▸ @{C.END}").strip().lower()
                if not raw_input:
                    break
                    
                handle = raw_input.replace("@", "")
                if "twitter.com/" in handle or "x.com/" in handle:
                    match = re.search(r"(?:twitter\.com|x\.com)/([a-zA-Z0-9_]{1,15})", handle)
                    if match:
                        handle = match.group(1)
                
                found_profiles.append({"handle": handle, "manual": True})

        added = 0
        for p_data in found_profiles:
            handle = p_data["handle"]
            if handle in existing_handles:
                if is_manual:
                    print(f"    {C.D}(@{handle} already exists, skipping){C.END}")
                continue

            # Create/Fill profile
            profile = {
                "handle": handle,
                "display_name": p_data.get("display_name"),
                "bio": p_data.get("bio"),
                "platform_id": p_data.get("platform_id"),
                "platform": "x",
                "followers_count": p_data.get("followers_count"),
                "following_count": p_data.get("following_count"),
                "tweet_count": p_data.get("tweet_count"),
                "verified": p_data.get("verified", False),
                "profile_url": f"https://x.com/{handle}",
                "profile_image_url": p_data.get("profile_image_url"),
                "location": p_data.get("location"),
                "website": p_data.get("website"),
                "account_created_at": None,
                "source_topic": topic,
                "found_via_tweet": p_data.get("found_via_tweet"),
                "discovered_at": datetime.utcnow().isoformat(),
            }
            new_profiles.append(profile)
            existing_handles.add(handle)
            state.add_profile(handle)
            state.mark_processed(handle, "mined")
            added += 1
            if is_manual:
                print(f"    {C.G}✓ Added @{handle}{C.END}")

        if not is_manual:
            print(f"    Added {added} new profiles to pipeline.")
        
        state.update_topic_status(topic, "completed", results_count=len(found_profiles))

    # Merge and save
    if new_profiles:
        all_profiles = existing_profiles + new_profiles
        DATA_DIR.mkdir(exist_ok=True)
        with open(PROFILES_RAW_FILE, "w") as f:
            json.dump(all_profiles, f, indent=2, default=str)
        
        state.save()
        print(f"\n  {C.G}✓ Saved {len(new_profiles)} new profiles to {PROFILES_RAW_FILE.name}{C.END}")
    else:
        print(f"\n  {C.D}No new profiles added.{C.END}")


if __name__ == "__main__":
    run()


if __name__ == "__main__":
    run()
