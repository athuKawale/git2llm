from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Set
from github import Github
from github.GithubException import GithubException, UnknownObjectException
from git2llm.collectors.base import BaseCollector
from git2llm.utils.logging import logger


class IssueCollector(BaseCollector):
    def __init__(self, repo_name: str, config, token: str, max_workers: int = 8):
        super().__init__(repo_name, config)
        self.token = token
        self.max_workers = max_workers
        self._cache: Dict[int, str] = {}
        self._repo = None
        self._max_issue_number: Optional[int] = None  # lazy-loaded

    def _get_repo(self):
        """Lazy-init the GitHub repo object and reuse across calls."""
        if self._repo is None:
            g = Github(self.token, per_page=100)
            self._repo = g.get_repo(self.repo_name)
        return self._repo

    def _get_max_issue_number(self) -> int:
        """
        Get the repo's actual GitHub issue count to filter out external tracker IDs.
        Django PRs reference Trac IDs like #142145 which don't exist on GitHub.
        """
        if self._max_issue_number is None:
            try:
                repo = self._get_repo()
                # open_issues_count includes both issues and PRs, but gives a good ceiling
                # Add a 50% buffer to account for closed issues not counted
                self._max_issue_number = max(repo.open_issues_count * 3, 5000)
            except Exception:
                self._max_issue_number = 100_000  # fallback: allow all
        return self._max_issue_number

    def _fetch_single(self, issue_number: int) -> str:
        """Fetch one issue body. Returns '' on any error."""
        try:
            repo = self._get_repo()
            issue = repo.get_issue(issue_number)
            return issue.body or ""
        except UnknownObjectException:
            # 404 — issue doesn't exist (external tracker reference, e.g. Trac ID)
            logger.debug(f"Issue #{issue_number} not found in {self.repo_name} (likely external tracker reference)")
            return ""
        except GithubException as e:
            if e.status == 404:
                logger.debug(f"Issue #{issue_number} not found in {self.repo_name}: {e.data.get('message', '')}")
            else:
                logger.warning(f"Failed to fetch issue #{issue_number} in {self.repo_name}: {e}")
            return ""
        except Exception as e:
            logger.warning(f"Failed to fetch issue #{issue_number} in {self.repo_name}: {e}")
            return ""

    def get_issue_body(self, issue_number: int) -> str:
        """Fetch a single issue body (with caching). Use prefetch_issues() for bulk."""
        if issue_number in self._cache:
            return self._cache[issue_number]

        # Skip obviously-external tracker IDs before making an API call
        if issue_number > self._get_max_issue_number():
            logger.debug(
                f"Skipping issue #{issue_number} in {self.repo_name}: "
                f"number exceeds repo's issue range (likely a Trac/Jira/Bugzilla ID)"
            )
            self._cache[issue_number] = ""
            return ""

        body = self._fetch_single(issue_number)
        self._cache[issue_number] = body
        return body

    def prefetch_issues(self, issue_numbers: List[int]) -> None:
        """
        Batch-fetch multiple issue bodies in parallel and populate the cache.
        Call this before iterating over PRs to amortize network latency.
        """
        # Filter out already-cached and obviously-out-of-range numbers
        max_num = self._get_max_issue_number()
        to_fetch: List[int] = []
        for num in set(issue_numbers):
            if num in self._cache:
                continue
            if num > max_num:
                logger.debug(
                    f"Skipping issue #{num} in {self.repo_name}: "
                    f"exceeds repo issue range (likely external tracker ID)"
                )
                self._cache[num] = ""
                continue
            to_fetch.append(num)

        if not to_fetch:
            return

        workers = min(self.max_workers, len(to_fetch))
        logger.debug(f"Prefetching {len(to_fetch)} issues for {self.repo_name} with {workers} workers...")

        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_to_num = {pool.submit(self._fetch_single, num): num for num in to_fetch}
            for future in as_completed(future_to_num):
                num = future_to_num[future]
                try:
                    self._cache[num] = future.result()
                except Exception as e:
                    logger.warning(f"Unexpected error prefetching issue #{num}: {e}")
                    self._cache[num] = ""

    def collect(self):
        # General issues collection — not used directly in pipeline
        return []
