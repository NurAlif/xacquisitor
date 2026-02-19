"""
Streamlined Pipeline Configuration.
Loads environment variables and defines constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR
DATA_DIR = BASE_DIR / "data"
COOKIES_FILE = BASE_DIR / "x_cookies.json"

# Create data directory if it doesn't exist
DATA_DIR.mkdir(exist_ok=True)

# --- Load .env from project root ---
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Try parent as fallback (for transition period)
    parent_env = PROJECT_ROOT.parent / ".env"
    if parent_env.exists():
        load_dotenv(parent_env)
    else:
        print(f"⚠ Warning: .env not found at {env_path}")

# --- API Keys ---
DEEPSEEK_KEY = os.getenv("deepseek_key") or os.getenv("DEEPSEEK_KEY")
X_BEARER_TOKEN = os.getenv("x_bearer_token") or os.getenv("X_BEARER_TOKEN")

# --- Constants ---
MAX_FOLLOWERS = 10_000          # Filter threshold: drop >= this
MAX_INACTIVE_DAYS = 25          # Filter threshold: drop if inactive > this
MAX_POSTS_TO_FETCH = 10         # Number of latest posts to scrape per profile
PLAYWRIGHT_RATE_LIMIT = 60      # Seconds between Playwright scrapes
LLM_REQUEST_INTERVAL = 10       # Seconds between DeepSeek API calls

# DeepSeek API config
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# --- Score Weights (rebalanced, LLM highest) ---
SCORE_WEIGHTS = {
    "llm_eval": 35,          # 0-35 (highest)
    "semantic": 20,           # 0-20
    "technical": 15,          # 0-15
    "tweet_engagement": 15,   # 0-15
    "links": 10,              # 0-10
    "profile_completeness": 5 # 0-5
}

# Classification categories
CLASSIFICATION_CATEGORIES = [
    "Early-stage founder",
    "AI researcher",
    "AI operator",
    "Angel investor",
    "Noise/others",
]

# --- Data File Paths ---
STATE_FILE = DATA_DIR / "state.json"
PROFILES_RAW_FILE = DATA_DIR / "profiles_raw.json"
PROFILES_ENRICHED_FILE = DATA_DIR / "profiles_enriched.json"
PROFILES_FILTERED_FILE = DATA_DIR / "profiles_filtered.json"
PROFILES_SCORED_FILE = DATA_DIR / "profiles_scored.json"
PROFILES_CLASSIFIED_FILE = DATA_DIR / "profiles_classified.json"
RESULTS_JSON_FILE = DATA_DIR / "results.json"
RESULTS_CSV_FILE = DATA_DIR / "results.csv"

# --- Validation ---
def validate_config():
    """Print config status for debugging."""
    print("=" * 50)
    print("  Streamlined Pipeline Configuration")
    print("=" * 50)
    print(f"  Data Dir:      {DATA_DIR}")
    print(f"  Cookies File:  {COOKIES_FILE} ({'✓' if COOKIES_FILE.exists() else '✗'})")
    print(f"  DeepSeek Key:  {'✓ Set' if DEEPSEEK_KEY else '✗ Missing'}")
    print(f"  X Bearer:      {'✓ Set' if X_BEARER_TOKEN else '✗ Missing'}")
    print("=" * 50)


if __name__ == "__main__":
    validate_config()
