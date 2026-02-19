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

    if selected_topics:
        topics_to_process = selected_topics
        print(f"  {C.B}Adding handles to {len(topics_to_process)} selected categories...{C.END}")
    else:
        print(f"  {C.D}Existing profiles: {len(existing_handles)}{C.END}")
        print(f"\n  {C.BOLD}How would you like to proceed?{C.END}")
        print(f"  {C.B}1{C.END}  Add handles to a new topic")
        print(f"  {C.B}2{C.END}  Generate topic ideas using AI")
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

        if choice == "1":
            topic = input(f"  Enter topic/category name: ").strip()
            if topic:
                topics_to_process = [topic]

    if not topics_to_process:
        return

    new_profiles = []
    for topic in topics_to_process:
        state.add_topic(topic)
        print(f"\n  {C.BOLD}Category: {topic}{C.END}")
        print(f"  Enter handles (one per line, empty to finish):")
        
        while True:
            raw_input = input(f"  {C.W}▸ @{C.END}").strip().lower()
            if not raw_input:
                break
                
            # Basic cleaning (remove @ if present, extract from URL if pasted)
            handle = raw_input.replace("@", "")
            if "twitter.com/" in handle or "x.com/" in handle:
                match = re.search(r"(?:twitter\.com|x\.com)/([a-zA-Z0-9_]{1,15})", handle)
                if match:
                    handle = match.group(1)

            if handle in existing_handles:
                print(f"    {C.D}(@{handle} already exists, skipping){C.END}")
                continue

            # Create skeleton profile
            profile = {
                "handle": handle,
                "display_name": None,
                "bio": None,
                "platform_id": None,
                "platform": "x",
                "followers_count": None,
                "following_count": None,
                "tweet_count": None,
                "verified": False,
                "profile_url": f"https://x.com/{handle}",
                "profile_image_url": None,
                "location": None,
                "website": None,
                "account_created_at": None,
                "source_topic": topic,
                "found_via_tweet": None,
                "discovered_at": datetime.utcnow().isoformat(),
            }
            new_profiles.append(profile)
            existing_handles.add(handle)
            state.add_profile(handle)
            state.mark_processed(handle, "mined")
            print(f"    {C.G}✓ Added @{handle}{C.END}")

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
