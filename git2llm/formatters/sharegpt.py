from typing import Dict, Any
from git2llm.models import PRRecord
from git2llm.formatters.templates import PR_REVIEW_INSTRUCTION

def format_pr_to_sharegpt(pr: PRRecord, score: float = 1.0) -> Dict[str, Any]:
    """Format a PR record to ShareGPT schema with _meta."""
    comments_markdown = []
    for comment in pr.review_comments:
        comments_markdown.append(
            f"### Review Comment on `{comment.path}`:\n"
            f"**Context:**\n"
            f"```diff\n{comment.diff_hunk}\n```\n"
            f"**Feedback:** {comment.body}"
        )
    
    gpt_response = "\n\n".join(comments_markdown) if comments_markdown else "No specific comments."
    human_value = f"PR #{pr.number}: {pr.title}\n\n**Description:** {pr.body or 'No description provided.'}\n\n```diff\n{pr.diff}\n```"
    
    return {
        "conversations": [
            {
                "from": "system",
                "value": PR_REVIEW_INSTRUCTION
            },
            {
                "from": "human",
                "value": human_value
            },
            {
                "from": "gpt",
                "value": gpt_response
            }
        ],
        "_meta": {
            "repo": pr.repo,
            "pr_number": pr.number,
            "task": "pr_review",
            "score": score,
            "timestamp": pr.merged_at.isoformat() if pr.merged_at else ""
        }
    }

from git2llm.formatters.templates import ISSUE_TO_PATCH_INSTRUCTION
from git2llm.formatters.alpaca import strip_html_comments

def format_issue_pr_to_sharegpt(pr: PRRecord, score: float = 1.0) -> Dict[str, Any]:
    """Format linked Issue + PR to ShareGPT schema (issue_to_patch task) with _meta."""
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
        "conversations": [
            {
                "from": "system",
                "value": ISSUE_TO_PATCH_INSTRUCTION
            },
            {
                "from": "human",
                "value": issues_text
            },
            {
                "from": "gpt",
                "value": pr.diff
            }
        ],
        "_meta": {
            "repo": pr.repo,
            "pr_number": pr.number,
            "task": "issue_to_patch",
            "score": score,
            "timestamp": pr.merged_at.isoformat() if pr.merged_at else ""
        }
    }

