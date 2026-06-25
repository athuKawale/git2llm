from concurrent.futures import ThreadPoolExecutor, as_completed
from git2llm.config import AppConfig
from git2llm.models import CommitRecord, PRRecord
from git2llm.collectors.commits import CommitCollector
from git2llm.collectors.pull_requests import PRCollector
from git2llm.collectors.issues import IssueCollector
from git2llm.filters import (
    check_hard_exclusions,
    check_structural_commit,
    check_structural_pr,
    check_content_quality,
    Deduplicator
)
from git2llm.formatters import (
    format_commit_to_alpaca,
    format_issue_pr_to_alpaca,
    format_pr_to_sharegpt,
    format_issue_pr_to_sharegpt
)
from git2llm.writer import DatasetWriter
from git2llm.utils.logging import logger
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

def format_commit_to_sharegpt(commit: CommitRecord, diff_text: str, score: float) -> dict:
    return {
        "conversations": [
            {
                "from": "system",
                "value": "You are an expert software engineer. Given a code diff, write a clear and informative commit message."
            },
            {
                "from": "human",
                "value": f"Write a commit message for this diff:\n\n```diff\n{diff_text}\n```"
            },
            {
                "from": "gpt",
                "value": commit.message_subject
            }
        ],
        "_meta": {
            "repo": commit.repo,
            "sha": commit.sha,
            "task": "commit_message",
            "score": score,
            "timestamp": commit.timestamp.isoformat()
        }
    }

def process_repo(
    repo_name: str,
    config: AppConfig,
    token: str,
    deduplicator: Deduplicator,
    writer: DatasetWriter,
    dry_run: bool = False,
    progress = None
):
    """Process a single repository: collect commits/PRs, filter them, format, and write."""
    writer.add_repo_processed(repo_name)
    
    repo_task_id = None
    if progress:
        total_steps = 0
        if config.task in {"all", "commit_message"}:
            total_steps += config.collection.max_commits_per_repo
        if config.task in {"all", "pr_review", "issue_to_patch"}:
            total_steps += config.collection.max_prs_per_repo
        repo_task_id = progress.add_task(
            f"[cyan][{repo_name}] Initializing...",
            total=total_steps if total_steps > 0 else None
        )

    # --- 1. Commits processing (Task: commit_message) ---
    if config.task in {"all", "commit_message"}:
        logger.info(f"[{repo_name}] Collecting commits...")
        commit_collector = CommitCollector(repo_name, config, token, progress, repo_task_id)
        commits = commit_collector.collect()
        writer.record_raw_counts(commits=len(commits))
        
        for commit in commits:
            # Stage 1: Hard Exclusions
            passed, reason = check_hard_exclusions(commit, config.filter)
            if not passed:
                if not dry_run:
                    writer.write_excluded(commit.model_dump(mode='json'), "stage1", reason)
                continue
                
            # Stage 2: Structural Checks
            passed, reason = check_structural_commit(commit, config.filter)
            if not passed:
                if not dry_run:
                    writer.write_excluded(commit.model_dump(mode='json'), "stage2", reason)
                continue
                
            # Stage 3: Content Quality Scoring
            passed, score, reason = check_content_quality(commit, config.filter)
            if not passed:
                if not dry_run:
                    writer.write_excluded(commit.model_dump(mode='json'), "stage3", reason)
                continue
                
            # Stage 4: Deduplication
            diff_text = ""
            for f in commit.files_changed:
                diff_text += f"diff --git a/{f.filename} b/{f.filename}\n{f.diff or ''}\n"
                
            is_dup = deduplicator.add_and_check(commit.sha, commit.message_subject, diff_text)
            if is_dup:
                if not dry_run:
                    writer.write_excluded(commit.model_dump(mode='json'), "stage4", "dedup:near_duplicate")
                continue
                
            # Format record
            if config.output_format == "alpaca":
                formatted = format_commit_to_alpaca(commit, score)
            else:
                formatted = format_commit_to_sharegpt(commit, diff_text, score)
                
            if not dry_run:
                writer.write_passed(formatted, task_type="commit_message")

    # --- 2. PRs processing (Tasks: pr_review, issue_to_patch) ---
    pr_tasks = {"all", "pr_review", "issue_to_patch"}
    if config.task in pr_tasks:
        logger.info(f"[{repo_name}] Collecting PRs...")
        pr_collector = PRCollector(repo_name, config, token, progress, repo_task_id)
        prs = pr_collector.collect()
        writer.record_raw_counts(prs=len(prs))
        
        issue_collector = IssueCollector(repo_name, config, token)
        
        for pr in prs:
            # Stage 2: Structural Checks (PR specific)
            passed, reason = check_structural_pr(pr, config.filter)
            if not passed:
                if not dry_run:
                    writer.write_excluded(pr.model_dump(mode='json'), "stage2", reason)
                continue
                
            # Stage 4: Deduplication based on PR diff
            is_dup = deduplicator.add_and_check(f"pr_{pr.number}", pr.title, pr.diff)
            if is_dup:
                if not dry_run:
                    writer.write_excluded(pr.model_dump(mode='json'), "stage4", "dedup:near_duplicate_pr")
                continue
                
            # Task: pr_review
            if config.task in {"all", "pr_review"}:
                # Format to ShareGPT by default, or Alpaca if configured
                # ShareGPT fits code review dialogue best
                if config.output_format == "sharegpt":
                    formatted_review = format_pr_to_sharegpt(pr)
                else:
                    # Fallback to Alpaca-like shape for reviews
                    formatted_review = {
                        "instruction": "Review this pull request diff and provide comments.",
                        "input": pr.diff,
                        "output": "\n".join(f"[{c.path}] {c.body}" for c in pr.review_comments),
                        "_meta": {"repo": pr.repo, "pr_number": pr.number, "task": "pr_review", "timestamp": pr.merged_at.isoformat() if pr.merged_at else ""}
                    }
                if not dry_run:
                    writer.write_passed(formatted_review, task_type="pr_review")
                    
            # Task: issue_to_patch
            if config.task in {"all", "issue_to_patch"}:
                # Filter out PRs without linked issues if required
                if config.filter.require_linked_issue and not pr.linked_issue_numbers:
                    if not dry_run:
                        writer.write_excluded(pr.model_dump(mode='json'), "stage1", "pr_exclusion:no_linked_issue")
                    continue
                    
                # Fetch issue bodies for linked issues
                linked_bodies = []
                for num in pr.linked_issue_numbers:
                    body = issue_collector.get_issue_body(num)
                    if body:
                        linked_bodies.append(f"Issue #{num}:\n{body}")
                pr.linked_issue_bodies = linked_bodies
                
                if config.output_format == "sharegpt":
                    formatted_patch = format_issue_pr_to_sharegpt(pr)
                    input_text = formatted_patch["conversations"][1]["value"]
                else:
                    formatted_patch = format_issue_pr_to_alpaca(pr)
                    input_text = formatted_patch["input"]
                
                # Check combined input word count threshold
                input_words = len(input_text.strip().split())
                min_patch_words = getattr(config.filter, "min_issue_to_patch_words", 20)
                if input_words < min_patch_words:
                    if not dry_run:
                        writer.write_excluded(pr.model_dump(mode='json'), "stage3", "content_quality:insufficient_context")
                    continue
                    
                if not dry_run:
                    writer.write_passed(formatted_patch, task_type="issue_to_patch")

    if progress and repo_task_id:
        progress.remove_task(repo_task_id)

def run_pipeline(
    repos: list[str],
    config: AppConfig,
    token: str,
    writer: DatasetWriter,
    dry_run: bool = False
):
    """Run parallel processing across multiple repositories."""
    deduplicator = Deduplicator(
        threshold=config.filter.dedup_threshold,
        method=config.filter.dedup_method
    )
    
    max_workers = min(config.max_workers, len(repos)) if len(repos) > 0 else 1
    
    logger.info(f"Starting pipeline for {len(repos)} repos using {max_workers} worker threads...")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        transient=True
    ) as progress:
        task_id = progress.add_task("[cyan]Processing repositories...", total=len(repos))
        
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(process_repo, repo, config, token, deduplicator, writer, dry_run, progress): repo
                for repo in repos
            }
            
            for future in as_completed(futures):
                repo = futures[future]
                try:
                    future.result()
                    logger.info(f"Finished processing repository: {repo}")
                except Exception as e:
                    logger.error(f"Error processing repository {repo}: {e}", exc_info=True)
                finally:
                    progress.update(task_id, advance=1)
