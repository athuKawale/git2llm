import re
import requests
from typing import List, Optional
from github import Github
from github.GithubException import GithubException
from git2llm.collectors.base import BaseCollector
from git2llm.models import PRRecord, ReviewComment
from git2llm.utils.logging import logger
from git2llm.utils.rate_limiter import RateLimiter

CLOSES_PATTERN = re.compile(
    r'(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)',
    re.IGNORECASE
)

class PRCollector(BaseCollector):
    def __init__(self, repo_name: str, config, token: str):
        super().__init__(repo_name, config)
        self.token = token

    def _fetch_diff(self, pr_number: int) -> str:
        """Fetch unified diff for a PR using Accept header."""
        url = f"https://api.github.com/repos/{self.repo_name}/pulls/{pr_number}"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.diff"
        }
        try:
            res = requests.get(url, headers=headers)
            if res.status_code == 200:
                return res.text
            else:
                logger.error(f"Failed to fetch diff for PR #{pr_number}. Status: {res.status_code}")
        except Exception as e:
            logger.error(f"Error fetching PR diff: {e}")
        return ""

    def collect(self) -> List[PRRecord]:
        g = Github(self.token)
        try:
            repo = g.get_repo(self.repo_name)
        except Exception as e:
            logger.error(f"Failed to get repo {self.repo_name} for PR collection: {e}")
            return []

        logger.info(f"Collecting pull requests for {self.repo_name}...")
        
        limiter = RateLimiter(g)
        
        # Get closed pulls
        pulls = repo.get_pulls(state="closed", sort="updated", direction="desc")
        records = []
        max_prs = self.config.collection.max_prs_per_repo

        for pr in pulls:
            limiter.check_and_wait()
            if len(records) >= max_prs:
                break
                
            # Filter only merged PRs
            if not pr.merged:
                continue

            # Apply since date filter if configured
            if self.config.collection.since:
                since_dt = self.config.collection.since
                if pr.merged_at and pr.merged_at.date() < since_dt:
                    # Since we sort by updated desc, older PRs will follow.
                    # Wait, sorting by updated desc means we can't completely break, but we can skip.
                    continue

            # Parse linked issues from body
            body_text = pr.body or ""
            linked_issues = [int(num) for num in CLOSES_PATTERN.findall(body_text)]

            # Fetch review comments
            review_comments = []
            try:
                comments = pr.get_review_comments()
                for c in comments:
                    review_comments.append(ReviewComment(
                        path=c.path,
                        diff_hunk=c.diff_hunk,
                        body=c.body,
                        author=c.user.login if c.user else "unknown"
                    ))
            except GithubException as e:
                logger.warning(f"Failed to get review comments for PR #{pr.number}: {e}")

            # Fetch unified diff
            diff_text = self._fetch_diff(pr.number)

            records.append(PRRecord(
                number=pr.number,
                repo=self.repo_name,
                title=pr.title,
                body=body_text,
                diff=diff_text,
                review_comments=review_comments,
                linked_issue_numbers=linked_issues,
                labels=[label.name for label in pr.labels],
                merged_at=pr.merged_at
            ))

        logger.info(f"Collected {len(records)} merged PRs for {self.repo_name}")
        return records
