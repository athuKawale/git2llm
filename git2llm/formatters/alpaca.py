from typing import Dict, Any
from git2llm.models import CommitRecord, PRRecord
from git2llm.formatters.templates import COMMIT_TO_MESSAGE_INSTRUCTION, ISSUE_TO_PATCH_INSTRUCTION

def format_commit_diff(commit: CommitRecord) -> str:
    diff_parts = []
    for f in commit.files_changed:
        diff_parts.append(f"diff --git a/{f.filename} b/{f.filename}\n{f.diff or ''}")
    return "\n".join(diff_parts)

def format_commit_to_alpaca(commit: CommitRecord, score: float = 1.0) -> Dict[str, Any]:
    """Format a commit record to Alpaca schema with _meta."""
    diff_text = format_commit_diff(commit)
    # Output is the commit message subject (or full message if needed)
    # The specification says: output: commit message subject
    output_text = commit.message_subject
    
    return {
        "instruction": COMMIT_TO_MESSAGE_INSTRUCTION,
        "input": diff_text,
        "output": output_text,
        "_meta": {
            "repo": commit.repo,
            "sha": commit.sha,
            "task": "commit_message",
            "score": score,
            "timestamp": commit.timestamp.isoformat()
        }
    }

import re

def strip_html_comments(text: str) -> str:
    """Remove HTML comments from a string."""
    if not text:
        return ""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()

def format_issue_pr_to_alpaca(pr: PRRecord, score: float = 1.0) -> Dict[str, Any]:
    """Format linked Issue + PR to Alpaca schema (issue_to_patch task) with _meta."""
    parts = []
    
    # 1. Add linked issue bodies (stripped of HTML comments)
    if pr.linked_issue_bodies:
        for body in pr.linked_issue_bodies:
            cleaned_body = strip_html_comments(body)
            if cleaned_body:
                parts.append(cleaned_body)
                
    # 2. Add PR description (stripped of HTML comments)
    if pr.body:
        cleaned_pr_body = strip_html_comments(pr.body)
        if cleaned_pr_body:
            parts.append(f"PR Description:\n{cleaned_pr_body}")
            
    # 3. Combine parts, fallback to title if empty
    if parts:
        issues_text = "\n\n".join(parts)
    else:
        issues_text = pr.title
        
    return {
        "instruction": ISSUE_TO_PATCH_INSTRUCTION,
        "input": issues_text,
        "output": pr.diff,
        "_meta": {
            "repo": pr.repo,
            "pr_number": pr.number,
            "task": "issue_to_patch",
            "score": score,
            "timestamp": pr.merged_at.isoformat()
        }
    }
