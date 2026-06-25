import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from github import Github
from github.GithubException import GithubException
from git2llm.collectors.base import BaseCollector
from git2llm.models import PRRecord, ReviewComment
from git2llm.utils.logging import logger
from git2llm.utils.rate_limiter import RateLimiter

CLOSES_PATTERN = re.compile(
    r'(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\\s+#(\\d+)',
    re.IGNORECASE
)

class PRCollector(BaseCollector):
    def __init__(self, repo_name: str, config, token: str, progress=None, task_id=None):
        super().__init__(repo_name, config)
        self.token = token
        self.progress = progress
        self.task_id = task_id

    def _fetch_diff(self, pr_number: int) -> str:
        """Fetch unified diff for a PR using Accept header."""
        url = f"https://api.github.com/repos/{self.repo_name}/pulls/{pr_number}"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.diff"
        }
        try:
            res = requests.get(url, headers=headers, timeout=15)
            if res.status_code == 200:
                return res.text
            else:
                logger.debug(f"Failed to fetch diff for PR #{pr_number}. Status: {res.status_code}")
        except Exception as e:
            logger.debug(f"Error fetching PR diff: {e}")
        return ""

    def _fetch_pr_details(self, pr) -> Optional[PRRecord]:
        """Fetch diff + review comments for a single PR. Designed to run in a thread pool."""
        body_text = pr.body or ""
        issue_mentions = re.findall(r'#(\d+)', body_text)
        url_mentions = re.findall(r'(?:issues|pulls)/(\d+)', body_text)

        all_numbers = set()
        for num in issue_mentions + url_mentions:
            val = int(num)
            if val != pr.number:
                all_numbers.add(val)
        linked_issues = sorted(list(all_numbers))

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
            logger.debug(f"Failed to get review comments for PR #{pr.number}: {e}")

        # Fetch unified diff
        diff_text = self._fetch_diff(pr.number)

        return PRRecord(
            number=pr.number,
            repo=self.repo_name,
            title=pr.title,
            body=body_text,
            diff=diff_text,
            review_comments=review_comments,
            linked_issue_numbers=linked_issues,
            labels=[label.name for label in pr.labels],
            merged_at=pr.merged_at
        )

    def collect(self) -> List[PRRecord]:
        # Use per_page=100 at client level to minimize API round-trips (default is 30)
        g = Github(self.token, per_page=100)
        try:
            repo = g.get_repo(self.repo_name)
        except Exception as e:
            logger.error(f"Failed to get repo {self.repo_name} for PR collection: {e}")
            return []

        max_prs = self.config.collection.max_prs_per_repo
        # Cap how many closed PRs we scan to avoid spending forever on repos
        # where many PRs were closed-without-merge (e.g. golang/go mirrors issues as PRs).
        # Scan at most 5x the target to find enough merged ones.
        max_scan = max_prs * 5

        if self.progress and self.task_id:
            self.progress.update(
                self.task_id,
                description=f"[cyan][{self.repo_name}] Scanning PRs (found 0/{max_prs})..."
            )

        limiter = RateLimiter(g, check_interval=50)

        pulls = repo.get_pulls(state="closed", sort="updated", direction="desc")

        candidates = []
        scanned = 0
        for pr in pulls:
            # NOTE: Do NOT call limiter.check_and_wait() here in the scan loop —
            # just iterating the PaginatedList already uses API calls, and calling
            # check_and_wait() additionally slows down the scan significantly.
            scanned += 1

            if len(candidates) >= max_prs or scanned > max_scan:
                break

            # Use merged_at instead of pr.merged — pr.merged triggers a full per-PR
            # API fetch, while merged_at is included in the list response for free.
            if pr.merged_at is None:
                # Update description every 25 scanned so user sees progress
                if self.progress and self.task_id and scanned % 25 == 0:
                    self.progress.update(
                        self.task_id,
                        description=f"[cyan][{self.repo_name}] Scanning PRs (found {len(candidates)}/{max_prs}, scanned {scanned})..."
                    )
                continue

            if self.config.collection.since:
                since_dt = self.config.collection.since
                if pr.merged_at.date() < since_dt:
                    continue

            candidates.append(pr)
            if self.progress and self.task_id:
                self.progress.update(
                    self.task_id,
                    description=f"[cyan][{self.repo_name}] Scanning PRs (found {len(candidates)}/{max_prs}, scanned {scanned})..."
                )

        if self.progress and self.task_id:
            self.progress.update(
                self.task_id,
                description=f"[cyan][{self.repo_name}] Fetching PR details (0/{len(candidates)})..."
            )

        # Fetch PR details in parallel (diff + review comments are I/O bound)
        records = []
        fetch_workers = min(8, len(candidates)) if candidates else 1

        with ThreadPoolExecutor(max_workers=fetch_workers) as pool:
            future_to_pr = {pool.submit(self._fetch_pr_details, pr): pr for pr in candidates}
            for future in as_completed(future_to_pr):
                try:
                    record = future.result()
                    if record:
                        records.append(record)
                except Exception as e:
                    pr = future_to_pr[future]
                    logger.debug(f"Error fetching details for PR #{pr.number}: {e}")

                if self.progress and self.task_id:
                    self.progress.update(
                        self.task_id,
                        description=f"[cyan][{self.repo_name}] Fetching PR details ({len(records)}/{len(candidates)})...",
                        advance=1
                    )

        if self.progress and self.task_id:
            remaining = max_prs - len(records)
            if remaining > 0:
                self.progress.advance(self.task_id, remaining)
            self.progress.update(self.task_id, description=f"[cyan][{self.repo_name}] PRs collected.")

        logger.info(f"Collected {len(records)} merged PRs from {scanned} scanned for {self.repo_name}")
        return records
