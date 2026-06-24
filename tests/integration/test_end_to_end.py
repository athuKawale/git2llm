import os
import json
import shutil
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, date, timezone
from git2llm.config import AppConfig
from git2llm.writer import DatasetWriter
from git2llm.orchestrator import run_pipeline

@pytest.fixture
def temp_output_dir():
    path = "./test_git2llm_output"
    if os.path.exists(path):
        shutil.rmtree(path)
    yield path
    if os.path.exists(path):
        shutil.rmtree(path)

@patch("git2llm.collectors.commits.clone_repo")
@patch("git2llm.collectors.commits.Repository")
@patch("git2llm.collectors.pull_requests.Github")
@patch("git2llm.collectors.issues.Github")
def test_end_to_end_pipeline(
    mock_issues_github,
    mock_pr_github,
    mock_pydriller_repo,
    mock_clone_repo,
    temp_output_dir
):
    # 1. Setup mock path
    mock_clone_repo.return_value = "/fake/repo/path"
    
    # 2. Setup mock PyDriller commit
    mock_commit = MagicMock()
    mock_commit.hash = "deadbeef"
    mock_commit.msg = "Fix: resolve array index boundary check\n\nDetailed explanation here."
    mock_commit.author.name = "Test User"
    mock_commit.author.email = "test@user.com"
    mock_commit.author_date = datetime.now(timezone.utc)
    mock_commit.merge = False
    mock_commit.parents = ["parentsha"]
    mock_commit.insertions = 1
    mock_commit.deletions = 1
    
    mock_mod = MagicMock()
    mock_mod.change_type.name = "MODIFY"
    mock_mod.new_path = "src/main.py"
    mock_mod.old_path = "src/main.py"
    mock_mod.diff = "@@ -10,3 +10,5 @@\n-val = arr[idx]\n+if 0 <= idx < len(arr):\n+    val = arr[idx]"
    mock_mod.added = 1
    mock_mod.deleted = 1
    
    mock_commit.modified_files = [mock_mod]
    
    mock_miner = MagicMock()
    mock_miner.traverse_commits.return_value = [mock_commit]
    mock_pydriller_repo.return_value = mock_miner

    # 3. Setup mock PRs and Issues
    mock_pr = MagicMock()
    mock_pr.number = 42
    mock_pr.title = "Fix index bounds issue"
    mock_pr.body = "This fixes issue #101 by checking bounds."
    mock_pr.merged = True
    mock_pr.merged_at = datetime.now(timezone.utc)
    mock_pr.labels = []
    
    mock_comment = MagicMock()
    mock_comment.path = "src/main.py"
    mock_comment.diff_hunk = "@@ -10,3 +10,5 @@"
    mock_comment.body = "Nice fix!"
    mock_comment.user.login = "reviewer"
    mock_pr.get_review_comments.return_value = [mock_comment]
    
    mock_repo = MagicMock()
    mock_repo.get_pulls.return_value = [mock_pr]
    
    mock_issue = MagicMock()
    mock_issue.body = "API crashes when index is out of bounds."
    mock_repo.get_issue.return_value = mock_issue
    
    # Configure mock GitHub clients
    mock_pr_client = MagicMock()
    mock_pr_client.get_repo.return_value = mock_repo
    mock_pr_github.return_value = mock_pr_client
    
    mock_issues_client = MagicMock()
    mock_issues_client.get_repo.return_value = mock_repo
    mock_issues_github.return_value = mock_issues_client

    # 4. Instantiate configuration
    config = AppConfig()
    config.task = "all"
    config.output_format = "alpaca"
    config.collection.since = date(2020, 1, 1)

    writer = DatasetWriter(temp_output_dir)

    # 5. Run pipeline
    run_pipeline(
        repos=["test/repo"],
        config=config,
        token="faketoken",
        writer=writer,
        dry_run=False
    )

    report = writer.generate_report("alpaca", "all")

    # 6. Verify outputs
    assert os.path.exists(os.path.join(temp_output_dir, "dataset.jsonl"))
    assert os.path.exists(os.path.join(temp_output_dir, "dataset_with_meta.jsonl"))
    assert os.path.exists(os.path.join(temp_output_dir, "run_report.json"))

    assert report["stats"]["final_records"] > 0
    assert "test/repo" in report["repos_processed"]
