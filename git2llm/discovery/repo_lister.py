from typing import List, Dict, Any
from github import Github
from pydantic import BaseModel

class RepoMeta(BaseModel):
    full_name: str
    visibility: str  # "public" or "private"
    language: str
    stars: int
    updated_at: str

def list_accessible_repos(g: Github) -> List[RepoMeta]:
    """List all accessible repositories for the authenticated user."""
    repos = []
    seen = set()
    
    # We fetch all repositories the user has access to (personal, org, collab)
    for r in g.get_user().get_repos():
        if r.full_name in seen:
            continue
        seen.add(r.full_name)
        
        repos.append(RepoMeta(
            full_name=r.full_name,
            visibility="private" if r.private else "public",
            language=r.language or "Unknown",
            stars=r.stargazers_count or 0,
            updated_at=r.updated_at.strftime("%Y-%m-%d") if r.updated_at else "Unknown"
        ))
        
    return repos
