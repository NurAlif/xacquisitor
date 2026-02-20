## 1. CURRENT STATE AND VISION
**Current State**: A sequential, single-threaded statefull pipeline using CLI interface.Utilizing local JSON filesfor storage; XAPIv2 and Playwright for data mining; and vector embedding and deepseek for analysis and classification. Using topic to search for tweets using XAPIv2 and then using playwright to scrape the profile details and tweets. The strategy is due to limited credits of XAPIv2.Limited to ~50 profiles/day with significant manual oversight.

**Target Vision**: A 24/7 cloud-native, highly available discovery engine utilizing multi-modality ingestion and intelligent orchestration to autonomously discover, enrich, and categorize the world's top AI builders.

**Philosophy**: Modular, highly scalable, fault-tolerant, and platform-agnostic architecture designed for continuous, autonomous operation.

---

## 2. ARCHITECHTURE

To achieve fault-free scaling, the architecture transitions from a linear script to a distributed, event-driven pattern:

### The Controller
A centralized orchestrator that makes real-time decisions on routing workloads. It monitors system health, tracks API costs, and dynamically assigns tasks to the most efficient extraction method. Tracks success rates, average latencies, and auto-triggers circuit breakers if APIs fail. Implement a web user interface to monitor and control the whole data aquisition operation.

### Mining Nodes
Stateless Docker containers operating as specialized workers, utilizing mixed approach and switchable mining strategy to get the best efficiency and to avoid the fragility of relying on one method. Push the result to a normalization layer to handle the different data formats from the different mining methods into normalized data structure.
- **Official APIs**: X API v2. High reliability, high cost. Used for priority targets. There are even different options of API  kind from X to use if accessible (might be cheaper).
- **Proxy Providers**: Apify, SocialData. Balances proxy management, IP rotation, and moderate cost for bulk data collection.
- **Self-Hosted Browsers**: Playwright clusters. Heaviest and most brittle, utilized as a fallback or for specialized data extraction. Unstable and hard to maintain. (Last resort but can be cheapest)

### Normalization Layer
Extracting data from diverse sources (X API, Apify, GitHub) yields inconsistent schemas. This layer converts all payloads into a standardized schema. 

**Entity Resolution Engine (Deduplication)**: Use X's account user_id identifier, not @username handle, since it can be changed. Futhermore we can matches diverse profiles using handle, bio-similarity algorithms (Jaccard), and linked cross-platform accounts to form a canonical "Builder Identity."

### Centralized Cloud Storage
- **Primary Database (RDS PostgreSQL with `pgvector`)**: Stores relational profiles, scores, and JSONB raw payloads. Replaces the need for a dedicated vector DB by handling similarity searches natively.
- **High-Speed Cache/Queue (Redis)**: Acts as a sub-millisecond task broker for workers. Uses RedisBloom for O(1) duplicate prevention without database strain.
- **Data Lake (S3)**: Highly scalable, cheap storage for bulky static files (raw HTML/dumps, ML checkpoints) to keep the primary DB lean.

### AI & Processor Nodes
To scale compute independently from scraping/proxy limits, processing is completely separated from mining:
- **Asynchronous AI Workers**: Docker containers pull scraped profiles from Redis queues, route them to LLMs (e.g., DeepSeek, openAI) for rapid scoring/classification, and write results to the DB.
- **Embedding Generation**: Dedicated compute processes generate vector embeddings for text/bios, storing them directly in PostgreSQL (`pgvector`) for native similarity clustering.
- **Multi-Modal Analysis**: Specialized vision/audio models transcribe and analyze non-text media (e.g., converting project demo videos, audio, or screenshots into text annotations) to extract maximum signal from every profile.



## 3. RELIABILITY & ERROR HANDLING

Scaling up requires systems that can gracefully fail and recover without human intervention.

- **Circuit Breakers**: If a specific API tier or proxy fails frequently, the circuit "opens" and the Controller automatically diverts traffic to fallback methods.

- **Graceful Degradation**: Instead of failing an entire run, workers attempt Tier 1, then Tier 2, then Tier 3. If all fail, partial or cached data is returned, flagged as `degraded`, allowing the pipeline to proceed without stalling.

- **Dead Letter Queues (DLQ)**: Profiles that repeatedly crash the pipeline are rerouted to a DLQ for offline analysis or manual review, preventing queue blockages.

- **Recursive viral Discovery**: Automated logic extracts `@mentions`, GitHub repos, and linked websites from high-value profiles to seed the next generation of discovery tasks, creating an infinite, self-sustaining loop.

## 4. ANALYTICS & VALUE EXTRACTION

With ingestion scaled, the value comes from connecting disparate data points to identify the strongest signals:
- **Deep Feature Engineering**: Code activity (commits/launches via GitHub integration), follower momentum, network centrality, and "shipping velocity" are computed for every enriched profile.
- **Custom BERT-based Classification**: To maximize efficiency and reduce LLM API costs over time, a fine-tuned BERT (or RoBERTa) model will be trained on the structured profiles. This allows for lightning-fast, high-throughput classification of builders without relying on expensive, high-latency generalized LLM calls.
- **Unconstrained Categorization via Clustering**: By applying dimensionality reduction (e.g., UMAP or t-SNE) to the generated vector embeddings, profiles can be algorithmically grouped into emergent clusters. This enables dynamic categorizations (e.g., discovering a new subset of "Agentic Framework Engineers") rather than forcing them into predefined, rigid tag constraints.
- **Builder Intelligence Categories**:
  - *Hidden Gems:* High technical/shipping scores but <1K followers.
  - *Rising Stars:* Strong week-over-week follower acceleration.
  - *Network Hubs:* Using Graph analysis (PageRank) to identify central figures connecting isolated developer groups.
- **Market Trends Dashboard**: Tracking the exact vocabulary and topics builders use to proactively discover emerging AI concepts before they hit the mainstream.

### Data Presentation Layer
To present this wealth of data efficiently, a specialized presentation layer will serve a high-performance Web User Interface (Dashboard):
- **Fast OLAP Database (ClickHouse)**: Aggregated analytics (shipping waves, geographical clusters, follower trends) will be pushed from PostgreSQL/Redis into ClickHouse to enable sub-second aggregations over millions of rows.
- **API Gateway (FastAPI)**: Serves the analytical queries directly to the frontend. highly flexible for advanced analytics and custom presentation.
- **Interactive Dashboard**: Features real-time pipeline monitoring, filterable builder matrices (filter by technical score, follower tier, etc.), and visual cluster maps (network graphs showing how builders are connected or clustered based on dimensionality reduction).

