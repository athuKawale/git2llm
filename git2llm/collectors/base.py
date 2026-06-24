from git2llm.config import AppConfig

class BaseCollector:
    def __init__(self, repo_name: str, config: AppConfig):
        self.repo_name = repo_name  # e.g., "owner/name"
        self.config = config

    def collect(self) -> list:
        raise NotImplementedError
