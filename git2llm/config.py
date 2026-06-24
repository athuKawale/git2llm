import os
from datetime import date
from typing import Optional, List
from pydantic import BaseModel, Field
import yaml

class FilterConfig(BaseModel):
    # Hard exclusions
    exclude_merge_commits: bool = True
    exclude_bot_authors: bool = True
    exclude_binary_only: bool = True
    exclude_revert_commits: bool = True
    
    # Structural
    min_commit_message_words: int = 5
    max_commit_message_chars: int = 500
    min_diff_lines: int = 3
    max_diff_lines: int = 500
    max_files_changed: int = 20
    min_files_changed: int = 1
    
    # Content quality
    min_content_score: float = 0.5    # 0.0–1.0
    require_verb_start: bool = True    # V-DO pattern
    exclude_wip_messages: bool = True
    
    # Dedup
    dedup_method: str = "minhash"      # "minhash" or "exact"
    dedup_threshold: float = 0.85
    
    # PR-specific
    min_pr_body_words: int = 20
    require_linked_issue: bool = False
    
class CollectionConfig(BaseModel):
    max_commits_per_repo: int = 5000
    max_prs_per_repo: int = 1000
    since: Optional[date] = None  # None or date object, e.g., date(2019, 1, 1)
    branches: List[str] = ["main", "master", "develop"]

class AppConfig(BaseModel):
    filter: FilterConfig = Field(default_factory=FilterConfig)
    collection: CollectionConfig = Field(default_factory=CollectionConfig)
    max_workers: int = 4
    output_format: str = "alpaca"
    task: str = "all"

    @classmethod
    def load_from_yaml(cls, path: str) -> "AppConfig":
        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        return cls.model_validate(data)
