#!/usr/bin/env python3
"""
Streamlined AI Builder Scout — Interactive CLI Runner.
Stateful pipeline manager with interactive menu.
"""

import sys
import os
import json
from pathlib import Path

# Add project root to path (works for both standalone and pakcage)
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from config import validate_config, DATA_DIR, COOKIES_FILE
from state import PipelineState
import cookies_util


# --- Colors ---
class C:
    H = '\033[95m'   # Header/purple
    B = '\033[94m'   # Blue
    G = '\033[92m'   # Green
    Y = '\033[93m'   # Yellow
    R = '\033[91m'   # Red
    W = '\033[97m'   # White
    D = '\033[90m'   # Dim
    BOLD = '\033[1m'
    END = '\033[0m'


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def print_banner():
    print(f"{C.H}{C.BOLD}")
    print("  ╔══════════════════════════════════════════╗")
    print("  ║   AI Builder Scout — Streamlined CLI     ║")
    print("  ╚══════════════════════════════════════════╝")
    print(f"{C.END}")


def print_state_summary(state: PipelineState):
    summary = state.get_summary()
    total = summary["total_profiles"]
    counts = summary["stage_counts"]

    print(f"\n{C.D}  ── Pipeline State ──{C.END}")
    print(f"  {C.W}Total profiles: {C.BOLD}{total}{C.END}   "
          f"{C.D}Topics: {summary['topics_completed']}/{summary['topics_total']}{C.END}")

    if total > 0:
        stages = [
            ("mined", C.B), ("enriched", C.G), ("filtered", C.Y),
            ("scored", C.H), ("classified", C.R), ("exported", C.W),
        ]
        parts = []
        for stage_name, color in stages:
            n = counts.get(stage_name, 0)
            if n > 0:
                parts.append(f"{color}{stage_name}:{n}{C.END}")
        if parts:
            print(f"  {' → '.join(parts)}")
    print()


def menu_choice(state: PipelineState) -> str:
    print(f"  {C.BOLD}Choose an action:{C.END}\n")
    print(f"  {C.B}1{C.END}  {C.BOLD}Topic Management{C.END} (Manage topics & Mine)")
    print(f"  {C.B}2{C.END}  Enrich profiles (Playwright)")
    print(f"  {C.B}3{C.END}  Filter profiles")
    print(f"  {C.B}4{C.END}  Score profiles (intelligence)")
    print(f"  {C.B}5{C.END}  Classify profiles (LLM + semantic)")
    print(f"  {C.B}6{C.END}  Export results (JSON + CSV)")
    print(f"  {C.G}7{C.END}  Manage Playwright Cookies")
    print(f"  {C.Y}8{C.END}  Run full pipeline (mine → export)")
    print(f"  {C.H}H{C.END}  {C.BOLD}Help / Instructions{C.END}")
    print(f"  {C.D}9{C.END}  View state details / Reset a stage")
    print(f"  {C.R}0{C.END}  Exit")
    print()

    choice = input(f"  {C.W}▸ {C.END}").strip().lower()
    return choice


def manage_topics():
    """Detailed topic management menu."""
    while True:
        state = PipelineState()
        topics = state.get_topics()
        
        clear_screen()
        print_banner()
        print(f"\n  {C.H}═══ Topic Management ═══{C.END}\n")
        
        if not topics:
            print(f"  {C.D}No topics tracked.{C.END}")
        else:
            print(f"  {C.BOLD}{'#':<3} {'Topic':<35} {'Status':<10} {'Results':<8}{C.END}")
            print(f"  {C.D}{'─' * 60}{C.END}")
            for i, (topic, data) in enumerate(topics.items(), 1):
                status = data.get("status", "pending")
                results = data.get("results", 0)
                color = C.G if status == "completed" else C.Y
                print(f"  {i:<3} {topic:<35} {color}{status:<10}{C.END} {results:<8}")
        
        print(f"\n  {C.BOLD}Options:{C.END}")
        print(f"  {C.B}a{C.END}  Add new topic")
        print(f"  {C.B}d{C.END}  Delete topic")
        print(f"  {C.B}m{C.END}  Mine selected topic(s)")
        print(f"  {C.B}g{C.END}  Generate topics via AI")
        print(f"  {C.B}0{C.END}  Back to main menu")
        
        choice = input(f"\n  {C.W}▸ {C.END}").strip().lower()
        
        if choice == "0":
            break
        elif choice == "a":
            t = input(f"  Enter topic to add: ").strip()
            if t:
                state.add_topic(t)
                print(f"  {C.G}✓ Topic added.{C.END}")
        elif choice == "d":
            idx = input(f"  Enter topic number to delete: ").strip()
            if idx.isdigit():
                idx = int(idx)
                topic_list = list(topics.keys())
                if 1 <= idx <= len(topic_list):
                    t = topic_list[idx-1]
                    state.remove_topic(t)
                    print(f"  {C.R}✗ Topic deleted.{C.END}")
        elif choice == "m":
            indices = input(f"  Enter topic numbers to mine (e.g. 1,3,4 or 'all'): ").strip().lower()
            topic_list = list(topics.keys())
            selected = []
            if indices == "all":
                selected = topic_list
            else:
                for part in indices.replace(",", " ").split():
                    if part.isdigit():
                        idx = int(part)
                        if 1 <= idx <= len(topic_list):
                            selected.append(topic_list[idx-1])
            
            if selected:
                from pipelines.p01_mine_topics import run as mine_run
                mine_run(selected_topics=selected)
                input(f"\n  {C.D}Mining complete. Press Enter to continue...{C.END}")
        elif choice == "g":
            from pipelines.p01_mine_topics import generate_topics_llm
            print(f"  {C.D}Generating 5 topics via AI...{C.END}")
            new_topics = generate_topics_llm(5)
            if new_topics:
                for t in new_topics:
                    state.add_topic(t)
                print(f"  {C.G}✓ Generated and added {len(new_topics)} topics.{C.END}")
            input(f"\n  {C.D}Press Enter to continue...{C.END}")





def manage_cookies():
    """Menu to manage Playwright cookies."""
    while True:
        clear_screen()
        print_banner()
        print(f"\n  {C.H}═══ Cookie Management ═══{C.END}\n")
        
        exists = COOKIES_FILE.exists()
        status = f"{C.G}✓ Found{C.END}" if exists else f"{C.R}✗ Missing{C.END}"
        print(f"  Current Status: {status}")
        if exists:
            try:
                cookies = json.loads(COOKIES_FILE.read_text())
                print(f"  Count: {len(cookies)} cookies")
            except:
                print(f"  {C.R}Error reading cookies file.{C.END}")
        
        print(f"\n  {C.BOLD}Options:{C.END}")
        print(f"  {C.B}1{C.END}  Paste cookies (JSON)")
        print(f"  {C.B}2{C.END}  Import from file path")
        print(f"  {C.B}0{C.END}  Back to main menu")
        
        choice = input(f"\n  {C.W}▸ {C.END}").strip()
        
        if choice == "0":
            break
        elif choice == "1":
            print(f"\n  Paste JSON cookies here and press Enter + Ctrl-D (on Linux) to save:")
            print(f"  {C.D}(Or just press Enter to cancel){C.END}")
            user_input = sys.stdin.read().strip()
            if user_input:
                try:
                    valid_cookies = cookies_util.validate_cookies(user_input)
                    cookies_util.save_cookies(valid_cookies, COOKIES_FILE)
                    print(f"\n  {C.G}✓ Successfully saved {len(valid_cookies)} cookies.{C.END}")
                except Exception as e:
                    print(f"\n  {C.R}✗ Failed: {e}{C.END}")
            input(f"\n  Press Enter to continue...")
        elif choice == "2":
            path_str = input(f"  Enter path to cookie JSON file: ").strip()
            if path_str:
                path = Path(path_str)
                if path.exists():
                    try:
                        valid_cookies = cookies_util.validate_cookies(path.read_text())
                        cookies_util.save_cookies(valid_cookies, COOKIES_FILE)
                        print(f"  {C.G}✓ Successfully imported {len(valid_cookies)} cookies.{C.END}")
                    except Exception as e:
                        print(f"  {C.R}✗ Failed: {e}{C.END}")
                else:
                    print(f"  {C.R}✗ File not found.{C.END}")
            input(f"\n  Press Enter to continue...")


def run_mine_topics():
    """Run topic mining pipeline."""
    print(f"\n{C.H}═══ Mine Profiles from Topics ═══{C.END}\n")
    from pipelines.p01_mine_topics import run as mine_run
    mine_run()


def run_enrich():
    """Run enrichment pipeline."""
    print(f"\n{C.H}═══ Enrich Profiles (Playwright) ═══{C.END}\n")
    from pipelines.p02_enrich import run as enrich_run
    enrich_run()


def run_filter():
    """Run filtering pipeline."""
    print(f"\n{C.H}═══ Filter Profiles ═══{C.END}\n")
    from pipelines.p03_filter import run as filter_run
    filter_run()


def run_score():
    """Run scoring pipeline."""
    print(f"\n{C.H}═══ Score Profiles (Intelligence) ═══{C.END}\n")
    from pipelines.p04_score import run as score_run
    score_run()


def run_classify():
    """Run classification pipeline."""
    print(f"\n{C.H}═══ Classify Profiles ═══{C.END}\n")
    from pipelines.p05_classify import run as classify_run
    classify_run()


def run_export():
    """Run export pipeline."""
    print(f"\n{C.H}═══ Export Results ═══{C.END}\n")
    from pipelines.p06_export import run as export_run
    export_run()


def run_full_pipeline():
    """Run full pipeline from mining to export."""
    print(f"\n{C.H}═══ Full Pipeline ═══{C.END}\n")
    print(f"  {C.B}1{C.END}  Full pipeline: mine → enrich → filter → score → classify → export")
    print(f"  {C.B}2{C.END}  From enrichment: enrich → filter → score → classify → export")
    print(f"  {C.B}3{C.END}  From scoring: score → classify → export")
    print(f"  {C.B}0{C.END}  Cancel")
    choice = input(f"\n  {C.W}▸ {C.END}").strip()

    if choice == "1":
        run_mine_topics()
        run_enrich()
        run_filter()
        run_score()
        run_classify()
        run_export()
    elif choice == "2":
        run_enrich()
        run_filter()
        run_score()
        run_classify()
        run_export()
    elif choice == "3":
        run_score()
        run_classify()
        run_export()
    else:
        print("  Cancelled.")


def view_state_details():
    """View detailed state and optionally reset stages."""
    state = PipelineState()
    state.print_summary()

    print(f"\n  {C.D}Options:{C.END}")
    print(f"  {C.B}r{C.END}  Reset a stage (re-run all profiles at that stage)")
    print(f"  {C.B}p{C.END}  Show profiles at a stage")
    print(f"  {C.B}t{C.END}  Show mined topics")
    print(f"  {C.B}0{C.END}  Back to menu")
    choice = input(f"\n  {C.W}▸ {C.END}").strip().lower()

    if choice == "r":
        print(f"\n  Stages: {', '.join(['mined', 'enriched', 'filtered', 'scored', 'classified', 'exported'])}")
        stage = input(f"  Stage to reset: ").strip().lower()
        if stage in ["mined", "enriched", "filtered", "scored", "classified", "exported"]:
            confirm = input(f"  {C.R}Reset '{stage}' for all profiles? (y/N): {C.END}").strip().lower()
            if confirm == "y":
                state.reset_stage(stage)
                print(f"  {C.G}✓ Stage '{stage}' reset.{C.END}")
        else:
            print(f"  {C.R}Invalid stage.{C.END}")

    elif choice == "p":
        stage = input(f"  Stage (mined/enriched/filtered/scored/classified): ").strip().lower()
        handles = state.get_processed_at(stage)
        print(f"\n  {C.W}{len(handles)} profiles at '{stage}':{C.END}")
        for h in handles[:30]:
            print(f"    @{h}")
        if len(handles) > 30:
            print(f"    ... and {len(handles) - 30} more")

    elif choice == "t":
        topics = state.get_topics()
        print(f"\n  {C.W}Mined topics ({len(topics)}):{C.END}")
        for t in topics:
            print(f"    • {t}")


def main():
    """Main CLI loop."""
    state = PipelineState()

    while True:
        clear_screen()
        print_banner()
        print_state_summary(state)

        choice = menu_choice(state)

        try:
            if choice == "0":
                print(f"\n  {C.D}Goodbye!{C.END}\n")
                break
            elif choice == "1":
                manage_topics()
            elif choice == "2":
                run_enrich()
            elif choice == "3":
                run_filter()
            elif choice == "4":
                run_score()
            elif choice == "5":
                run_classify()
            elif choice == "6":
                run_export()
            elif choice == "7":
                manage_cookies()
            elif choice == "8":
                run_full_pipeline()
            elif choice == "h":
                show_help()
            elif choice == "9":
                view_state_details()
            else:
                print(f"  {C.R}Invalid choice.{C.END}")
        except KeyboardInterrupt:
            print(f"\n\n  {C.Y}Interrupted. Returning to menu...{C.END}")
        except Exception as e:
            print(f"\n  {C.R}Error: {e}{C.END}")
            import traceback
            traceback.print_exc()

        # Reload state after each action
        state = PipelineState()
        input(f"\n  {C.D}Press Enter to continue...{C.END}")


def show_help():
    """Display instructions and app flow."""
    clear_screen()
    print_banner()
    print(f"\n  {C.H}═══ Help & Instructions ═══{C.END}\n")
    
    print(f"  {C.BOLD}1. Application Flow:{C.END}")
    print(f"  {C.B}Mine{C.END}      → Find X handles using Tavily search (Topic Management).")
    print(f"  {C.B}Enrich{C.END}    → Use Playwright to scrape full profile data & latest 10 posts.")
    print(f"  {C.B}Filter{C.END}    → Automatically drop low-follower or inactive accounts.")
    print(f"  {C.B}Score{C.END}     → 6-component IQ score including DeepSeek LLM evaluation.")
    print(f"  {C.B}Classify{C.END}  → Categorize into Founder, Researcher, Operator, or Investor.")
    print(f"  {C.B}Export{C.END}    → Generate clean JSON and CSV results for outreach.")
    
    print(f"\n  {C.BOLD}2. Topic Management:{C.END}")
    print(f"  - This is where you feed the engine keywords or queries.")
    print(f"  - You can enter queries like \"AI agent builder\" or \"shipped a new LLM tool\".")
    print(f"  - {C.G}AI Generation{C.END}: Let DeepSeek suggest high-signal search queries for you.")
    print(f"  - The engine searches Tavily to find profile URLs and extracts the handles.")
    
    print(f"\n  {C.BOLD}3. Cookie Management:{C.END}")
    print(f"  - Enrichment requires a logged-in X session to avoid aggressive rate limits.")
    print(f"  - Install a browser extension like 'EditThisCookie' or 'Cookie-Editor'.")
    print(f"  - Log into X.com in your browser, export cookies as {C.Y}JSON{C.END}, and paste them here.")
    print(f"  - This app uses these cookies to impersonate your session safely via Playwright.")
    
    print(f"\n  {C.BOLD}4. Pro Tips:{C.END}")
    print(f"  - Use {C.BOLD}Option 8{C.END} to run the entire pipeline end-to-end.")
    print(f"  - If a stage fails (e.g. rate limit), you can resume exactly where you left off.")
    print(f"  - All data is saved in the {C.BOLD}data/{C.END} directory.")
    
    print(f"\n  {C.D}Press Enter to return to main menu...{C.END}")
    input()


if __name__ == "__main__":
    main()
