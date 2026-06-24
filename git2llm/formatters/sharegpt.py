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
