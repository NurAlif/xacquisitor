# Streamlined AI Builder Scout

A standalone, stateful pipeline for discovering, enriching, and scoring early-stage AI builders on X (Twitter).

## Features

- **X API v2 Discovery**: Rapidly find handles by searching for keywords in recent tweets or bios.
- **AI-Assisted Personas**: Use DeepSeek LLM to brainstorm high-signal builder personas.
- **Playwright Enrichment**: Scrape bio, followers, and latest posts directly from X for deep intelligence.

## Mining Strategy

The application uses a two-layered acquisition strategy to maximize efficiency and depth:

1.  **Discovery (X API v2)**: The "Mining" stage uses the official X API v2 to search for recent activity matching your target topics. This is used for fast, broad discovery of handles without the risk of browser-based rate limits during the initial finding phase.
2.  **Enrichment (Playwright)**: Once handles are found, the app uses Playwright to perform deep scraping of the profile, bio, and last 10 posts. This bypasses the limitations of the API v2 (which often requires expensive tiers for deep data) and provides more technical context for the scoring engine.
- **Intelligence Scoring**: 6-component scoring system (0-100) using LLM evaluation and semantic analysis.
- **Dual Classification**: Categorize builders into Founders, Researchers, Operators, or Investors.
- **Export**: Results available in clean JSON and flat CSV formats.

## Setup

1.  **Clone/Copy**: Copy this directory to your desired location.
2.  **Environment**:
    ```bash
    cp .env.example .env
    # Edit .env with your DEEPSEEK_KEY and TAVILY_KEY
    ```
3.  **Install Dependencies**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```
4.  **Setup Playwright**:
    - **macOS/Linux**: `chmod +x scripts/setup_playwright.sh && ./scripts/setup_playwright.sh`
    - **Windows**: `.\scripts\setup_playwright.ps1`
5.  **Cookies**:
    - Run the app: `python run.py`
    - Go to `Manage Playwright Cookies` (Option 'C')
    - Paste your X cookies in JSON format (e.g., from "EditThisCookie" or "Cookie-Editor" extensions).

## Running

Launch the interactive CLI:
```bash
python run.py
```

## Project Structure

- `run.py`: Main interactive CLI entry point.
- `pipelines/`: Individual pipeline stage scripts.
- `data/`: Where all persistent state and results are stored.
- `models.py`: Pydantic data models.
- `config.py`: Configuration and constants.
- `state.py`: Pipeline state manager.
- `cookies_util.py`: Cookie management utilities.
