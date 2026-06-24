from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class FileChange(BaseModel):
    filename: str
    change_type: str          # "ADD", "MODIFY", "DELETE", "RENAME"
    diff: str                 # unified diff for this file
    additions: int
    deletions: int
    language: Optional[str] = None  # detected by file extension

class CommitRecord(BaseModel):
    sha: str
    repo: str
    message_subject: str      # first line only
    message_body: str         # rest of the message
    author: str
    author_email: Optional[str] = None
    timestamp: datetime
    files_changed: List[FileChange]
    total_additions: int
    total_deletions: int
    is_merge: bool
    parent_shas: List[str]

class ReviewComment(BaseModel):
    path: str
    diff_hunk: str
    body: str
    author: str

class PRRecord(BaseModel):
    number: int
    repo: str
    title: str
    body: str
    diff: str                 # full unified diff
    review_comments: List[ReviewComment] = []
    linked_issue_numbers: List[int] = []
    linked_issue_bodies: List[str] = []   # fetched separately
    labels: List[str] = []
    merged_at: datetime

class FilterResult(BaseModel):
    record_id: str
    passed: bool
    stage_failed: Optional[str] = None    # e.g. "hard_exclusion:is_merge"
    score: Optional[float] = None

class OutputRecord(BaseModel):
    """Final record before formatting"""
    source_type: str          # "commit", "pr", "issue_pr_pair"
    task_type: str            # "commit_message", "issue_to_patch", etc.
    repo: str
    sha_or_pr: str
    instruction: str
    context: str              # the "input" field
    response: str             # the "output" field
    metadata: Dict[str, Any]  # repo, sha, date, etc. — not in training data
