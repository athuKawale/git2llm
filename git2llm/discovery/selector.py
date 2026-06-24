from typing import List
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from git2llm.discovery.repo_lister import RepoMeta

def select_repos(repos: List[RepoMeta]) -> List[str]:
    """Present interactive multi-select UI to pick repositories."""
    if not repos:
        return []
        
    choices = []
    for r in repos:
        # Build a nice descriptive label
        name_part = f"{r.full_name:<40}"
        lang_part = f"[{r.language}]"
        star_part = f"★{r.stars}"
        updated_part = f"updated {r.updated_at}"
        label = f"{name_part} {lang_part:<15} {star_part:<8} {updated_part}"
        
        choices.append(Choice(value=r.full_name, name=label))
        
    result = inquirer.checkbox(
        message="Select repositories to mine (space=select, enter=confirm):",
        choices=choices,
        vi_mode=False
    ).execute()
    
    return result
