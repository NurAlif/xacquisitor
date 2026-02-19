#!/usr/bin/env python3
"""
Pipeline 02: Enrich profiles using Playwright.
- Scrapes X profiles for: followers, following, last active, 10 latest posts
- Extracts links and shipping signals from posts
- Rate limited: 60s between scrapes
- Resumable: skips already-enriched profiles
- Saves to data/profiles_enriched.json
"""

import sys
import os
import json
import asyncio
import time
import re
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path

# Fix paths for standalone or package execution
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    PROFILES_RAW_FILE, PROFILES_ENRICHED_FILE, DATA_DIR,
    PLAYWRIGHT_RATE_LIMIT, MAX_POSTS_TO_FETCH, COOKIES_FILE,
)
from state import PipelineState


class C:
    G = '\033[92m'; Y = '\033[93m'; R = '\033[91m'; B = '\033[94m'
    D = '\033[90m'; W = '\033[97m'; BOLD = '\033[1m'; END = '\033[0m'


# Shipping signal keywords
SHIPPING_KEYWORDS = [
    "shipped", "launched", "released", "deployed", "pushed to prod",
    "live now", "just built", "open sourced", "open-sourced",
    "demo", "beta", "alpha", "v1", "v2", "mvp", "prototype",
    "building", "shipping", "working on", "side project",
]

# Link patterns to extract
LINK_PATTERNS = {
    "github": re.compile(r"github\.com/([a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_.-]+)?)"),
    "huggingface": re.compile(r"huggingface\.co/([a-zA-Z0-9_-]+)"),
    "product_hunt": re.compile(r"producthunt\.com/posts/([a-zA-Z0-9_-]+)"),
    "linkedin": re.compile(r"linkedin\.com/in/([a-zA-Z0-9_-]+)"),
    "youtube": re.compile(r"(?:youtube\.com|youtu\.be)/([a-zA-Z0-9_-]+)"),
    "website": re.compile(r"https?://(?!(?:twitter|x|t)\.co)(?!github\.com)(?!linkedin\.com)[a-zA-Z0-9.-]+\.[a-z]{2,}[^\s]*"),
}


def extract_links(text: str) -> List[Dict[str, str]]:
    """Extract platform links from text."""
    links = []
    if not text:
        return links

    for platform, pattern in LINK_PATTERNS.items():
        matches = pattern.findall(text)
        for match in matches:
            url = match if match.startswith("http") else f"https://{platform}.com/{match}" if platform != "website" else match
            links.append({"platform": platform, "url": url, "source": "post"})

    return links


def detect_shipping_signals(text: str) -> List[str]:
    """Detect shipping-related keywords in text."""
    if not text:
        return []
    text_lower = text.lower()
    return [kw for kw in SHIPPING_KEYWORDS if kw in text_lower]


async def enrich_with_playwright(handles: List[str], existing_enriched: Dict[str, dict]) -> List[dict]:
    """Enrich profiles using Playwright browser scraping."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print(f"  {C.R}✗ Playwright not installed. Run: pip install playwright && playwright install chromium{C.END}")
        return []

    # Determine cookie file
    cookie_file = COOKIES_FILE
    if not cookie_file.exists():
        # Try parent directory
        parent_cookies = Path(__file__).resolve().parent.parent.parent / "x_cookies.json"
        if parent_cookies.exists():
            cookie_file = parent_cookies

    if not cookie_file.exists():
        print(f"  {C.R}✗ Cookie file not found at {cookie_file}{C.END}")
        print(f"    Please copy x_cookies.json to {COOKIES_FILE}")
        return []

    enriched_profiles = []
    
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu",
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York",
        )

        # Load cookies
        try:
            cookies_data = json.loads(cookie_file.read_text())
            await context.add_cookies(cookies_data)
            print(f"  {C.G}✓ Loaded {len(cookies_data)} cookies{C.END}")
        except Exception as e:
            print(f"  {C.R}✗ Failed to load cookies: {e}{C.END}")
            await browser.close()
            return []

        page = await context.new_page()

        # Store intercepted responses
        xhr_responses = {}

        async def intercept_response(response):
            try:
                if response.request.resource_type not in ["xhr", "fetch"]:
                    return
                url = response.url
                if "graphql" in url.lower() or "api.x.com" in url:
                    if "UserByScreenName" in url or "UserByRestId" in url:
                        xhr_responses["user_profile"] = await response.json()
                    elif "UserTweets" in url:
                        xhr_responses["user_tweets"] = await response.json()
            except Exception:
                pass

        page.on("response", intercept_response)

        # Anti-detection
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        """)

        # Verify login
        print(f"  {C.D}Verifying login...{C.END}")
        await navigate_with_retry(page, "https://x.com/home")
        is_logged = await page.is_visible('[data-testid="SideNav_NewTweet_Button"]')
        if not is_logged:
            print(f"  {C.R}✗ Not logged in. Cookies may be expired.{C.END}")
            await browser.close()
            return []
        print(f"  {C.G}✓ Authenticated{C.END}")

        # Process each handle
        for idx, handle in enumerate(handles):
            print(f"\n  {C.B}[{idx+1}/{len(handles)}]{C.END} Enriching @{handle}...")

            try:
                xhr_responses.clear()

                # --- Scrape Profile ---
                await navigate_with_retry(page, f"https://x.com/{handle}")

                # Wait for profile to load
                try:
                    await page.wait_for_selector("[data-testid='primaryColumn']", timeout=10000)
                except Exception:
                    print(f"    {C.Y}⚠ Profile may be private/suspended{C.END}")
                    continue

                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(3)

                # Parse profile from GraphQL
                profile_data = _parse_profile_graphql(xhr_responses, handle)
                if not profile_data:
                    profile_data = await _parse_profile_html(page, handle)

                if not profile_data:
                    print(f"    {C.Y}⚠ Could not extract profile data{C.END}")
                    continue

                # --- Scrape Tweets ---
                xhr_responses.clear()
                tweets = await _scrape_tweets(page, handle, MAX_POSTS_TO_FETCH)

                # Process tweets
                posts = []
                all_text_parts = []
                all_links = []
                all_shipping = []

                for tweet in tweets:
                    posts.append({
                        "text": tweet.get("text", ""),
                        "created_at": tweet.get("created_at"),
                        "like_count": tweet.get("like_count", 0),
                        "retweet_count": tweet.get("retweet_count", 0),
                        "reply_count": tweet.get("reply_count", 0),
                        "view_count": tweet.get("view_count", 0),
                        "is_reply": False,
                        "is_retweet": False,
                        "url": tweet.get("url"),
                    })
                    text = tweet.get("text", "")
                    all_text_parts.append(text)
                    all_links.extend(extract_links(text))
                    all_shipping.extend(detect_shipping_signals(text))

                # Also check bio for links and signals
                bio = profile_data.get("bio", "")
                if bio:
                    all_links.extend(extract_links(bio))
                    all_shipping.extend(detect_shipping_signals(bio))

                # Calculate last active
                last_active = None
                days_since_active = None
                tweet_dates = [t.get("created_at") for t in tweets if t.get("created_at")]
                if tweet_dates:
                    try:
                        parsed_dates = []
                        for d in tweet_dates:
                            try:
                                parsed_dates.append(datetime.fromisoformat(d.replace("Z", "+00:00")))
                            except Exception:
                                pass
                        if parsed_dates:
                            latest = max(parsed_dates)
                            last_active = latest.isoformat()
                            diff = datetime.utcnow() - latest.replace(tzinfo=None)
                            days_since_active = diff.days
                            
                            # If less than 1 day, provide a string representation
                            if days_since_active == 0:
                                hours = diff.seconds // 3600
                                if hours > 0:
                                    last_active_str = f"{hours}h ago"
                                else:
                                    last_active_str = f"{diff.seconds // 60}m ago"
                            else:
                                last_active_str = f"{days_since_active}d ago"
                            
                            profile_data["last_active_str"] = last_active_str
                    except Exception:
                        pass

                # Deduplicate links
                unique_links = []
                seen_urls = set()
                for link in all_links:
                    if link["url"] not in seen_urls:
                        seen_urls.add(link["url"])
                        unique_links.append(link)

                enriched = {
                    "handle": handle,
                    "display_name": profile_data.get("display_name"),
                    "bio": bio,
                    "platform_id": profile_data.get("platform_id"),
                    "platform": "x",
                    "followers_count": profile_data.get("followers_count"),
                    "following_count": profile_data.get("following_count"),
                    "tweet_count": profile_data.get("tweet_count"),
                    "verified": profile_data.get("verified", False),
                    "profile_url": f"https://x.com/{handle}",
                    "profile_image_url": profile_data.get("profile_image_url"),
                    "location": profile_data.get("location"),
                    "website": profile_data.get("website"),
                    "account_created_at": profile_data.get("created_at"),
                    "source_topic": existing_enriched.get(handle, {}).get("source_topic", ""),
                    "found_via_tweet": existing_enriched.get(handle, {}).get("found_via_tweet"),
                    "discovered_at": existing_enriched.get(handle, {}).get("discovered_at", datetime.utcnow().isoformat()),
                    "posts": posts,
                    "last_active": last_active,
                    "last_active_str": profile_data.get("last_active_str"),
                    "days_since_active": days_since_active,
                    "extracted_links": unique_links,
                    "has_shipping_signals": len(set(all_shipping)) > 0,
                    "shipping_keywords": list(set(all_shipping)),
                    "enriched_at": datetime.utcnow().isoformat(),
                }

                enriched_profiles.append(enriched)

                fc = profile_data.get("followers_count", "?")
                print(f"    {C.G}✓{C.END} followers={fc}, posts={len(posts)}, "
                      f"last_active={days_since_active}d ago, "
                      f"links={len(unique_links)}, shipping={len(set(all_shipping))}")

            except Exception as e:
                print(f"    {C.R}✗ Error: {e}{C.END}")

            # Rate limit - Randomized 70-90s
            if idx < len(handles) - 1:
                interval = random.randint(70, 90)
                print(f"    {C.D}Waiting {interval}s (randomized rate limit)...{C.END}")
                await asyncio.sleep(interval)

        await browser.close()

    return enriched_profiles


async def navigate_with_retry(page, url, retries=2):
    """Helper for robust navigation with retries and random waits."""
    for i in range(retries):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=90000)
            await asyncio.sleep(random.uniform(3, 6))
            return True
        except Exception as e:
            if i == retries - 1:
                raise e
            print(f"    \033[93m⚠ Navigation failed, retrying ({i+1}/{retries})...\033[0m")
            await asyncio.sleep(5)
    return False


def _parse_profile_graphql(xhr_responses: dict, handle: str) -> Optional[dict]:
    """Parse profile data from intercepted GraphQL response."""
    try:
        user_data = xhr_responses.get("user_profile", {})
        if not user_data:
            return None

        result = user_data.get("data", {}).get("user", {}).get("result", {})
        if not result:
            return None

        legacy = result.get("legacy", {})

        website = None
        entities = legacy.get("entities", {})
        if entities and "url" in entities and "urls" in entities["url"]:
            urls = entities["url"]["urls"]
            if urls:
                website = urls[0].get("expanded_url")

        return {
            "platform_id": result.get("rest_id"),
            "display_name": legacy.get("name"),
            "bio": legacy.get("description"),
            "location": legacy.get("location"),
            "website": website,
            "followers_count": legacy.get("followers_count", 0),
            "following_count": legacy.get("friends_count", 0),
            "tweet_count": legacy.get("statuses_count", 0),
            "verified": legacy.get("verified", False) or result.get("is_blue_verified", False),
            "created_at": legacy.get("created_at"),
            "profile_image_url": legacy.get("profile_image_url_https"),
        }
    except Exception:
        return None


async def _parse_profile_html(page, handle: str) -> Optional[dict]:
    """Fallback: extract profile data from HTML."""
    try:
        data = await page.evaluate("""
            () => {
                const result = { handle: '', name: null, bio: null, followers: 0, following: 0, verified: false };
                
                const nameEl = document.querySelector('[data-testid="UserName"] span span');
                if (nameEl) result.name = nameEl.textContent;
                
                const bioEl = document.querySelector('[data-testid="UserDescription"]');
                if (bioEl) result.bio = bioEl.textContent;
                
                const followersEl = document.querySelector('a[href$="/verified_followers"] span span') || 
                                    document.querySelector('a[href$="/followers"] span span');
                if (followersEl) {
                    const text = followersEl.textContent.replace(/,/g, '');
                    if (text.includes('K')) result.followers = Math.round(parseFloat(text.replace('K', '')) * 1000);
                    else if (text.includes('M')) result.followers = Math.round(parseFloat(text.replace('M', '')) * 1000000);
                    else result.followers = parseInt(text) || 0;
                }
                
                const followingEl = document.querySelector('a[href$="/following"] span span');
                if (followingEl) {
                    const text = followingEl.textContent.replace(/,/g, '');
                    if (text.includes('K')) result.following = Math.round(parseFloat(text.replace('K', '')) * 1000);
                    else result.following = parseInt(text) || 0;
                }
                
                result.verified = !!document.querySelector('[data-testid="icon-verified"]');
                return result;
            }
        """)

        return {
            "platform_id": None,
            "display_name": data.get("name"),
            "bio": data.get("bio"),
            "location": None,
            "website": None,
            "followers_count": int(data.get("followers", 0)),
            "following_count": int(data.get("following", 0)),
            "tweet_count": 0,
            "verified": data.get("verified", False),
            "created_at": None,
            "profile_image_url": None,
        }
    except Exception:
        return None


async def _scrape_tweets(page, handle: str, max_tweets: int = 10) -> List[dict]:
    """Scrape recent tweets from a user's profile."""
    tweets = []
    seen_ids = set()

    try:
        await navigate_with_retry(page, f"https://x.com/{handle}")

        try:
            await page.wait_for_selector("[data-testid='cellInnerDiv']", timeout=10000)
        except Exception:
            return []

        scroll_attempts = 0
        while len(tweets) < max_tweets and scroll_attempts < 10:
            scroll_attempts += 1

            new_tweets = await page.evaluate("""
                () => {
                    const tweets = [];
                    const articles = document.querySelectorAll('article[data-testid="tweet"]');
                    
                    articles.forEach(article => {
                        try {
                            const textEl = article.querySelector('[lang]');
                            const text = textEl ? textEl.textContent : '';
                            
                            const timeEl = article.querySelector('time');
                            const datetime = timeEl ? timeEl.dateTime : null;
                            
                            const group = article.querySelector('div[role="group"]');
                            let likes = 0, retweets = 0, replies = 0, views = 0;
                            
                            if (group) {
                                const label = group.getAttribute('aria-label') || '';
                                const likeMatch = label.match(/([\d,.KM]+)\s*Likes?/i);
                                const retweetMatch = label.match(/([\d,.KM]+)\s*Reposts?/i);
                                const replyMatch = label.match(/([\d,.KM]+)\s*Replies?/i);
                                const viewMatch = label.match(/([\d,.KM]+)\s*Views?/i);
                                
                                function parseCount(str) {
                                    if (!str) return 0;
                                    str = str.replace(/,/g, '');
                                    if (str.includes('K')) return Math.round(parseFloat(str.replace('K', '')) * 1000);
                                    if (str.includes('M')) return Math.round(parseFloat(str.replace('M', '')) * 1000000);
                                    return parseInt(str) || 0;
                                }
                                
                                likes = likeMatch ? parseCount(likeMatch[1]) : 0;
                                retweets = retweetMatch ? parseCount(retweetMatch[1]) : 0;
                                replies = replyMatch ? parseCount(replyMatch[1]) : 0;
                                views = viewMatch ? parseCount(viewMatch[1]) : 0;
                            }
                            
                            const linkEl = article.querySelector('a[href*="/status/"]');
                            const tweetUrl = linkEl ? linkEl.href : null;
                            const tweetId = tweetUrl ? tweetUrl.split('/status/').pop().split('?')[0] : null;
                            
                            tweets.push({
                                id: tweetId, text: text.trim(), created_at: datetime,
                                like_count: likes, retweet_count: retweets, reply_count: replies, view_count: views,
                                url: tweetUrl
                            });
                        } catch (e) {}
                    });
                    return tweets;
                }
            """)

            for tweet in new_tweets:
                tid = tweet.get("id")
                if tid and tid not in seen_ids:
                    seen_ids.add(tid)
                    tweets.append(tweet)

            if len(tweets) >= max_tweets:
                break

            # Slower, randomized scrolling pattern
            steps = random.randint(3, 6)
            for _ in range(steps):
                # Scroll by a portion of the page
                await page.evaluate(f"window.scrollBy(0, {random.randint(400, 800)})")
                await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Final scroll to bottom just in case
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(random.uniform(2, 4))

        return tweets[:max_tweets]
    except Exception as e:
        print(f"    {C.Y}⚠ Tweet scraping error: {e}{C.END}")
        return tweets


def run():
    state = PipelineState()

    # Load raw profiles
    if not PROFILES_RAW_FILE.exists():
        print(f"  {C.R}✗ No profiles found. Run mining or DB import first.{C.END}")
        return

    raw_profiles = json.loads(PROFILES_RAW_FILE.read_text())
    print(f"  {C.D}Total raw profiles: {len(raw_profiles)}{C.END}")

    # Load existing enriched profiles
    existing_enriched = {}
    if PROFILES_ENRICHED_FILE.exists():
        try:
            enriched_data = json.loads(PROFILES_ENRICHED_FILE.read_text())
            existing_enriched = {p["handle"]: p for p in enriched_data}
        except Exception:
            pass

    # Find profiles needing enrichment
    unenriched_handles = state.get_unprocessed("enriched", from_stage="mined")

    # Also check for profiles that are in raw but not yet tracked
    raw_handles = {p["handle"] for p in raw_profiles}
    for h in raw_handles:
        if not state.is_processed(h, "mined"):
            state.add_profile(h)
            state.mark_processed(h, "mined")

    unenriched_handles = state.get_unprocessed("enriched", from_stage="mined")
    
    # Also include profiles that are marked as enriched but have null followers or activity (often from DB import)
    missing_data_handles = []
    for h, p in existing_enriched.items():
        if p.get("followers_count") is None or p.get("last_active") is None:
            if h not in unenriched_handles:
                missing_data_handles.append(h)
    
    if missing_data_handles:
        print(f"  {C.Y}⚠ Found {len(missing_data_handles)} profiles with missing followers/activity data.{C.END}")
        unenriched_handles.extend(missing_data_handles)

    if not unenriched_handles:
        print(f"  {C.G}✓ All profiles are already enriched. ({len(existing_enriched)} total){C.END}")
        print(f"  {C.D}To re-enrich, reset the 'enriched' stage from the menu.{C.END}")
        return

    print(f"  {C.W}Profiles needing enrichment: {len(unenriched_handles)}{C.END}")
    print(f"\n  {C.BOLD}Options:{C.END}")
    print(f"  {C.B}a{C.END}  Enrich all {len(unenriched_handles)} profiles")
    print(f"  {C.B}n{C.END}  Enrich specific number")
    print(f"  {C.B}0{C.END}  Cancel")
    choice = input(f"\n  {C.W}▸ {C.END}").strip().lower()

    if choice == "0":
        return

    handles_to_enrich = unenriched_handles
    if choice == "n":
        n = input(f"  How many? ").strip()
        n = int(n) if n.isdigit() else len(unenriched_handles)
        handles_to_enrich = unenriched_handles[:n]

    print(f"\n  {C.W}Will enrich {len(handles_to_enrich)} profiles{C.END}")
    print(f"  {C.D}Estimated time: ~{len(handles_to_enrich) * PLAYWRIGHT_RATE_LIMIT // 60} minutes{C.END}")

    # Build existing enriched map from raw profiles too
    raw_map = {p["handle"]: p for p in raw_profiles}
    for h in handles_to_enrich:
        if h not in existing_enriched and h in raw_map:
            existing_enriched[h] = raw_map[h]

    # Run enrichment
    new_enriched = asyncio.run(
        enrich_with_playwright(handles_to_enrich, existing_enriched)
    )

    # Merge with existing enriched
    for ep in new_enriched:
        existing_enriched[ep["handle"]] = ep
        state.mark_processed(ep["handle"], "enriched")

    # Save
    all_enriched = list(existing_enriched.values())
    DATA_DIR.mkdir(exist_ok=True)
    with open(PROFILES_ENRICHED_FILE, "w") as f:
        json.dump(all_enriched, f, indent=2, default=str)

    state.save()

    print(f"\n  {C.G}{'═' * 40}{C.END}")
    print(f"  {C.G}✓ Enrichment complete{C.END}")
    print(f"    Newly enriched: {len(new_enriched)}")
    print(f"    Total enriched: {len(all_enriched)}")
    print(f"    Saved to: {PROFILES_ENRICHED_FILE}")


if __name__ == "__main__":
    run()
