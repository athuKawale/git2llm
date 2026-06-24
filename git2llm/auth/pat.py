import os
from github import Github
from github.GithubException import BadCredentialsException, GithubException
from git2llm.utils.logging import logger
from git2llm.auth.token_store import load_token, save_token

class AuthProvider:
    def get_token(self) -> str:
        raise NotImplementedError
        
    def get_github_client(self) -> Github:
        raise NotImplementedError

class PATAuth(AuthProvider):
    def __init__(self, token: str = None):
        self.token = token or os.environ.get("GIT2LLM_TOKEN") or os.environ.get("GITHUB_TOKEN") or load_token()
        
    def get_token(self) -> str:
        if not self.token:
            # Fall back to console input
            self.token = input("Enter GitHub Personal Access Token (PAT): ").strip()
            if self.token:
                # Save token locally for subsequent commands
                save_token(self.token)
        return self.token
        
    def get_github_client(self) -> Github:
        token = self.get_token()
        if not token:
            raise ValueError("No GitHub token provided.")
        g = Github(token)
        # Validate token
        try:
            user = g.get_user()
            logger.debug(f"Authenticated as: {user.login}")
            # Try to read scopes if available in headers
            scopes = user.raw_headers.get("x-oauth-scopes", "")
            logger.debug(f"Token scopes: {scopes}")
        except BadCredentialsException:
            raise ValueError("Invalid GitHub Personal Access Token.")
        except GithubException as e:
            raise ValueError(f"GitHub API error during auth: {e}")
        return g
