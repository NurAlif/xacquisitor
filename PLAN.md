# Streamlined AI Builder Scout — Design Plan

## Overview

A streamlined, pipeline-driven system for identifying early-stage AI builders. Replaces the bloated queue-based architecture with sequential CLI scripts and JSON-only storage.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────┐
│  init_from_db   │     │ 01 Mine      │     │ 02 Enrich    │
│  (one-time DB   │────▸│ Topics       │────▸│ (Playwright) │
│   seed)         │     │ (Tavily/LLM) │     │ 10 posts     │
└─────────────────┘     └──────────────┘     └──────┬───────┘
                                                     │
        ┌──────────────┐    ┌──────────────┐    ┌────▼─────────┐
        │ 05 Classify  │◂───│ 04 Score     │◂───│ 03 Filter    │
        │ (LLM+Semant.)│    │ (6-component)│    │ (10k/25d)    │
        └──────┬───────┘    └──────────────┘    └──────────────┘
               │
        ┌──────▼───────┐
        │ 06 Export    │──▸ results.json + results.csv
        │ (JSON+CSV)   │
        └──────────────┘
```

## Data Flow

Each stage reads from the previous stage's JSON and writes its own:

| Stage | Input | Output |
|-------|-------|--------|
| init_from_db | PostgreSQL | `profiles_raw.json` |
| 01_mine | Tavily API | `profiles_raw.json` (append) |
| 02_enrich | `profiles_raw.json` | `profiles_enriched.json` |
| 03_filter | `profiles_enriched.json` | `profiles_filtered.json` |
| 04_score | `profiles_filtered.json` | `profiles_scored.json` |
| 05_classify | `profiles_scored.json` | `profiles_classified.json` |
| 06_export | `profiles_classified.json` | `results.json` + `results.csv` |

## State Tracking

`data/state.json` tracks per-profile processing state and per-topic results:

```json
{
  "profiles": {
    "handle1": {"stages": {"mined": "...", "enriched": "...", "filtered": "..."}}
  },
  "pipeline": {
    "topics_mined": {
      "AI agents": {"status": "completed", "results": 42, "last_run": "..."}
    }
  }
}
```

This enables:
- **Selective mining**: Browse topics and trigger mining only for selected ones
- **Selective runs**: Only process unprocessed profiles at each stage
- **Partial runs**: Process N profiles then resume later
- **Re-runs**: Reset a stage and reprocess all profiles
- **Resume**: Pick up where you left off after interruption

## Scoring System (0–100)

| Component | Weight | Description |
|-----------|--------|-------------|
| DeepSeek LLM Eval | **0–35** | Comprehensive evaluation with full context |
| Semantic Relevance | 0–20 | Keyword frequency vs AI builder reference |
| Technical Density | 0–15 | Tiered keyword matching (3 tiers) |
| Tweet Engagement | 0–15 | Likes, retweets, views, engagement rate |
| Link & URL Analysis | 0–10 | GitHub, Product Hunt, personal site |
| Profile Completeness | 0–5 | Bio quality, metadata richness |

## Classification

Dual approach (separate from scoring):

1. **LLM Classification** — DeepSeek with comprehensive context → category + confidence + reasoning
2. **Semantic Classification** — Keyword-tier scoring per category → similarity scores

**Categories**: Early-stage founder, AI researcher, AI operator, Angel investor, Noise/others

## Usage

```bash
# Interactive CLI
python streamlined/run.py

# Individual pipelines (standalone)
python -m streamlined.pipelines.p01_mine_topics
python -m streamlined.pipelines.p02_enrich
python -m streamlined.pipelines.p03_filter
python -m streamlined.pipelines.p04_score
python -m streamlined.pipelines.p05_classify
python -m streamlined.pipelines.p06_export
```

## Requirements

- Python 3.10+
- `pydantic`, `requests`, `python-dotenv`
- `playwright` + chromium (for enrichment)
- `sqlmodel`, `psycopg2-binary` (for DB init only)
- DeepSeek API key, Tavily API key

## Rate Limits

- Playwright scrapes: **60s** between requests
- DeepSeek API calls: **10s** between requests
