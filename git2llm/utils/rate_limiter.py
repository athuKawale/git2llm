import time
from datetime import datetime, timezone
from github import Github
from git2llm.utils.logging import logger

class RateLimiter:
    def __init__(self, github_client: Github):
        self.g = github_client
    
    def check_and_wait(self):
        """Check current core rate limit and sleep if it is low."""
        try:
            rate_limit = self.g.get_rate_limit()
            core = rate_limit.rate
            
            if core.remaining < 100:
                reset_time = core.reset
                if reset_time.tzinfo is None:
                    reset_time = reset_time.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                wait_seconds = max((reset_time - now).total_seconds() + 5, 0)
                
                logger.warning(
                    f"GitHub API Rate Limit low ({core.remaining}/{core.limit}). "
                    f"Sleeping for {int(wait_seconds)} seconds until reset..."
                )
                time.sleep(wait_seconds)
            else:
                logger.debug(f"GitHub API Rate Limit: {core.remaining}/{core.limit}")
        except Exception as e:
            logger.warning(f"Failed to check GitHub rate limit: {e}")
