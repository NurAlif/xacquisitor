"""
Streamlined Pipeline State Manager.
Tracks per-profile processing state and pipeline-level state.
Persists everything to data/state.json.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from config import STATE_FILE, DATA_DIR


# Pipeline stages in order
STAGES = ["mined", "enriched", "filtered", "scored", "classified", "exported"]


class PipelineState:
    """
    Tracks per-profile processing state.
    
    State structure:
    {
        "profiles": {
            "handle1": {
                "stages": {"mined": "2024-01-01T...", "enriched": "2024-01-02T..."},
            },
            ...
        },
        "pipeline": {
            "last_run": {"mined": "2024-01-01T...", ...},
            "topics_mined": ["AI agents", ...]
        }
    }
    """

    def __init__(self, state_file: Path = STATE_FILE):
        self.state_file = state_file
        self._state = self._load()

    def _load(self) -> dict:
        """Load state from JSON file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"profiles": {}, "pipeline": {"last_run": {}, "topics_mined": []}}

    def save(self):
        """Persist state to JSON file."""
        DATA_DIR.mkdir(exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self._state, f, indent=2, default=str)

    # --- Per-Profile State ---

    def mark_processed(self, handle: str, stage: str):
        """Mark a profile as processed at a given stage."""
        if handle not in self._state["profiles"]:
            self._state["profiles"][handle] = {"stages": {}}
        self._state["profiles"][handle]["stages"][stage] = datetime.utcnow().isoformat()
        self.save()

    def mark_batch_processed(self, handles: List[str], stage: str):
        """Mark multiple profiles as processed (saves once)."""
        now = datetime.utcnow().isoformat()
        for handle in handles:
            if handle not in self._state["profiles"]:
                self._state["profiles"][handle] = {"stages": {}}
            self._state["profiles"][handle]["stages"][stage] = now
        self._state["pipeline"]["last_run"][stage] = now
        self.save()

    def is_processed(self, handle: str, stage: str) -> bool:
        """Check if a profile has been processed at a given stage."""
        profile = self._state["profiles"].get(handle, {})
        return stage in profile.get("stages", {})

    def get_unprocessed(self, stage: str, from_stage: Optional[str] = None) -> List[str]:
        """
        Get handles that haven't been processed at `stage`.
        If `from_stage` is given, only considers profiles that HAVE been processed at `from_stage`.
        """
        result = []
        for handle, data in self._state["profiles"].items():
            stages = data.get("stages", {})
            if stage in stages:
                continue  # already processed
            if from_stage and from_stage not in stages:
                continue  # not yet at prerequisite stage
            result.append(handle)
        return result

    def get_processed_at(self, stage: str) -> List[str]:
        """Get all handles that have been processed at a given stage."""
        result = []
        for handle, data in self._state["profiles"].items():
            if stage in data.get("stages", {}):
                result.append(handle)
        return result

    def reset_stage(self, stage: str):
        """Remove a stage from all profiles (allows re-running)."""
        for handle in self._state["profiles"]:
            stages = self._state["profiles"][handle].get("stages", {})
            stages.pop(stage, None)
        self._state["pipeline"]["last_run"].pop(stage, None)
        self.save()

    def reset_profile_stage(self, handle: str, stage: str):
        """Remove a stage from a specific profile."""
        if handle in self._state["profiles"]:
            self._state["profiles"][handle].get("stages", {}).pop(stage, None)
            self.save()

    # --- Topics ---

    def add_topic(self, topic: str):
        """Record a new topic as pending."""
        topics = self._state["pipeline"].get("topics_mined", {})
        if not isinstance(topics, dict):
            # Migration: convert list to dict
            old_list = topics if isinstance(topics, list) else []
            topics = {t: {"status": "completed", "results": 0, "last_run": None} for t in old_list}
            self._state["pipeline"]["topics_mined"] = topics

        if topic not in topics:
            topics[topic] = {
                "status": "pending",
                "results": 0,
                "last_run": None,
                "added_at": datetime.utcnow().isoformat()
            }
            self.save()

    def update_topic_status(self, topic: str, status: str, results_count: int = 0):
        """Update a topic's mining status and result count."""
        topics = self._state["pipeline"].get("topics_mined", {})
        if not isinstance(topics, dict):
            self.add_topic(topic)  # This will also handle migration
            topics = self._state["pipeline"]["topics_mined"]

        if topic in topics:
            topics[topic]["status"] = status
            topics[topic]["results"] = results_count
            topics[topic]["last_run"] = datetime.utcnow().isoformat()
            self.save()

    def remove_topic(self, topic: str):
        """Delete a topic from the tracker."""
        topics = self._state["pipeline"].get("topics_mined", {})
        if isinstance(topics, dict) and topic in topics:
            del topics[topic]
            self.save()

    def get_topics(self) -> Dict[str, Dict]:
        """Get all topics with their status and results."""
        topics = self._state["pipeline"].get("topics_mined", {})
        if isinstance(topics, list):
            # Migration
            self.add_topic("")  # Trigger migration
            topics = self._state["pipeline"]["topics_mined"]
            topics.pop("", None)
        return topics if isinstance(topics, dict) else {}

    # --- Summary ---

    def get_summary(self) -> Dict:
        """Get a summary of pipeline state."""
        total = len(self._state["profiles"])
        counts = {}
        for stage in STAGES:
            counts[stage] = len(self.get_processed_at(stage))

        topics = self.get_topics()
        completed_topics = sum(1 for t in topics.values() if t.get("status") == "completed")

        return {
            "total_profiles": total,
            "stage_counts": counts,
            "topics_total": len(topics),
            "topics_completed": completed_topics,
            "last_run": self._state["pipeline"].get("last_run", {}),
        }

    def print_summary(self):
        """Print a formatted summary to console."""
        summary = self.get_summary()
        print("\n┌─────────────────────────────────────┐")
        print("│       Pipeline State Summary        │")
        print("├─────────────────────────────────────┤")
        print(f"│  Total Profiles: {summary['total_profiles']:<19}│")
        print(f"│  Topics: {summary['topics_completed']}/{summary['topics_total']:<12}         │")
        print("├─────────────────────────────────────┤")
        for stage, count in summary["stage_counts"].items():
            bar = "█" * min(20, int(count / max(1, summary['total_profiles']) * 20))
            print(f"│  {stage:<12} {count:>4}  {bar:<20}│")
        print("└─────────────────────────────────────┘")

    def get_all_handles(self) -> Set[str]:
        """Get all tracked handles."""
        return set(self._state["profiles"].keys())

    def add_profile(self, handle: str):
        """Register a profile handle without any stage."""
        if handle not in self._state["profiles"]:
            self._state["profiles"][handle] = {"stages": {}}

    def remove_profile(self, handle: str):
        """Remove a profile entirely from state."""
        self._state["profiles"].pop(handle, None)
        self.save()
