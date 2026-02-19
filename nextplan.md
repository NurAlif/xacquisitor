# Continuous Automated Pipeline — Scaling Plan (v2)

## Current State: Streamlined CLI Pipeline

### Overview

The existing system (`streamlined/`) is a **sequential, CLI-driven pipeline** for discovering AI builders on X/Twitter. Designed for simplicity and local development, it replaces an earlier complex queue-based architecture with straightforward Python scripts.

### Current Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────┐
│  init_from_db   │     │ 01 Mine      │     │ 02 Enrich    │
│  (one-time DB   │────▶│ Topics       │────▶│ (Playwright) │
│   seed)         │     │ (Tavily/LLM) │     │ 10 posts     │
└─────────────────┘     └──────────────┘     └──────┬───────┘
                                                     │
        ┌──────────────┐    ┌──────────────┐    ┌────▼─────────┐
        │ 05 Classify  │◀───│ 04 Score     │◀───│ 03 Filter    │
        │ (LLM+Semant.)│    │ (6-component)│    │ (10k/25d)    │
        └──────┬───────┘    └──────────────┘    └──────────────┘
               │
        ┌──────▼───────┐
        │ 06 Export    │──▶ results.json + results.csv
        │ (JSON+CSV)   │
        └──────────────┘
```

### Key Characteristics

| Aspect | Current Approach |
|--------|------------------|
| **Execution** | Manual CLI triggers (`python streamlined/run.py`) |
| **Data Flow** | Sequential JSON files (raw → enriched → filtered → scored → classified → export) |
| **Storage** | Local JSON files in `data/` directory |
| **State** | `data/state.json` tracks per-profile stage completion |
| **Scraping** | Playwright (single browser, 60s rate limit) |
| **Discovery** | Tavily API search + LLM-generated topics |
| **Scoring** | 6-component system (LLM eval, semantic, technical, engagement, links, completeness) |
| **Deduplication** | Handle-based exact match only |

### Current Limitations

| Limitation | Impact |
|------------|--------|
| **Manual operation** | Requires human to trigger each run |
| **Single-threaded** | One profile at a time, ~1 profile/minute |
| **No fault tolerance** | Script fails = manual intervention |
| **Playwright-dependent** | Cookie expiration, UI changes break scraping |
| **Limited deduplication** | Same person with different handles = duplicate |
| **No real-time visibility** | Check JSON files or CLI output for status |
| **Local-only** | Cannot scale across machines |
| **No API access** | Data only via file reads |

### Current Performance

- **Throughput:** ~50 profiles/day (manual, limited by rate limits)
- **Enrichment success rate:** ~85%
- **Duplicate rate:** ~10%
- **Cost:** ~$0.10/profile (Tavily + DeepSeek API)
- **Human intervention:** Required per run

---

## Scaling Vision

Transform the current CLI-driven pipeline into a **continuous, automated discovery engine** that runs 24/7, constantly finding, enriching, and scoring new AI builders with minimal human intervention.

**Key Philosophy:** Multi-modality scraping, platform-agnostic data, centralized orchestration, cloud-native infrastructure.

**Target Performance:**
- **Throughput:** 500-2,000 profiles/day (10-40x improvement)
- **Enrichment success rate:** >95%
- **Duplicate rate:** <2%
- **Cost:** ~$0.02/profile (5x reduction)
- **Human intervention:** Weekly review only

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CONTROLLER (The Brain)                               │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │ Strategy         │  │ Health           │  │ Dynamic Routing          │  │
│  │ Dispatcher       │  │ Monitor          │  │ (switch scraping method) │  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────────────────────────┘  │
└───────────┼─────────────────────┼───────────────────────────────────────────┘
            │                     │
            ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      MINING NODES (The Muscle)                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ X API Node   │  │ Apify Node   │  │ Playwright   │  │ GitHub Node  │    │
│  │ (Tier 1)     │  │ (Tier 2)     │  │ (Tier 3)     │  │ (Cross-ref)  │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ ProductHunt  │  │ HuggingFace  │  │ LinkedIn     │  │ Recursive    │    │
│  │ Node         │  │ Node         │  │ Node         │  │ (@mentions)  │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      NORMALIZATION LAYER                                     │
│  Raw JSON → InternalProfile Schema → Entity Resolution → Canonical Storage  │
└─────────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CENTRALIZED STORAGE LAYER                               │
│  ┌─────────────────────┐  ┌─────────────────┐  ┌────────────────────────┐  │
│  │ PostgreSQL (RDS)    │  │ Redis (ElastiCache) │  │ S3 (Raw Lake)       │  │
│  │ - Profiles          │  │ - Queue           │  │ - Raw HTML/JSON      │  │
│  │ - Scores            │  │ - Bloom Filter    │  │ - Audit Trail        │  │
│  │ - Relationships     │  │ - Rate Limiting   │  │                      │  │
│  └─────────────────────┘  └─────────────────┘  └────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Multi-Source Ingestion & Enrichment Strategy

### Why Playwright Alone Is Not Future-Proof

| Issue | Impact | Mitigation |
|-------|--------|------------|
| **Fragile to UI changes** | X changes HTML → scraper breaks | Multi-tier approach |
| **Cookie dependency** | Cookies expire, accounts get flagged | Rotate authentication sources |
| **Rate limiting** | IP bans, CAPTCHAs | Distributed proxy networks |
| **Maintenance overhead** | Selectors drift, constant updates | Abstraction layer |
| **Scale limitations** | Browser instances are heavy | Use APIs for bulk, Playwright for edge cases |

**Conclusion:** Playwright is excellent for prototyping and low-volume scraping, but production systems need **multi-modality ingestion**.

---

### Tiered Extraction Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                    TIER 1: Official APIs                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ X API v2 (Twitter API)                                     │  │
│  │ - Cost: $100-5000/month (Basic to Enterprise)             │  │
│  │ - Rate: 10K-1M tweets/month                               │  │
│  │ - Pros: Stable, legal, structured data                    │  │
│  │ - Cons: Expensive at scale, limited historical access     │  │
│  │                                                           │  │
│  │ Use Case: High-priority builders, real-time monitoring    │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              TIER 2: Third-Party Proxy APIs                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Apify (Twitter Scraper Actors)                             │  │
│  │ - Cost: $0.10-0.50 per 100 results                        │  │
│  │ - Pros: Handles proxies, rotation, anti-detection         │  │
│  │ - Cons: Can be MORE expensive than official API at scale  │  │
│  │                                                           │  │
│  │ Bright Data (Web Scraper IDE)                              │  │
│  │ - Cost: $15/GB scraped + proxy fees                       │  │
│  │ - Pros: Enterprise-grade, compliant                       │  │
│  │ - Cons: Complex pricing, overkill for small scale         │  │
│  │                                                           │  │
│  │ SocialData API                                             │  │
│  │ - Cost: $50-500/month                                     │  │
│  │ - Pros: X-specific, good documentation                    │  │
│  │ - Cons: Limited features vs official API                  │  │
│  │                                                           │  │
│  │ ScrapingBee / ScraperAPI                                   │  │
│  │ - Cost: $0.001-0.01 per request                           │  │
│  │ - Pros: Simple, handles headless browsers                 │  │
│  │ - Cons: Generic (not X-optimized)                         │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│           TIER 3: Self-Hosted Playwright/Puppeteer               │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Distributed Browser Cluster                                │  │
│  │ - Cost: Compute only (~$0.01 per profile)                 │  │
│  │ - Pros: Cheapest at scale, full control                   │  │
│  │ - Cons: High maintenance, cookie management, IP rotation  │  │
│  │                                                           │  │
│  │ Use Case: Fallback when APIs fail, specialized scraping   │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Cost Comparison (10,000 profiles/month)

| Method | Estimated Cost | Maintenance | Reliability |
|--------|---------------|-------------|-------------|
| X API v2 (Basic) | $100-500/month | Low | High |
| Apify Actors | $100-300/month | Low | Medium-High |
| Bright Data | $150-400/month | Low | High |
| Self-hosted Playwright | $20-50/month (compute) | High | Medium |
| **Hybrid (Recommended)** | **$50-150/month** | Medium | High |

**Hybrid Strategy:**
- 70% via Tier 2 (Apify/SocialData) — bulk ingestion
- 20% via Tier 1 (X API) — high-priority targets
- 10% via Tier 3 (Playwright) — fallback, edge cases

---

### Recursive Discovery Engine

```python
def recursive_discovery(high_scoring_profile: dict) -> List[str]:
    """
    Extract new discovery seeds from processed profiles.
    """
    seeds = []
    
    # 1. Extract @mentions from tweets
    for post in profile.get("posts", []):
        mentions = re.findall(r"@(\w+)", post.get("text", ""))
        seeds.extend(mentions)
    
    # 2. Extract GitHub repos from links
    for link in profile.get("extracted_links", []):
        if "github.com" in link["url"]:
            repo = extract_github_repo(link["url"])
            contributors = github_api.get_contributors(repo)
            seeds.extend(contributors)
    
    # 3. Cross-platform bridge
    if profile.get("website"):
        linkedin_profile = find_linkedin_from_website(profile["website"])
        if linkedin_profile:
            seeds.append(linkedin_profile)
    
    return deduplicate(seeds)
```

**Benefit:** Each high-quality profile discovery leads to 3-5 new candidates, creating a **viral discovery loop**.

---

### GitHub Cross-Validation

```python
def validate_shipping_via_github(handle: str, github_username: str) -> dict:
    """
    Cross-validate "shipping" signals by analyzing GitHub activity.
    """
    repo = github_api.get_user_repos(github_username)
    
    return {
        "commit_frequency": repo.commits_last_30_days,
        "technical_density": analyze_code_quality(repo),
        "ai_signals": detect_ai_projects(repo),  # LLM, ML, agents keywords
        "collaboration": repo.contributors_count,
        "traction": repo.stars_growth_rate,
    }
```

---

## 2. Normalization Layer (The "Data Standardizer")

### Why Normalization Matters

Different sources return different schemas:
```json
// X API v2
{
  "data": {
    "id": "123456789",
    "username": "builder",
    "public_metrics": { "followers_count": 1000 }
  }
}

// Apify
{
  "id": "987654321",
  "handle": "@builder",
  "stats": { "followers": 1000 }
}

// Playwright (scraped)
{
  "screen_name": "builder",
  "followers_count": "1K"
}
```

### InternalProfile Schema

```python
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class InternalProfile(BaseModel):
    """Canonical profile schema — platform agnostic."""
    
    # Immutable identifiers
    canonical_id: str  # Generated UUID
    source_id: str     # Original platform ID (X user ID, GitHub ID, etc.)
    source_platform: str  # "x", "github", "linkedin", "producthunt"
    
    # Core identity
    handle: str  # @username (may change)
    display_name: Optional[str]
    bio: Optional[str]
    
    # Cross-platform links
    linked_profiles: List[dict]  # [{platform, handle, url, verified}]
    
    # Metrics (normalized)
    followers_count: Optional[int]
    following_count: Optional[int]
    content_count: Optional[int]
    
    # Content
    recent_posts: List[dict]  # Unified post schema
    extracted_links: List[dict]
    
    # Signals
    shipping_signals: List[str]
    technical_keywords: List[str]
    
    # Metadata
    first_discovered_at: datetime
    last_enriched_at: datetime
    enrichment_quality: str  # "high", "medium", "low", "partial"
    
    # Processing state
    pipeline_stage: str  # "raw", "enriched", "scored", "classified"
```

### Entity Resolution

```python
class EntityResolver:
    """
    Link handles/identities across platforms to build unified "Builder Identity".
    """
    
    def resolve(self, profile: InternalProfile) -> Optional[str]:
        """
        Returns existing canonical_id if match found, else creates new.
        """
        # Level 1: Exact source_id match (fastest)
        existing = db.query("SELECT canonical_id FROM profiles WHERE source_id = ?", profile.source_id)
        if existing:
            return existing.canonical_id
        
        # Level 2: Handle + platform match
        existing = db.query("""
            SELECT canonical_id FROM profiles 
            WHERE handle = ? AND source_platform = ?
        """, profile.handle, profile.source_platform)
        if existing:
            return existing.canonical_id
        
        # Level 3: Fuzzy match (name + bio similarity)
        existing = db.query("""
            SELECT canonical_id, display_name, bio FROM profiles
            WHERE similarity(display_name, ?) > 0.9
        """, profile.display_name)
        
        for candidate in existing:
            if jaccard_similarity(candidate.bio, profile.bio) > 0.7:
                return candidate.canonical_id
        
        # Level 4: Cross-platform link matching
        if profile.linked_profiles:
            for link in profile.linked_profiles:
                existing = db.query("""
                    SELECT canonical_id FROM linked_profiles
                    WHERE platform = ? AND handle = ?
                """, link.platform, link.handle)
                if existing:
                    return existing.canonical_id
        
        # No match — create new identity
        return create_new_canonical_id()
```

### Normalization Pipeline

```
Raw Source Data → Schema Mapper → Entity Resolver → Canonical Profile → Storage
       │                │               │                  │
       │                │               │                  │
   (X API,         (Transform      (Link to          (InternalProfile
   Apify,           fields to       existing          written to
   Playwright)      InternalProfile)  identity)         PostgreSQL)
```

---

## 3. Centralized Controller Architecture

### The Controller (Brain)

```python
class PipelineController:
    """
    Centralized orchestration — makes real-time decisions about:
    - Which scraping method to use
    - How to route work based on health/cost/urgency
    - When to scale workers up/down
    """
    
    def __init__(self):
        self.health_monitor = HealthMonitor()
        self.strategy_dispatcher = StrategyDispatcher()
        self.queue_manager = QueueManager()
    
    def dispatch_batch(self, profiles: List[InternalProfile]) -> None:
        """
        Decide which mining node handles each profile.
        """
        for profile in profiles:
            # Get current health metrics
            health = self.health_monitor.get_all()
            
            # Decision logic
            if profile.priority == "high":
                # Use official API for important targets
                method = "x_api_v2" if health["x_api"]["success_rate"] > 0.95 else "apify"
            elif health["playwright"]["success_rate"] < 0.80:
                # Playwright failing — route to API
                method = "apify" if health["apify"]["success_rate"] > 0.90 else "x_api_v2"
            elif self.queue_manager.depth("apify") > 1000:
                # Apify queue backed up — use fallback
                method = "playwright"
            else:
                # Default: cost-optimized routing
                method = self.cost_optimizer.select_cheapest_available(health)
            
            # Route to appropriate queue
            self.queue_manager.enqueue(method, profile)
```

### Strategy Dispatcher

```python
class StrategyDispatcher:
    """
    Dynamic routing table — decides scraping approach per batch.
    """
    
    ROUTING_RULES = [
        # Rule 1: API credit management
        {
            "condition": lambda ctx: ctx.x_api_credits_remaining < 1000,
            "action": "route_to_apify",
            "priority": 1,
        },
        # Rule 2: Playwright failure detection
        {
            "condition": lambda ctx: ctx.playwright_error_rate > 0.15,
            "action": "shift_to_tier2",
            "priority": 2,
        },
        # Rule 3: Cost optimization
        {
            "condition": lambda ctx: ctx.apify_cost_per_profile < ctx.x_api_cost * 0.5,
            "action": "prefer_apify",
            "priority": 3,
        },
        # Rule 4: Urgency-based routing
        {
            "condition": lambda ctx: ctx.profile.priority == "urgent",
            "action": "use_most_reliable",
            "priority": 0,  # Highest priority
        },
    ]
    
    def select_strategy(self, context: RoutingContext) -> str:
        """
        Evaluate rules in priority order, return selected method.
        """
        for rule in sorted(self.ROUTING_RULES, key=lambda r: r["priority"]):
            if rule["condition"](context):
                return rule["action"]
        
        return "default_cost_optimized"
```

### Health Monitor

```python
class HealthMonitor:
    """
    Track performance of all mining nodes in real-time.
    """
    
    def __init__(self):
        self.metrics = {
            "x_api_v2": NodeMetrics(),
            "apify": NodeMetrics(),
            "playwright": NodeMetrics(),
            "github": NodeMetrics(),
        }
    
    def record_success(self, node: str, duration_ms: int):
        self.metrics[node].record_success(duration_ms)
    
    def record_failure(self, node: str, error_code: int):
        self.metrics[node].record_failure(error_code)
    
    def get_all(self) -> dict:
        return {
            node: {
                "success_rate": metrics.success_rate_last_hour,
                "avg_latency_ms": metrics.avg_latency,
                "requests_per_minute": metrics.rpm,
                "error_breakdown": metrics.error_codes,
            }
            for node, metrics in self.metrics.items()
        }
    
    def is_healthy(self, node: str) -> bool:
        metrics = self.metrics[node]
        return (
            metrics.success_rate_last_hour > 0.90 and
            metrics.circuit_breaker_state != "OPEN"
        )
```

### Mining Nodes (Muscle)

```yaml
Node Characteristics:
  - Stateless: No persistent state, fetch work from queue
  - Single-purpose: Each node type does ONE thing well
  - Self-reporting: Push metrics back to controller
  - Graceful degradation: Handle errors locally, report failures

Deployment:
  - Docker containers (one image per node type)
  - Auto-scaled based on queue depth
  - Health checks every 30 seconds
  - Automatic restart on failure
```

---

## 4. Infrastructure & Storage: Cloud-Native Design

### Compute Options Comparison

| Provider | Service | Best For | Cost Model |
|----------|---------|----------|------------|
| **AWS** | ECS/Fargate | Production workloads | Pay-per-second |
| **AWS** | Lambda | Burst scraping, event-driven | Pay-per-request |
| **GCP** | Cloud Run | Simple deployment, auto-scale | Pay-per-request |
| **GCP** | Cloud Functions | Event-driven, lightweight | Pay-per-invocation |
| **Azure** | Container Apps | Enterprise integration | Pay-per-second |
| **Azure** | Functions | Microsoft ecosystem | Pay-per-execution |

### Recommended: AWS Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AWS Cloud Architecture                           │
│                                                                          │
│  ┌─────────────────┐    ┌─────────────────────────────────────────────┐ │
│  │ CloudWatch      │    │              ECS Cluster                     │ │
│  │ Events          │───▶│  ┌─────────┐  ┌─────────┐  ┌─────────┐     │ │
│  │ (Scheduler)     │    │  │ X API   │  │ Apify   │  │ Play-   │     │ │
│  └─────────────────┘    │  │ Worker  │  │ Worker  │  │ wright  │     │ │
│                         │  └─────────┘  └─────────┘  └─────────┘     │ │
│                         │  ┌─────────┐  ┌─────────┐  ┌─────────┐     │ │
│                         │  │ GitHub  │  │ Score   │  │ Export  │     │ │
│                         │  │ Worker  │  │ Worker  │  │ Worker  │     │ │
│                         │  └─────────┘  └─────────┘  └─────────┘     │ │
│                         └─────────────────────────────────────────────┘ │
│                                    │                                     │
│                                    ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                      Data Layer                                      │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │ │
│  │  │ RDS          │  │ ElastiCache  │  │ S3                        │  │ │
│  │  │ (PostgreSQL) │  │ (Redis)      │  │ - Raw scraping payloads  │  │ │
│  │  │ - Profiles   │  │ - Queue      │  │ - Enrichment cache       │  │ │
│  │  │ - Scores     │  │ - Bloom      │  │ - Export files           │  │ │
│  │  │ - Links      │  │ - Rate limit │  │                          │  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                      Observability                                   │ │
│  │  CloudWatch Logs │ CloudWatch Metrics │ X-Ray (tracing)            │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why Docker?

```yaml
Benefits:
  - Consistency: Same container runs locally, in CI, and in production
  - Isolation: Each worker has its dependencies (Playwright, API SDKs)
  - Portability: Move between AWS, GCP, Azure without code changes
  - Scaling: Kubernetes/ECS can auto-scale containers based on metrics
  - Version control: Tag containers, rollback easily

Example Dockerfile (Playwright Worker):
  FROM python:3.11-slim
  RUN pip install playwright && playwright install chromium
  COPY worker.py /app/worker.py
  CMD ["python", "/app/worker.py"]
```

---

### Storage Architecture

#### Centralized vs Distributed

| Aspect | Centralized | Distributed |
|--------|-------------|-------------|
| Complexity | Low | High |
| Consistency | Strong | Eventual |
| Cost | Lower (single instance) | Higher (multiple regions) |
| Latency | Single region | Edge caching possible |
| **Recommendation** | ✅ Start here | Scale to this later |

**Start Centralized:** Single RDS instance, single Redis cluster, single S3 bucket.

**Scale Later:** Read replicas for PostgreSQL, Redis Cluster, S3 Cross-Region Replication.

---

### Database Selection

#### Primary Database: PostgreSQL (RDS)

```sql
-- Why PostgreSQL?
-- 1. Relational data (profiles → posts → links → scores)
-- 2. JSONB support (store raw payloads alongside structured data)
-- 3. Full-text search (tsvector for bio/tweet search)
-- 4. pgvector extension (semantic similarity search)
-- 5. Mature, reliable, well-supported on all cloud providers

-- Core tables
CREATE TABLE profiles (
    canonical_id UUID PRIMARY KEY,
    source_id VARCHAR(255) NOT NULL,
    source_platform VARCHAR(50) NOT NULL,
    handle VARCHAR(100) NOT NULL,
    display_name VARCHAR(255),
    bio TEXT,
    followers_count INTEGER,
    following_count INTEGER,
    raw_payload JSONB,  -- Store original API response
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_id, source_platform)
);

CREATE TABLE profile_links (
    id SERIAL PRIMARY KEY,
    canonical_id UUID REFERENCES profiles(canonical_id),
    linked_platform VARCHAR(50),
    linked_handle VARCHAR(100),
    linked_url TEXT,
    verified BOOLEAN DEFAULT FALSE
);

CREATE TABLE scores (
    canonical_id UUID PRIMARY KEY REFERENCES profiles(canonical_id),
    overall_score DECIMAL(5,2),
    llm_score DECIMAL(5,2),
    technical_score DECIMAL(5,2),
    engagement_score DECIMAL(5,2),
    shipping_score DECIMAL(5,2),
    classification VARCHAR(100),
    classification_confidence DECIMAL(5,2),
    scored_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_profiles_handle ON profiles(handle);
CREATE INDEX idx_profiles_followers ON profiles(followers_count DESC);
CREATE INDEX idx_profiles_raw_gin ON profiles USING GIN(raw_payload);
```

---

### Why Redis? (vs Alternatives)

| Feature | Redis | RabbitMQ | SQS | Kafka |
|---------|-------|----------|-----|-------|
| **Queue Operations** | ✅ Lists/Streams | ✅ Native | ✅ Native | ✅ Streams |
| **Latency** | <1ms | ~5ms | ~50ms | ~10ms |
| **Pub/Sub** | ✅ Built-in | ✅ Built-in | ❌ | ✅ Built-in |
| **Caching** | ✅ Native | ❌ | ❌ | ❌ |
| **Bloom Filter** | ✅ RedisBloom | ❌ | ❌ | ❌ |
| **Rate Limiting** | ✅ INCR + TTL | ❌ | ❌ | ❌ |
| **Persistence** | Optional | Yes | Yes | Yes |
| **Complexity** | Low | Medium | Low | High |
| **Cost** | $ | $$ | $ | $$$ |

**Why Redis Wins:**
1. **Multi-purpose:** Queue + Cache + Rate Limiter + Bloom Filter in one
2. **Extreme low-latency:** Critical for high-throughput scraping
3. **Simple operations:** LPUSH/BRPOP for queue, SET/GET for cache, INCR for rate limiting
4. **RedisBloom:** Native bloom filter for O(1) deduplication
5. **Atomic operations:** Critical for distributed rate limiting

**When to consider alternatives:**
- **Exactly-once delivery needed:** SQS or Kafka
- **Message ordering critical:** Kafka
- **Complex routing:** RabbitMQ
- **Massive scale (1M+ msg/sec):** Kafka

---

### Queue Architecture with Redis

```python
# Queue structure in Redis
QUEUES = {
    "queue:mining:x_api": [],      # Profiles to mine via X API
    "queue:mining:apify": [],      # Profiles to mine via Apify
    "queue:mining:playwright": [], # Profiles to mine via Playwright
    "queue:enrichment": [],        # Profiles to enrich
    "queue:scoring": [],           # Profiles to score
    "queue:classification": [],    # Profiles to classify
    "queue:export": [],            # Profiles to export
    "queue:dlq": [],               # Failed profiles (Dead Letter Queue)
}

# Bloom filter for deduplication (RedisBloom module)
# PFADD x:handles:all <handle>  # Add handle
# PFEXISTS x:handles:all <handle>  # Check if exists (O(1))

# Rate limiting (sliding window)
# Key: ratelimit:apify:2024-01-01-12-05
# Value: count of requests in this minute
```

---

### Do We Need Cron?

**Answer: Yes, but cloud-native version.**

| Scheduler | Use Case | Pros | Cons |
|-----------|----------|------|------|
| **CloudWatch Events** | AWS-native scheduling | Integrated, reliable, free for basic use | AWS-only |
| **Google Cloud Scheduler** | GCP-native | HTTP targets, App Engine integration | GCP-only |
| **Azure Logic Apps** | Azure-native | Visual workflow designer | Azure-only, expensive |
| **Celery Beat** | Self-hosted | Python-native, flexible | Requires management |
| **Kubernetes CronJob** | K8s environments | Native to K8s, declarative | K8s required |

**Recommended: CloudWatch Events (AWS)**

```yaml
# EventBridge rule (runs every hour)
Schedule: cron(0 * * * ? *)
Target: ECS Task (Controller)

# EventBridge rule (runs daily at 2 AM UTC)
Schedule: cron(0 2 * * ? *)
Target: ECS Task (Topic Discovery + Cleanup)
```

**Why not local cron?**
- No visibility into execution
- No retry logic
- No centralized logging
- Single point of failure
- Hard to manage across environments

---

## 5. Basic Error Handling Strategy

### Exponential Backoff (All API Calls)

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type((RateLimitError, ConnectionError, TimeoutError)),
    reraise=True
)
def call_api(endpoint: str, data: dict) -> dict:
    """API call with automatic exponential backoff."""
    response = requests.post(endpoint, json=data, timeout=30)
    response.raise_for_status()
    return response.json()
```

---

### Circuit Breakers

```python
from pybreaker import CircuitBreaker

# Per-service circuit breakers
x_api_breaker = CircuitBreaker(fail_max=5, reset_timeout=60)
apify_breaker = CircuitBreaker(fail_max=5, reset_timeout=120)
playwright_breaker = CircuitBreaker(fail_max=3, reset_timeout=300)

@x_api_breaker
def call_x_api(handle: str) -> dict:
    return x_api.get_profile(handle)

# Usage in controller:
try:
    profile = call_x_api(handle)
except CircuitBreakerError:
    # Circuit is OPEN — route to alternative
    controller.route_to_alternative(handle, preferred="apify")
```

**Circuit States:**
- **CLOSED:** Normal operation, requests flow through
- **OPEN:** Too many failures, reject immediately, route elsewhere
- **HALF-OPEN:** Testing recovery, allow one request through

---

### Dead Letter Queue (DLQ)

```python
class DeadLetterHandler:
    """
    Handle profiles that fail processing repeatedly.
    """
    
    def send_to_dlq(self, profile: InternalProfile, error: str, attempts: int):
        """
        Move failed profile to DLQ for manual review or alternative processing.
        """
        dlq_entry = {
            "profile": profile.dict(),
            "error": error,
            "attempts": attempts,
            "last_failed_at": datetime.utcnow().isoformat(),
            "suggested_action": self.suggest_action(error),
        }
        
        redis.lpush("queue:dlq", json.dumps(dlq_entry))
        
        # Alert if DLQ growing too fast
        dlq_size = redis.llen("queue:dlq")
        if dlq_size > 100:
            alerting.send_slack(f"⚠️ DLQ size: {dlq_size} profiles")
    
    def suggest_action(self, error: str) -> str:
        """Suggest remediation based on error type."""
        if "403" in error or "401" in error:
            return "Try alternative authentication method"
        elif "timeout" in error.lower():
            return "Retry with longer timeout or different node"
        elif "not found" in error.lower():
            return "Profile may be deleted — mark as inactive"
        else:
            return "Manual review required"
    
    def reprocess_dlq(self, target_method: str = None):
        """
        Reprocess DLQ entries with alternative method.
        """
        while redis.llen("queue:dlq") > 0:
            entry = json.loads(redis.rpop("queue:dlq"))
            profile = InternalProfile(**entry["profile"])
            
            # Route to specified method or auto-select
            if target_method:
                queue_manager.enqueue(target_method, profile)
            else:
                # Auto-select based on error
                if "playwright" in entry["error"].lower():
                    queue_manager.enqueue("apify", profile)
                else:
                    queue_manager.enqueue("playwright", profile)
```

---

### Graceful Degradation

```python
def enrich_profile_with_fallbacks(handle: str) -> InternalProfile:
    """
    Enrich profile with cascading fallbacks.
    """
    profile = InternalProfile(handle=handle, enrichment_quality="unknown")
    
    # Attempt 1: Full enrichment via Playwright
    try:
        return playwright_enrich(handle)  # Returns full InternalProfile
    except PlaywrightError as e:
        log.warning(f"Playwright failed for @{handle}: {e}")
        profile.enrichment_quality = "degraded"
    
    # Attempt 2: API-based enrichment (less data but reliable)
    try:
        api_data = x_api.get_profile(handle)
        profile = api_to_internal(api_data)
        profile.enrichment_quality = "partial"
        return profile
    except XAPIError as e:
        log.warning(f"X API failed for @{handle}: {e}")
        profile.enrichment_quality = "minimal"
    
    # Attempt 3: Cached/stale data
    cached = redis.get(f"profile:cache:{handle}")
    if cached:
        profile = InternalProfile(**json.loads(cached))
        profile.enrichment_quality = "stale"
        profile.is_cached = True
        return profile
    
    # Attempt 4: Minimal profile (just handle)
    profile.enrichment_quality = "none"
    profile.partial = True
    return profile
```

---

### Monitoring & Alerting

```yaml
Key Metrics (CloudWatch/Prometheus):
  - pipeline_throughput: profiles_processed_per_hour
  - queue_depth_by_stage: {mining, enrichment, scoring, classification}
  - error_rate_by_node: {x_api, apify, playwright, github}
  - api_success_rate: percentage of successful API calls
  - enrichment_quality_distribution: {high, medium, low, partial}
  - dlq_size: number of profiles in dead letter queue
  - cost_per_profile: running total

Alerts (SNS/Slack):
  - Error rate > 10% for 5 minutes → Page on-call
  - Queue depth > 1000 → Scale up workers
  - DLQ size > 100 → Investigate failures
  - API success rate < 90% → Check credentials/limits
  - Pipeline stalled (no progress 30 min) → Auto-restart workers
  - Cost per profile > $0.05 → Review routing strategy

Dashboard (Grafana/CloudWatch):
  - Real-time pipeline visualization
  - Worker health status
  - Queue depth over time
  - Error breakdown by type
  - Cost tracking
```

---

## 6. Data Processing, Analysis & Dashboard

### Data Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA PROCESSING FLOW                                 │
│                                                                              │
│  Raw Data → Cleaning → Transformation → Aggregation → Analytics → Serving   │
│     │          │           │              │             │            │       │
│     │          │           │              │             │            │       │
│  ┌───▼───┐  ┌──▼───┐   ┌───▼───┐     ┌───▼────┐   ┌───▼────┐   ┌───▼───┐  │
│  │ S3    │  │ Null │   │ Feature│     │ Time   │   │ ML     │   │ API   │  │
│  │ (Raw) │  │ Fill │   │ Eng.   │     │ Window │   │ Models │   │ Layer │  │
│  └───────┘  └──────┘   └────────┘     └────────┘   └────────┘   └───────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### ETL Pipeline Stages

```python
class ProfileETLPipeline:
    """
    Transform raw profiles into analytics-ready data.
    """
    
    def extract(self) -> pd.DataFrame:
        """Pull from PostgreSQL with incremental loading."""
        return db.query("""
            SELECT * FROM profiles 
            WHERE updated_at > :last_sync
        """, last_sync=self.last_checkpoint)
    
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean, enrich, and feature-engineer."""
        # Cleaning
        df = df.drop_duplicates(subset=['canonical_id'])
        df['bio'] = df['bio'].fillna('').str.strip()
        df['followers_count'] = df['followers_count'].fillna(0)
        
        # Feature Engineering
        df['follower_growth_rate'] = self.calc_growth_rate(df)
        df['engagement_rate'] = df['avg_likes'] / (df['followers_count'] + 1)
        df['posting_frequency'] = df['tweet_count'] / df['account_age_days']
        df['shipping_velocity'] = self.calc_shipping_velocity(df)
        df['technical_score'] = self.calc_technical_density(df['bio'] + df['recent_posts'])
        
        # Categorization
        df['follower_tier'] = pd.cut(df['followers_count'], 
                                      bins=[0, 100, 1000, 10000, 100000, float('inf')],
                                      labels=['nano', 'micro', 'mid', 'macro', 'influencer'])
        df['activity_level'] = pd.cut(df['posting_frequency'],
                                       bins=[0, 0.1, 0.5, 1.0, float('inf')],
                                       labels=['inactive', 'casual', 'active', 'very_active'])
        
        return df
    
    def load(self, df: pd.DataFrame):
        """Write to analytics-optimized storage."""
        # Write to ClickHouse for fast OLAP queries
        clickhouse.insert('profiles_analytics', df)
        
        # Update materialized views in PostgreSQL
        self.refresh_materialized_views()
        
        # Cache aggregations in Redis
        self.cache_aggregations(df)
```

---

### Dashboard Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         AI BUILDER SCOUT DASHBOARD                            │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  REAL-TIME PIPELINE MONITORING                                          │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │ │
│  │  │ Mining   │  │Enrichment│  │ Scoring  │  │Classify  │  │ Export   │ │ │
│  │  │   523    │  │   412    │  │   389    │  │   356    │  │   340    │ │ │
│  │  │  ▲ 12%   │  │  ▲ 8%    │  │  ▼ 3%    │  │  ▲ 5%    │  │  ▲ 15%   │ │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
│  ┌─────────────────────────────┐  ┌─────────────────────────────────────────┐│
│  │  DISCOVERY TREND            │  │  TOP BUILDERS (24H)                     ││
│  │  ┌───────────────────────┐  │  │  ┌───────────────────────────────────┐  ││
│  │  │   ╱╲    ╱╲            │  │  │  │ 1. @builder1   Score: 94  ▲ New   │  ││
│  │  │  ╱  ╲  ╱  ╲   ╱╲       │  │  │  │ 2. @founder2   Score: 91  ▲ +5   │  ││
│  │  │ ╱    ╲╱    ╲ ╱  ╲      │  │  │  │ 3. @maker3     Score: 89  ▼ -2   │  ││
│  │  │                        │  │  │  │ 4. @dev4       Score: 87  ▲ +12  │  ││
│  │  │  0    6   12   18  24h │  │  │  │ 5. @creator5   Score: 85  ▲ New  │  ││
│  │  └───────────────────────┘  │  │  └───────────────────────────────────┘  ││
│  └─────────────────────────────┘  └─────────────────────────────────────────┘│
│                                                                               │
│  ┌─────────────────────────────┐  ┌─────────────────────────────────────────┐│
│  │  CLASSIFICATION BREAKDOWN   │  │  SHIPPING SIGNALS (7 DAYS)              ││
│  │  ┌───────────────────────┐  │  │  ┌───────────────────────────────────┐  ││
│  │  │      Early Founder    │  │  │  │                                   │  ││
│  │  │     ████████░░ 68%    │  │  │  │  42 builders shipped this week    │  ││
│  │  │      AI Researcher    │  │  │  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │  ││
│  │  │     ████░░░░░░ 35%    │  │  │  │                                   │  ││
│  │  │      AI Operator      │  │  │  │  Top launches:                    │  ││
│  │  │     ██████░░░░ 52%    │  │  │  │  • AgentKit v2 (123 upvotes)      │  ││
│  │  │      Angel Investor   │  │  │  │  • LLM Studio beta                │  ││
│  │  │     ██░░░░░░░░ 18%    │  │  │  │  • VectorDB launch                │  ││
│  │  └───────────────────────┘  │  │  └───────────────────────────────────┘  ││
│  └─────────────────────────────┘  └─────────────────────────────────────────┘│
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  NETWORK GRAPH: BUILDER CONNECTIONS                                     │ │
│  │  ┌───────────────────────────────────────────────────────────────────┐  │ │
│  │  │        ○────○────○                                                │  │ │
│  │  │       ╱      ╲    ╲                                               │  │ │
│  │  │      ○        ○────○────○  ← Cluster: AI Agents                   │  │ │
│  │  │       ╲      ╱    ╱                                               │  │ │
│  │  │        ○────○────○                                                │  │ │
│  │  │              ╲                                                    │  │ │
│  │  │               ○────○  ← Cluster: LLM Infrastructure               │  │ │
│  │  └───────────────────────────────────────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### Dashboard Views

#### 1. **Pipeline Health View** (Operations)

```yaml
Purpose: Monitor pipeline performance in real-time
Audience: Engineering/Operations team
Refresh Rate: 30 seconds

Key Metrics:
  - Throughput: profiles/hour by stage
  - Error Rates: by node (X API, Apify, Playwright)
  - Queue Depth: pending items per stage
  - Worker Status: healthy/degraded/failed
  - Cost Tracking: $/profile, daily spend

Alerts:
  - Queue depth > threshold
  - Error rate spike
  - Worker failures
  - Budget exceeded
```

#### 2. **Discovery Analytics View** (Investment Insights)

```yaml
Purpose: Understand builder discovery trends
Audience: Investment team, analysts
Refresh Rate: 5 minutes

Key Metrics:
  - New builders discovered (daily/weekly)
  - Discovery source breakdown (Tavily, X API, GitHub, etc.)
  - Quality distribution (score ranges)
  - Classification breakdown
  - Geographic distribution
  - Follower tier distribution

Visualizations:
  - Time series: discoveries over time
  - Funnel: mined → enriched → scored → high-quality
  - Pie charts: classification, source breakdown
  - Map: geographic heatmap
```

#### 3. **Builder Intelligence View** (Deep Dives)

```yaml
Purpose: Analyze individual builders and segments
Audience: Investment team
Refresh Rate: 1 hour

Features:
  - Search & filter builders
  - Builder profile cards (full enrichment data)
  - Comparison tool (side-by-side builder comparison)
  - Shipping timeline (when did they ship what)
  - Network view (who they interact with)
  - Trend analysis (follower growth, engagement trends)

Segments:
  - Top 100 builders (by score)
  - Rising stars (fastest growing followers)
  - Active shippers (shipped in last 7 days)
  - Hidden gems (high score, low followers)
  - Cross-platform builders (active on X + GitHub)
```

#### 4. **Market Intelligence View** (Trends)

```yaml
Purpose: Identify macro trends in AI builder ecosystem
Audience: Strategy, investment committee
Refresh Rate: Daily

Analyses:
  - Trending topics (what are builders talking about)
  - Emerging categories (new classification clusters)
  - Shipping velocity by category
  - Funding signal detection (who's raising)
  - Competitive landscape (who's building similar things)
  - Talent flow (who's joining which companies)

Visualizations:
  - Word clouds (trending keywords)
  - Topic evolution over time
  - Category growth charts
  - Correlation matrices
```

---

### Analysis Approaches

#### 1. **Descriptive Analytics** (What happened?)

```python
# Aggregation queries
def daily_discovery_summary() -> pd.DataFrame:
    return db.query("""
        SELECT 
            DATE(created_at) as date,
            COUNT(*) as new_builders,
            AVG(overall_score) as avg_score,
            COUNT(CASE WHEN overall_score > 80 THEN 1 END) as high_quality,
            classification,
            COUNT(*) as by_classification
        FROM profiles
        GROUP BY DATE(created_at), classification
        ORDER BY date DESC
    """)

# Cohort analysis
def cohort_retention() -> pd.DataFrame:
    """Analyze builder activity over time."""
    return db.query("""
        WITH cohorts AS (
            SELECT 
                canonical_id,
                DATE_TRUNC('month', first_discovered_at) as cohort_month,
                DATEDIFF(day, first_discovered_at, CURRENT_DATE) as days_since_discovery
            FROM profiles
        )
        SELECT 
            cohort_month,
            days_since_discovery,
            COUNT(DISTINCT canonical_id) as active_builders
        FROM cohorts
        JOIN profile_activity USING (canonical_id)
        GROUP BY cohort_month, days_since_discovery
    """)
```

#### 2. **Diagnostic Analytics** (Why did it happen?)

```python
def analyze_score_distribution():
    """Understand what drives high scores."""
    df = db.query("""
        SELECT 
            overall_score,
            llm_score,
            technical_score,
            engagement_score,
            shipping_score,
            followers_count,
            posting_frequency
        FROM scores
        JOIN profiles USING (canonical_id)
    """)
    
    # Correlation analysis
    correlation_matrix = df.corr()
    
    # Feature importance (what predicts high overall score)
    from sklearn.ensemble import RandomForestRegressor
    model = RandomForestRegressor()
    model.fit(df[['llm_score', 'technical_score', 'engagement_score', 'shipping_score']], 
              df['overall_score'])
    
    return {
        'correlations': correlation_matrix,
        'feature_importance': model.feature_importances_
    }

def root_cause_analysis(error_spike: str):
    """Diagnose sudden error rate increases."""
    # Break down by node, time, error type
    return db.query("""
        SELECT 
            node_name,
            DATE_TRUNC('hour', error_timestamp) as hour,
            error_type,
            COUNT(*) as error_count
        FROM pipeline_errors
        WHERE error_timestamp > NOW() - INTERVAL '24 hours'
        GROUP BY node_name, hour, error_type
        ORDER BY hour DESC, error_count DESC
    """)
```

#### 3. **Predictive Analytics** (What will happen?)

```python
class BuilderSuccessPredictor:
    """
    Predict which builders are likely to gain traction.
    """
    
    def train(self, historical_data: pd.DataFrame):
        """
        Train on historical builders, label = achieved traction (funding, users, etc.)
        """
        features = [
            'initial_followers',
            'follower_growth_rate',
            'engagement_rate',
            'shipping_frequency',
            'technical_score',
            'network_centrality',
            'posting_consistency',
        ]
        
        X = historical_data[features]
        y = historical_data['achieved_traction']  # Binary: raised funding or not
        
        self.model = XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1
        )
        self.model.fit(X, y)
    
    def predict(self, builders: pd.DataFrame) -> pd.DataFrame:
        """Predict traction probability for new builders."""
        builders['traction_probability'] = self.model.predict_proba(builders[features])[:, 1]
        return builders.sort_values('traction_probability', ascending=False)

def trending_topic_predictor() -> List[str]:
    """
    Predict emerging topics before they go mainstream.
    """
    # Time series analysis on keyword frequency
    topics = db.query("""
        SELECT 
            keyword,
            DATE_TRUNC('week', mentioned_at) as week,
            COUNT(*) as mentions
        FROM keyword_mentions
        WHERE mentioned_at > NOW() - INTERVAL '12 weeks'
        GROUP BY keyword, week
    """)
    
    # Calculate growth rate for each topic
    topic_growth = calculate_growth_rate(topics)
    
    # Return topics with accelerating growth
    return topic_growth[
        (topic_growth['growth_rate'] > 0.5) & 
        (topic_growth['acceleration'] > 0.1)
    ]['keyword'].tolist()
```

#### 4. **Prescriptive Analytics** (What should we do?)

```python
class DiscoveryOptimizer:
    """
    Recommend optimal discovery strategies.
    """
    
    def recommend_topics(self) -> List[str]:
        """
        Suggest which topics to mine next for highest ROI.
        """
        # Analyze historical topic performance
        topic_performance = db.query("""
            SELECT 
                topic,
                COUNT(*) as profiles_found,
                AVG(overall_score) as avg_quality,
                COUNT(CASE WHEN overall_score > 80 THEN 1 END) * 1.0 / COUNT(*) as high_quality_rate
            FROM mining_results
            GROUP BY topic
        """)
        
        # Score topics by quality and quantity
        topic_performance['roi_score'] = (
            topic_performance['high_quality_rate'] * 0.6 +
            (topic_performance['profiles_found'] / topic_performance['profiles_found'].max()) * 0.4
        )
        
        # Recommend under-explored high-quality topics
        return topic_performance.nlargest(10, 'roi_score')['topic'].tolist()
    
    def recommend_routing(self, profile: dict) -> str:
        """
        Recommend which enrichment method to use for a profile.
        """
        # Based on profile characteristics, predict best enrichment success
        if profile['priority'] == 'high':
            return 'x_api_v2'  # Most reliable
        elif profile['followers_count'] > 10000:
            return 'apify'  # Good for active accounts
        else:
            return 'playwright'  # Cost-effective for smaller accounts
```

#### 5. **Network Analysis**

```python
import networkx as nx

class BuilderNetworkAnalyzer:
    """
    Analyze builder connections and influence patterns.
    """
    
    def build_network(self) -> nx.Graph:
        """
        Build graph from @mentions, replies, collaborations.
        """
        G = nx.DiGraph()
        
        # Add nodes (builders)
        builders = db.query("SELECT canonical_id, overall_score FROM profiles")
        for b in builders:
            G.add_node(b.canonical_id, score=b.overall_score)
        
        # Add edges (interactions)
        interactions = db.query("""
            SELECT 
                from_profile_id,
                to_profile_id,
                interaction_type,
                COUNT(*) as weight
            FROM profile_interactions
            GROUP BY from_profile_id, to_profile_id, interaction_type
        """)
        
        for edge in interactions:
            G.add_edge(
                edge.from_profile_id, 
                edge.to_profile_id, 
                weight=edge.weight,
                type=edge.interaction_type
            )
        
        return G
    
    def find_influencers(self, G: nx.Graph) -> List[str]:
        """
        Identify central nodes (influencers) in the network.
        """
        # PageRank for influence scoring
        pagerank = nx.pagerank(G, weight='weight')
        
        # Betweenness centrality (bridges between clusters)
        betweenness = nx.betweenness_centrality(G, weight='weight')
        
        # Combine metrics
        influence_scores = {
            node: 0.7 * pagerank[node] + 0.3 * betweenness[node]
            for node in G.nodes()
        }
        
        return sorted(influence_scores.items(), key=lambda x: x[1], reverse=True)[:20]
    
    def detect_communities(self, G: nx.Graph) -> List[dict]:
        """
        Find clusters of builders (by topic, collaboration).
        """
        communities = nx.community.louvain_communities(G, weight='weight')
        
        return [
            {
                'community_id': i,
                'members': list(comm),
                'size': len(comm),
                'avg_score': np.mean([G.nodes[m]['score'] for m in comm])
            }
            for i, comm in enumerate(communities)
        ]
```

---

### Insights You Can Gain

#### 1. **Builder Quality Insights**

| Insight | Description | Action |
|---------|-------------|--------|
| Hidden Gems | High scores, low followers (<1K) | Prioritize for early outreach |
| Rising Stars | Fastest follower growth (7-day) | Monitor for momentum |
| Serial Shippers | Multiple launches in 90 days | Strong execution signal |
| Network Hubs | High centrality in builder graph | Amplifiers, potential advisors |
| Cross-Platform | Active on X + GitHub + PH | More credible, multi-signal |

#### 2. **Market Trend Insights**

| Insight | Description | Action |
|---------|-------------|--------|
| Emerging Categories | New classification clusters appearing | Adjust thesis, explore new areas |
| Shipping Waves | Spikes in launches by category | Market heating up, competitive |
| Topic Momentum | Keywords accelerating in frequency | Early signal of trend |
| Geographic Clusters | Builder concentration by region | Regional investment opportunities |
| Talent Migration | Builders moving between companies | Where is talent flowing |

#### 3. **Pipeline Optimization Insights**

| Insight | Description | Action |
|---------|-------------|--------|
| Source Quality | Which discovery sources yield best builders | Reallocate budget |
| Method Success | Enrichment method success rates | Adjust routing rules |
| Bottleneck Detection | Stage with highest queue buildup | Scale that stage |
| Cost per Quality | $ spent per high-score builder | Optimize spending |
| False Positive Analysis | High-score builders that turned out low-quality | Refine scoring model |

#### 4. **Competitive Intelligence**

| Insight | Description | Action |
|---------|-------------|--------|
| Competitor Tracking | Builders associated with competing firms | Monitor their thesis |
| White Space | Categories with few high-quality builders | Investment opportunity |
| Overcrowded Spaces | Many builders, similar products | Avoid or differentiate |
| Partnership Signals | Builders who frequently collaborate | Potential portfolio synergies |

---

### Infrastructure for Analytics

#### Data Stack

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ANALYTICS INFRASTRUCTURE                             │
│                                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────────────┐ │
│  │  PostgreSQL  │────▶│  Airbyte/    │────▶│  Data Warehouse              │ │
│  │  (OLTP)      │     │  Fivetran    │     │  (ClickHouse/BigQuery)       │ │
│  └──────────────┘     └──────────────┘     └──────────────┬───────────────┘ │
│                                                           │                   │
│                                                           ▼                   │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────────────┐ │
│  │  Metabase/   │◀────│  dbt         │◀────│  Transformations             │ │
│  │  Superset    │     │  (Models)    │     │  (Aggregations, Features)    │ │
│  └──────────────┘     └──────────────┘     └──────────────────────────────┘ │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────────┐│
│  │  ML/Analysis Layer                                                        ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────────┐  ││
│  │  │  Jupyter    │  │  Feature    │  │  Model Registry                 │  ││
│  │  │  Notebooks  │  │  Store      │  │  (MLflow)                       │  ││
│  │  └─────────────┘  └─────────────┘  └─────────────────────────────────┘  ││
│  └──────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Technology Choices

| Layer | Option A (Cloud) | Option B (Self-Hosted) | Recommendation |
|-------|------------------|------------------------|----------------|
| **Data Warehouse** | BigQuery, Snowflake | ClickHouse | ClickHouse (cost-effective, fast) |
| **ETL/ELT** | Fivetran, Airbyte Cloud | Airbyte OSS | Airbyte OSS (flexible) |
| **Transformation** | dbt Cloud | dbt Core | dbt Core (same tool, free) |
| **BI/Dashboard** | Looker, Tableau | Metabase, Superset | Metabase (simple, free tier) |
| **Feature Store** | Tecton, Feast | Feast OSS | Feast (open source) |
| **ML Platform** | SageMaker, Vertex AI | MLflow | MLflow (lightweight) |
| **API Layer** | AWS API Gateway | FastAPI + ECS | FastAPI (flexible, Python) |

---

### API Design for Data Access

```python
from fastapi import FastAPI, Depends, Query
from typing import List, Optional

app = FastAPI(title="AI Builder Scout API")

# --- Builder Endpoints ---

@app.get("/api/v1/builders")
def list_builders(
    min_score: int = Query(70, ge=0, le=100),
    classification: Optional[str] = None,
    follower_tier: Optional[str] = None,
    sort_by: str = Query("overall_score", enum=["overall_score", "followers_count", "discovered_at"]),
    limit: int = Query(50, le=500),
    offset: int = 0,
) -> List[Builder]:
    """Search and filter builders."""
    return db.query("""
        SELECT * FROM profiles_analytics
        WHERE overall_score >= :min_score
        AND (:classification IS NULL OR classification = :classification)
        AND (:follower_tier IS NULL OR follower_tier = :follower_tier)
        ORDER BY {sort_by} DESC
        LIMIT :limit OFFSET :offset
    """, min_score=min_score, classification=classification, 
        follower_tier=follower_tier, sort_by=sort_by, limit=limit, offset=offset)

@app.get("/api/v1/builders/{canonical_id}")
def get_builder(canonical_id: str) -> Builder:
    """Get full builder profile with all enrichment data."""
    return db.query("""
        SELECT 
            p.*,
            s.*,
            ARRAY_AGG(DISTINCT lp.linked_platform || ':' || lp.linked_handle) as linked_profiles,
            ARRAY_AGG(DISTINCT p2.canonical_id) FILTER (WHERE p2.canonical_id IS NOT NULL) as related_builders
        FROM profiles p
        JOIN scores s ON p.canonical_id = s.canonical_id
        LEFT JOIN linked_profiles lp ON p.canonical_id = lp.canonical_id
        LEFT JOIN profile_interactions pi ON p.canonical_id = pi.from_profile_id
        LEFT JOIN profiles p2 ON pi.to_profile_id = p2.canonical_id
        WHERE p.canonical_id = :canonical_id
        GROUP BY p.canonical_id, s.canonical_id
    """, canonical_id=canonical_id)

# --- Analytics Endpoints ---

@app.get("/api/v1/analytics/summary")
def get_analytics_summary(
    period: str = Query("7d", enum=["24h", "7d", "30d", "90d"])
) -> AnalyticsSummary:
    """High-level analytics summary."""
    return {
        "new_builders": get_new_builders_count(period),
        "avg_score": get_average_score(period),
        "classification_breakdown": get_classification_breakdown(period),
        "top_topics": get_trending_topics(period),
        "shipping_count": get_shipping_count(period),
    }

@app.get("/api/v1/analytics/trends")
def get_trends(
    metric: str = Query("discoveries", enum=["discoveries", "avg_score", "shipping"]),
    granularity: str = Query("day", enum=["hour", "day", "week", "month"]),
) -> List[TrendPoint]:
    """Time series trends for key metrics."""
    return db.query("""
        SELECT 
            DATE_TRUNC(:granularity, discovered_at) as period,
            COUNT(*) as value
        FROM profiles
        WHERE discovered_at > NOW() - INTERVAL '90 days'
        GROUP BY period
        ORDER BY period
    """, granularity=granularity)

# --- Pipeline Health Endpoints ---

@app.get("/api/v1/pipeline/health")
def get_pipeline_health() -> PipelineHealth:
    """Real-time pipeline health metrics."""
    return {
        "stage_throughput": get_stage_throughput(),
        "error_rates": get_error_rates_by_node(),
        "queue_depths": get_queue_depths(),
        "worker_status": get_worker_health(),
        "cost_tracking": get_daily_cost(),
    }

@app.get("/api/v1/pipeline/alerts")
def get_active_alerts() -> List[Alert]:
    """Current active alerts."""
    return db.query("""
        SELECT * FROM pipeline_alerts
        WHERE resolved_at IS NULL
        ORDER BY created_at DESC
    """)

# --- Insights Endpoints ---

@app.get("/api/v1/insights/hidden-gems")
def get_hidden_gems(limit: int = 20) -> List[Builder]:
    """High-score builders with low followers."""
    return db.query("""
        SELECT * FROM profiles_analytics
        WHERE overall_score >= 80
        AND followers_count < 1000
        ORDER BY overall_score DESC
        LIMIT :limit
    """, limit=limit)

@app.get("/api/v1/insights/rising-stars")
def get_rising_stars(limit: int = 20) -> List[Builder]:
    """Builders with fastest follower growth."""
    return db.query("""
        SELECT *, 
            (followers_count - followers_count_7d_ago) / NULLIF(followers_count_7d_ago, 0) as growth_rate
        FROM profiles_analytics
        WHERE followers_count_7d_ago > 0
        ORDER BY growth_rate DESC
        LIMIT :limit
    """, limit=limit)

@app.get("/api/v1/insights/network/influencers")
def get_network_influencers() -> List[NetworkNode]:
    """Most influential builders by network centrality."""
    return network_analyzer.find_influencers()

@app.get("/api/v1/insights/topics/recommended")
def get_recommended_topics() -> List[str]:
    """Topics recommended for mining (highest ROI)."""
    return discovery_optimizer.recommend_topics()
```

---

### Monitoring the Analysis Pipeline

```python
class AnalyticsMonitor:
    """
    Monitor data quality and analysis pipeline health.
    """
    
    def check_data_freshness(self) -> DataFreshnessReport:
        """Ensure analytics data is up-to-date."""
        return db.query("""
            SELECT 
                'profiles' as table_name,
                MAX(updated_at) as last_update,
                NOW() - MAX(updated_at) as lag
            FROM profiles
            UNION ALL
            SELECT 
                'scores' as table_name,
                MAX(scored_at) as last_update,
                NOW() - MAX(scored_at) as lag
            FROM scores
        """)
    
    def check_data_quality(self) -> DataQualityReport:
        """Validate data integrity."""
        checks = {
            'null_bio_rate': self.check_null_rate('profiles', 'bio'),
            'score_distribution': self.check_score_distribution(),
            'duplicate_rate': self.check_duplicate_rate(),
            'orphan_records': self.check_orphan_records(),
        }
        
        # Alert if any check fails threshold
        for check_name, value in checks.items():
            if value > self.thresholds.get(check_name, 0.1):
                self.send_alert(f"Data quality issue: {check_name} = {value}")
        
        return checks
    
    def track_query_performance(self) -> QueryPerformanceReport:
        """Monitor slow queries in analytics."""
        return db.query("""
            SELECT 
                query,
                calls,
                mean_exec_time,
                total_exec_time
            FROM pg_stat_statements
            WHERE query LIKE '%profiles_analytics%'
            ORDER BY total_exec_time DESC
            LIMIT 10
        """)
```

---

## 7. Implementation Roadmap

### Phase 1: Foundation (Week 1-3)
- [ ] Containerize all pipeline stages (Docker)
- [ ] Set up AWS infrastructure (ECS, RDS, ElastiCache, S3)
- [ ] Implement InternalProfile schema + normalization layer
- [ ] Build basic Controller with health monitoring
- [ ] Migrate from cron to CloudWatch Events

### Phase 2: Multi-Source Ingestion (Week 4-6)
- [ ] Integrate Apify Twitter Scraper
- [ ] Implement tiered routing (Controller decides method)
- [ ] Add Redis queue + bloom filter for deduplication
- [ ] Build recursive discovery engine (@mentions extraction)
- [ ] Add GitHub cross-validation

### Phase 3: Reliability (Week 7-9)
- [ ] Implement circuit breakers for all nodes
- [ ] Build DLQ management CLI + auto-remediation
- [ ] Add exponential backoff to all API calls
- [ ] Implement graceful degradation cascade
- [ ] Set up CloudWatch dashboards + alerts

### Phase 4: Scale & Intelligence (Week 10-12)
- [ ] Auto-scaling workers based on queue depth
- [ ] Entity resolution (cross-platform identity linking)
- [ ] pgvector integration for semantic deduplication
- [ ] Cost optimization engine (dynamic routing based on price)
- [ ] Predictive discovery (ML model for high-value targets)

---

## 7. Success Metrics

| Metric | Current (CLI) | Target (3 months) | Target (6 months) |
|--------|---------------|-------------------|-------------------|
| Profiles/day | 50 (manual) | 500 (automated) | 2,000 (scaled) |
| Enrichment success rate | ~85% | >92% | >95% |
| Duplicate rate | ~10% | <5% | <2% |
| Cost per profile | $0.10 | $0.05 | $0.02 |
| Human intervention | Per run | Weekly review | Monthly audit |
| Mean time to recovery | Unknown | <15 minutes | <5 minutes |
| Pipeline availability | N/A | 95% | 99% |

---

## 8. Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| X API price increase | Medium | High | Multi-source strategy, don't depend on single source |
| Playwright detection/ban | High | Medium | Rotate proxies, use residential IPs, fallback to APIs |
| Third-party API shutdown | Low | Medium | Abstraction layer, easy to swap providers |
| Cost overrun | Medium | Medium | Budget alerts, per-profile cost tracking, daily caps |
| Data quality degradation | Medium | High | Automated quality checks, human review queue, sampling |
| Cloud provider outage | Low | High | Multi-region deployment (future), export backups |
| Cookie expiration (Playwright) | High | Low | Automated refresh, multiple accounts, API fallback |

---

## 9. Cost Projection

### Monthly Operating Costs (10,000 profiles)

| Component | AWS Service | Estimated Cost |
|-----------|-------------|----------------|
| Compute (ECS Fargate) | 2 vCPU, 4GB RAM, 500 hrs | $40 |
| Database (RDS PostgreSQL) | db.t3.small, 20GB storage | $25 |
| Cache/Queue (ElastiCache) | cache.t3.micro, Redis | $15 |
| Storage (S3) | 10GB + requests | $5 |
| X API v2 | Basic tier (10K tweets) | $100 |
| Apify | 5K results/month | $50 |
| Monitoring (CloudWatch) | Logs + Metrics | $10 |
| **Total** | | **$245/month** |

### Cost Optimization Levers
- Increase Apify ratio (cheaper than X API)
- Use Spot Instances for non-critical workers
- Implement aggressive caching
- Scale down during low-activity periods

---

## Conclusion

This plan transforms the streamlined CLI pipeline into a **production-grade, cloud-native discovery engine** with:

1. **Multi-modality ingestion** — Not dependent on Playwright alone; tiered approach balances cost, reliability, and scale
2. **Normalized data model** — Platform-agnostic InternalProfile schema ensures downstream processes work consistently
3. **Centralized intelligence** — Controller makes real-time routing decisions based on health, cost, and urgency
4. **Cloud-native infrastructure** — AWS services (ECS, RDS, ElastiCache, S3) provide scalability and reliability
5. **Comprehensive error handling** — Exponential backoff, circuit breakers, DLQ, graceful degradation
6. **Observable & maintainable** — Full monitoring, alerting, and operational tooling

**Start simple, design for scale:** Begin with centralized AWS deployment, then evolve to multi-region, multi-cloud as needed.
