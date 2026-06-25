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
    min_alignment_score: float = 0.0  # Min overlap score between commit message & diff
    require_verb_start: bool = True    # V-DO pattern
    exclude_wip_messages: bool = True
    
    # Dedup
    dedup_method: str = "minhash"      # "minhash" or "exact"
    dedup_threshold: float = 0.85
    
    # PR-specific
    min_pr_body_words: int = 20
    require_linked_issue: bool = False
    min_issue_to_patch_words: int = 20  # Minimum words in issue_to_patch description
    
class CollectionConfig(BaseModel):
    max_commits_per_repo: int = 5000
    max_prs_per_repo: int = 1000
    since: Optional[date] = None  # None or date object, e.g., date(2019, 1, 1)
    branches: List[str] = []

DEFAULT_PROFILES = {
    "default": {
        "filter": {
            "exclude_merge_commits": True,
            "exclude_bot_authors": True,
            "exclude_binary_only": True,
            "exclude_revert_commits": True,
            "min_commit_message_words": 5,
            "max_commit_message_chars": 500,
            "min_diff_lines": 3,
            "max_diff_lines": 500,
            "max_files_changed": 20,
            "min_files_changed": 1,
            "min_content_score": 0.5,
            "min_alignment_score": 0.15,
            "require_verb_start": True,
            "exclude_wip_messages": True,
            "dedup_method": "minhash",
            "dedup_threshold": 0.85,
            "min_pr_body_words": 20,
            "require_linked_issue": False,
            "min_issue_to_patch_words": 20,
        },
        "collection": {
            "max_commits_per_repo": 5000,
            "max_prs_per_repo": 1000,
            "since": None,
            "branches": [],
        },
        "output_format": "alpaca",
        "task": "all",
    },
    "strict": {
        "filter": {
            "exclude_merge_commits": True,
            "exclude_bot_authors": True,
            "exclude_binary_only": True,
            "exclude_revert_commits": True,
            "min_commit_message_words": 7,
            "max_commit_message_chars": 300,
            "min_diff_lines": 5,
            "max_diff_lines": 300,
            "max_files_changed": 10,
            "min_files_changed": 1,
            "min_content_score": 0.7,
            "min_alignment_score": 0.25,
            "require_verb_start": True,
            "exclude_wip_messages": True,
            "dedup_method": "minhash",
            "dedup_threshold": 0.80,
            "min_pr_body_words": 40,
            "require_linked_issue": True,
            "min_issue_to_patch_words": 30,
        },
        "collection": {
            "max_commits_per_repo": 1000,
            "max_prs_per_repo": 500,
            "since": date(2022, 1, 1),
            "branches": [],
        },
        "output_format": "alpaca",
        "task": "all",
    },
    "permissive": {
        "filter": {
            "exclude_merge_commits": True,
            "exclude_bot_authors": True,
            "exclude_binary_only": True,
            "exclude_revert_commits": True,
            "min_commit_message_words": 4,
            "max_commit_message_chars": 1000,
            "min_diff_lines": 1,
            "max_diff_lines": 1000,
            "max_files_changed": 30,
            "min_files_changed": 1,
            "min_content_score": 0.2,
            "min_alignment_score": 0.0,
            "require_verb_start": False,
            "exclude_wip_messages": False,
            "dedup_method": "exact",
            "dedup_threshold": 0.95,
            "min_pr_body_words": 5,
            "require_linked_issue": False,
            "min_issue_to_patch_words": 0,
        },
        "collection": {
            "max_commits_per_repo": 10000,
            "max_prs_per_repo": 2000,
            "since": None,
            "branches": [],
        },
        "output_format": "alpaca",
        "task": "all",
    },
}

class AppConfig(BaseModel):
    filter: FilterConfig = Field(default_factory=FilterConfig)
    collection: CollectionConfig = Field(default_factory=CollectionConfig)
    max_workers: int = 4
    output_format: str = "alpaca"
    task: str = "all"

    @classmethod
    def load_from_profile(cls, name: str) -> "AppConfig":
        if name not in DEFAULT_PROFILES:
            raise ValueError(f"Unknown config profile: {name}")
        return cls.model_validate(DEFAULT_PROFILES[name])

    @classmethod
    def load_from_yaml(cls, path: str) -> "AppConfig":
        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        return cls.model_validate(data)

    def dump_to_yaml(self, path: str):
        data = self.model_dump()
        if data.get("collection") and isinstance(data["collection"].get("since"), date):
            data["collection"]["since"] = data["collection"]["since"].isoformat()
        
        # Ensure directories exist
        dirname = os.path.dirname(path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
            
        with open(path, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

