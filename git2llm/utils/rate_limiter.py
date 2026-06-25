import time
from datetime import datetime, timezone
from github import Github
from git2llm.utils.logging import logger

class RateLimiter:
    def __init__(self, github_client: Github, check_interval: int = 50):
        self.g = github_client
        self.check_interval = check_interval  # Only check rate limit every N calls
        self._call_count = 0
        self._remaining: int = 5000  # Assume full budget at start
    
    def check_and_wait(self):
        """Check rate limit periodically and sleep only if critically low."""
        self._call_count += 1

        # Only poll GitHub for rate limit every `check_interval` calls
        if self._call_count % self.check_interval == 0:
            try:
                rate_limit = self.g.get_rate_limit()
                core = rate_limit.rate
                self._remaining = core.remaining

                if core.remaining < 50:
                    reset_time = core.reset
                    if reset_time.tzinfo is None:
                        reset_time = reset_time.replace(tzinfo=timezone.utc)
                    now = datetime.now(timezone.utc)
                    wait_seconds = max((reset_time - now).total_seconds() + 5, 0)

                    logger.warning(
                        f"GitHub API Rate Limit critically low ({core.remaining}/{core.limit}). "
                        f"Sleeping for {int(wait_seconds)}s until reset..."
                    )
                    time.sleep(wait_seconds)
                else:
                    logger.debug(f"GitHub API Rate Limit: {core.remaining}/{core.limit}")
            except Exception as e:
                logger.warning(f"Failed to check GitHub rate limit: {e}")
