"""
Streamlined Pipeline Data Models.
Pure Pydantic models — no SQLModel, no database dependencies.
All data is serialized to/from JSON files.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class Post(BaseModel):
    """A single post/tweet with engagement metrics."""
    text: str = ""
    created_at: Optional[str] = None  # ISO format string
    like_count: int = 0
    retweet_count: int = 0
    reply_count: int = 0
    view_count: int = 0
    is_reply: bool = False
    is_retweet: bool = False
    url: Optional[str] = None


class Profile(BaseModel):
    """Base profile as discovered during mining or DB import."""
    handle: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    platform_id: Optional[str] = None
    platform: str = "x"
    followers_count: Optional[int] = None
    following_count: Optional[int] = None
    tweet_count: Optional[int] = None
    verified: bool = False
    profile_url: Optional[str] = None
    profile_image_url: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    account_created_at: Optional[str] = None
    source_topic: Optional[str] = None
    found_via_tweet: Optional[str] = None  # The tweet text that surfaced this profile
    discovered_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class EnrichedProfile(Profile):
    """Profile enriched with Playwright-scraped data."""
    posts: List[Post] = []
    last_active: Optional[str] = None  # ISO format of latest post
    days_since_active: Optional[int] = None
    extracted_links: List[Dict[str, str]] = []  # [{platform, url, source}]
    has_shipping_signals: bool = False
    shipping_keywords: List[str] = []
    enriched_at: Optional[str] = None


class ScoreBreakdown(BaseModel):
    """Detailed breakdown of the 6-component signal strength score."""
    llm_eval: float = 0.0           # 0-35 (highest weight)
    llm_reasoning: str = ""
    semantic: float = 0.0           # 0-20
    technical: float = 0.0          # 0-15
    technical_keywords: List[str] = []
    tweet_engagement: float = 0.0   # 0-15
    engagement_details: Dict[str, Any] = {}
    links: float = 0.0              # 0-10
    link_details: List[Dict[str, str]] = []
    profile_completeness: float = 0.0  # 0-5


class Classification(BaseModel):
    """Dual classification result: LLM + Semantic."""
    # LLM-based classification
    llm_category: str = "Noise/others"
    llm_confidence: float = 0.0
    llm_reasoning: str = ""

    # Semantic similarity scores per category
    semantic_scores: Dict[str, float] = {}  # {category: similarity_score}
    semantic_top_category: str = "Noise/others"


class ScoredProfile(EnrichedProfile):
    """Fully scored and classified profile — the final data model."""
    signal_strength: float = 0.0
    score_breakdown: Optional[ScoreBreakdown] = None
    classification: Optional[Classification] = None
    scored_at: Optional[str] = None
    classified_at: Optional[str] = None
