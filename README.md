# Streamlined AI Builder Scout

A standalone, stateful pipeline for discovering, enriching, and scoring early-stage AI builders on X (Twitter).

## Features

- Use the X API v2 to rapidly find handles by searching for keywords in recent tweets or bios.
- Leverage the DeepSeek LLM to brainstorm high-signal builder personas.
- Directly scrape bios, follower counts, and the latest posts from X using Playwright for deep intelligence.

## Mining Strategy

The application uses a two-layered acquisition strategy to maximize efficiency and depth. 

The "Mining" stage uses the official X API v2 to search for recent activity matching your target topics, enabling fast and broad discovery of handles without the risk of browser-based rate limits. 

Once handles are found, the app uses Playwright to perform deep scraping of profiles to bypass the limitations of the standard API and provide technical context for the scoring engine.

Other core capabilities include:
- A 6-component scoring system (0-100) that utilizes LLM evaluation and semantic analysis for intelligence.
- Dual classification that categorizes builders into Founders, Researchers, Operators, or Investors.
- Results exported into clean JSON and flat CSV formats.

## Setup

1.  **Clone/Copy**: Copy this directory to your desired location.
2.  **Environment**:
    ```bash
    cp .env.example .env
    # Edit .env with your DEEPSEEK_KEY and X_BEARER_TOKEN
    ```
3.  **Install Dependencies**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```
4.  **Setup Playwright**:
    - Linux: Execute `chmod +x scripts/setup.sh && ./scripts/setup.sh`
    - Windows: Run `.\scripts\setup_playwright.ps1`
5.  **Cookies**:
    - Run the application using `python run.py`.
    - Select the `Manage Playwright Cookies` option.
    - Paste your X cookies in JSON format from browser extensions like EditThisCookie.

## Running

Launch the interactive CLI:
```bash
python run.py
```

## Project Structure

- `run.py` serves as the main interactive CLI entry point.
- `pipelines/` contains individual scripts for each pipeline stage.
- `data/` stores all persistent state and results.
- `models.py` defines the Pydantic data models used throughout the app.
- `config.py` handles configuration and constants.
- `state.py` manages the pipeline state.
- `cookies_util.py` provides utilities for managing cookies.
