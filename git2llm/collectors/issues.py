from typing import Dict, Optional
from github import Github
from git2llm.collectors.base import BaseCollector
from git2llm.utils.logging import logger

class IssueCollector(BaseCollector):
    def __init__(self, repo_name: str, config, token: str):
        super().__init__(repo_name, config)
        self.token = token
        self._cache: Dict[int, str] = {}

    def get_issue_body(self, issue_number: int) -> str:
        """Fetch the body of a specific issue (with local caching)."""
        if issue_number in self._cache:
            return self._cache[issue_number]
            
        g = Github(self.token)
        try:
            repo = g.get_repo(self.repo_name)
            issue = repo.get_issue(issue_number)
            body = issue.body or ""
            self._cache[issue_number] = body
            return body
        except Exception as e:
            logger.warning(f"Failed to fetch issue #{issue_number} in {self.repo_name}: {e}")
            self._cache[issue_number] = ""
            return ""
            
    def collect(self):
        # General issues collection if needed
        return []
