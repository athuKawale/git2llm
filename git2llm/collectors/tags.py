import re
from typing import List, Dict, Any
from github import Github
from git2llm.collectors.base import BaseCollector
from git2llm.utils.logging import logger

SEMVER_PATTERN = re.compile(
    r'^v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)'
    r'(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?'
    r'(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$'
)

class TagCollector(BaseCollector):
    def __init__(self, repo_name: str, config, token: str):
        super().__init__(repo_name, config)
        self.token = token

    def collect(self) -> List[Dict[str, Any]]:
        """Collect tags and associated release notes from GitHub."""
        g = Github(self.token)
        try:
            repo = g.get_repo(self.repo_name)
        except Exception as e:
            logger.error(f"Failed to get repo {self.repo_name} for tag collection: {e}")
            return []

        logger.info(f"Collecting tags/releases for {self.repo_name}...")
        records = []
        
        try:
            # Fetch releases (releases contain the markdown notes)
            releases = repo.get_releases()
            for rel in releases:
                tag_name = rel.tag_name
                # Check if matches semantic versioning
                is_semver = bool(SEMVER_PATTERN.match(tag_name))
                
                records.append({
                    "tag_name": tag_name,
                    "repo": self.repo_name,
                    "title": rel.title or "",
                    "body": rel.body or "",
                    "is_semver": is_semver,
                    "published_at": rel.published_at.isoformat() if rel.published_at else ""
                })
        except Exception as e:
            logger.error(f"Error fetching releases for {self.repo_name}: {e}")

        logger.info(f"Collected {len(records)} releases for {self.repo_name}")
        return records
