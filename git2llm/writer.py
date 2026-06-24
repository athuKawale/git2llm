import os
import json
import uuid
import time
import threading
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

class DatasetWriter:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        self.dataset_path = os.path.join(output_dir, "dataset.jsonl")
        self.dataset_meta_path = os.path.join(output_dir, "dataset_with_meta.jsonl")
        self.excluded_path = os.path.join(output_dir, "excluded_log.jsonl")
        self.report_path = os.path.join(output_dir, "run_report.json")
        
        # Clear existing files if any
        for path in [self.dataset_path, self.dataset_meta_path, self.excluded_path]:
            if os.path.exists(path):
                os.remove(path)
                
        self._lock = threading.Lock()
        self.start_time = time.time()
        self.run_id = str(uuid.uuid4())
        
        # Stats tracking
        self.repos_processed: List[str] = []
        self.stats = {
            "raw_commits_collected": 0,
            "raw_prs_collected": 0,
            "stage1_hard_exclusion_dropped": 0,
            "stage2_structural_dropped": 0,
            "stage3_content_score_dropped": 0,
            "stage4_dedup_dropped": 0,
            "final_records": 0
        }
        self.top_exclusion_reasons: Dict[str, int] = {}
        self.task_distribution: Dict[str, int] = {}

    def add_repo_processed(self, repo: str):
        with self._lock:
            if repo not in self.repos_processed:
                self.repos_processed.append(repo)

    def record_raw_counts(self, commits: int = 0, prs: int = 0):
        with self._lock:
            self.stats["raw_commits_collected"] += commits
            self.stats["raw_prs_collected"] += prs

    def write_passed(self, record: Dict[str, Any], task_type: str):
        """Write a record that passed all filters to both clean and meta files."""
        with self._lock:
            # 1. Write to dataset_with_meta.jsonl (contains _meta)
            with open(self.dataset_meta_path, "a") as f:
                f.write(json.dumps(record) + "\n")
                
            # 2. Write to dataset.jsonl (stripped of _meta)
            clean_rec = {k: v for k, v in record.items() if k != "_meta"}
            with open(self.dataset_path, "a") as f:
                f.write(json.dumps(clean_rec) + "\n")
                
            self.stats["final_records"] += 1
            self.task_distribution[task_type] = self.task_distribution.get(task_type, 0) + 1

    def write_excluded(self, record: Dict[str, Any], stage: str, reason: str):
        """Write an excluded record to excluded_log.jsonl with details."""
        with self._lock:
            # Update stats
            if stage == "stage1":
                self.stats["stage1_hard_exclusion_dropped"] += 1
            elif stage == "stage2":
                self.stats["stage2_structural_dropped"] += 1
            elif stage == "stage3":
                self.stats["stage3_content_score_dropped"] += 1
            elif stage == "stage4":
                self.stats["stage4_dedup_dropped"] += 1
                
            self.top_exclusion_reasons[reason] = self.top_exclusion_reasons.get(reason, 0) + 1
            
            # Write to log
            log_entry = {
                "record": record,
                "stage_failed": stage,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            with open(self.excluded_path, "a") as f:
                f.write(json.dumps(log_entry) + "\n")

    def generate_report(self, output_format: str, task: str):
        """Generate and save the run_report.json file."""
        duration = time.time() - self.start_time
        
        # Calculate filter rate
        total_collected = self.stats["raw_commits_collected"] + self.stats["raw_prs_collected"]
        dropped = total_collected - self.stats["final_records"]
        filter_rate_pct = (dropped / total_collected * 100) if total_collected > 0 else 0.0
        
        self.stats["filter_rate_pct"] = round(filter_rate_pct, 2)
        
        report = {
            "run_id": self.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "repos_processed": self.repos_processed,
            "duration_seconds": round(duration, 2),
            "stats": self.stats,
            "top_exclusion_reasons": self.top_exclusion_reasons,
            "format": output_format,
            "task": task,
            "task_distribution": self.task_distribution
        }
        
        with open(self.report_path, "w") as f:
            json.dump(report, f, indent=2)
            
        return report
