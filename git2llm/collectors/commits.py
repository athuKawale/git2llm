import os
import subprocess
from datetime import datetime
from typing import List, Optional
from pydriller import Repository, ModificationType
from git2llm.collectors.base import BaseCollector
from git2llm.models import CommitRecord, FileChange
from git2llm.utils.git_utils import clone_repo
from git2llm.utils.logging import logger

class CommitCollector(BaseCollector):
    def __init__(self, repo_name: str, config, token: Optional[str] = None):
        super().__init__(repo_name, config)
        self.token = token

    def _detect_language(self, filename: str) -> Optional[str]:
        ext = os.path.splitext(filename)[1].lower()
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".go": "go",
            ".java": "java",
            ".rb": "ruby",
            ".rs": "rust",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c-header",
            ".cs": "csharp",
            ".md": "markdown",
            ".html": "html",
            ".css": "css",
            ".sh": "shell",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".json": "json"
        }
        return ext_map.get(ext)

    def collect(self) -> List[CommitRecord]:
        try:
            local_path = clone_repo(self.repo_name, self.token)
        except Exception as e:
            logger.error(f"Cannot clone repository {self.repo_name}: {e}")
            return []

        logger.info(f"Mining commits from local path {local_path}...")
        
        base_kwargs = {}
        if self.config.collection.since:
            base_kwargs["since"] = datetime.combine(self.config.collection.since, datetime.min.time())

        branches = self.config.collection.branches or []
        records = []
        seen_shas = set()
        max_commits = self.config.collection.max_commits_per_repo

        def process_commit(commit):
            if commit.hash in seen_shas:
                return
            seen_shas.add(commit.hash)
            
            # Split message into subject and body
            msg_parts = commit.msg.split("\n", 1)
            subject = msg_parts[0]
            body = msg_parts[1] if len(msg_parts) > 1 else ""

            files_changed = []
            for mod in commit.modified_files:
                change_type = "MODIFY"
                if mod.change_type == ModificationType.ADD:
                    change_type = "ADD"
                elif mod.change_type == ModificationType.DELETE:
                    change_type = "DELETE"
                elif mod.change_type == ModificationType.RENAME:
                    change_type = "RENAME"

                filename = mod.new_path or mod.old_path or ""
                diff_content = mod.diff or ""
                files_changed.append(FileChange(
                    filename=filename,
                    change_type=change_type,
                    diff=diff_content,
                    additions=mod.added_lines,
                    deletions=mod.deleted_lines,
                    language=self._detect_language(filename)
                ))

            records.append(CommitRecord(
                sha=commit.hash,
                repo=self.repo_name,
                message_subject=subject,
                message_body=body,
                author=commit.author.name or "",
                author_email=commit.author.email or "",
                timestamp=commit.author_date,
                files_changed=files_changed,
                total_additions=commit.insertions,
                total_deletions=commit.deletions,
                is_merge=commit.merge,
                parent_shas=commit.parents
            ))

        try:
            if not branches:
                # Traverse all branches using include_remotes=True
                kwargs = {**base_kwargs, "include_remotes": True, "order": "reverse"}
                repo_miner = Repository(local_path, **kwargs)
                for commit in repo_miner.traverse_commits():
                    if len(records) >= max_commits:
                        logger.info(f"Reached commit limit of {max_commits} for {self.repo_name}")
                        break
                    process_commit(commit)
            else:
                # Traverse specific branches
                for branch in branches:
                    if len(records) >= max_commits:
                        break
                    
                    # Create local tracking branch if it exists as remote
                    subprocess.run(
                        ["git", "checkout", "-B", branch, f"origin/{branch}"],
                        cwd=local_path,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    
                    kwargs = {**base_kwargs, "only_in_branch": branch, "order": "reverse"}
                    try:
                        repo_miner = Repository(local_path, **kwargs)
                        for commit in repo_miner.traverse_commits():
                            if len(records) >= max_commits:
                                logger.info(f"Reached commit limit of {max_commits} for {self.repo_name}")
                                break
                            process_commit(commit)
                    except Exception as branch_err:
                        logger.warning(f"Branch {branch} not found or error mining in {self.repo_name}: {branch_err}")
        except Exception as e:
            logger.error(f"Error traversing commits for {self.repo_name}: {e}")
            
        logger.info(f"Collected {len(records)} raw commits from {self.repo_name}")
        return records
