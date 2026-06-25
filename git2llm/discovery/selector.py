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

def select_branches(branch_names: List[str]) -> List[str]:
    """Present interactive multi-select UI to pick branches."""
    if not branch_names:
        return []
        
    choices = [Choice(value="ALL", name="All branches (mine everything)")]
    for b in sorted(branch_names):
        choices.append(Choice(value=b, name=b))
        
    result = inquirer.checkbox(
        message="Select branches to mine (space=select, enter=confirm):",
        choices=choices,
        vi_mode=False
    ).execute()
    
    if "ALL" in result or not result:
        return []
    return result

def select_task() -> str:
    """Present interactive single-select UI to pick a dataset task."""
    choices = [
        Choice(value="commit_message", name="commit_message: Mine diffs to generate conventional commit messages"),
        Choice(value="pr_review", name="pr_review: Mine PRs & review comments to generate code reviews"),
        Choice(value="issue_to_patch", name="issue_to_patch: Mine linked issues & PR descriptions to generate patches/diffs"),
        Choice(value="all", name="all: Generate all supported task datasets"),
    ]
    result = inquirer.select(
        message="Select dataset generation task:",
        choices=choices,
        vi_mode=False
    ).execute()
    return result

