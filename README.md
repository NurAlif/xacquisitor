# AI Builder Scout — Streamlined

A standalone, stateful pipeline for discovering, enriching, and scoring early-stage AI builders on X (Twitter).

## Features

- **Topic-based Mining**: Find profiles using Tavily search and DeepSeek LLM.
- **Playwright Enrichment**: Scrape bio, followers, and latest posts directly from X.
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
    playwright install chromium
    ```
4.  **Cookies**:
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
