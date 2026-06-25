import os
import yaml
import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from git2llm.cli import cli

@pytest.fixture
def mock_github():
    with patch("git2llm.cli.PATAuth") as mock_auth:
        mock_client = MagicMock()
        mock_auth.return_value.get_github_client.return_value = mock_client
        mock_auth.return_value.get_token.return_value = "fake-token"
        
        # Mock user
        mock_user = MagicMock()
        mock_user.login = "testuser"
        mock_client.get_user.return_value = mock_user
        
        # Mock repos list
        mock_repo1 = MagicMock()
        mock_repo1.full_name = "test/repo1"
        mock_repo1.visibility = "public"
        mock_repo1.stars = 10
        mock_repo1.language = "Python"
        mock_repo1.updated_at = "2026-01-01"
        mock_client.get_repo.return_value.get_branches.return_value = []
        
        yield mock_client, mock_auth

@patch("git2llm.cli.run_pipeline")
@patch("git2llm.cli.list_accessible_repos")
@patch("git2llm.cli.select_repos")
@patch("git2llm.cli.select_task")
def test_cli_interactive_prompting(
    mock_select_task,
    mock_select_repos,
    mock_list_accessible_repos,
    mock_run_pipeline,
    mock_github
):
    mock_client, mock_auth = mock_github
    
    # Setup mocks
    mock_repo = MagicMock()
    mock_repo.full_name = "test/repo1"
    mock_repo.visibility = "public"
    mock_repo.stars = 10
    mock_repo.language = "Python"
    mock_repo.updated_at = "2026-01-01"
    mock_list_accessible_repos.return_value = [mock_repo]
    
    mock_select_repos.return_value = ["test/repo1"]
    mock_select_task.return_value = "issue_to_patch"
    
    runner = CliRunner()
    
    # 1. Test running with no repos/task specified -> prompts for repos & task
    result = runner.invoke(cli, ["run"])
    assert result.exit_code == 0
    mock_select_task.assert_called_once()
    mock_run_pipeline.assert_called_once()
    config_passed = mock_run_pipeline.call_args[1]["config"]
    assert config_passed.task == "issue_to_patch"

@patch("git2llm.cli.run_pipeline")
@patch("git2llm.cli.list_accessible_repos")
@patch("git2llm.cli.select_repos")
@patch("git2llm.cli.select_task")
def test_cli_interactive_with_task_specified(
    mock_select_task,
    mock_select_repos,
    mock_list_accessible_repos,
    mock_run_pipeline,
    mock_github
):
    mock_client, mock_auth = mock_github
    
    mock_repo = MagicMock()
    mock_repo.full_name = "test/repo1"
    mock_list_accessible_repos.return_value = [mock_repo]
    mock_select_repos.return_value = ["test/repo1"]
    
    runner = CliRunner()
    
    # 2. Test running with no repos, but task is specified via CLI option -> prompts for repos but NOT task
    result = runner.invoke(cli, ["run", "--task", "pr_review"])
    assert result.exit_code == 0
    mock_select_task.assert_not_called()
    mock_run_pipeline.assert_called_once()
    config_passed = mock_run_pipeline.call_args[1]["config"]
    assert config_passed.task == "pr_review"

@patch("git2llm.cli.run_pipeline")
@patch("git2llm.cli.select_task")
def test_cli_non_interactive_no_task_prompts(
    mock_select_task,
    mock_run_pipeline,
    mock_github
):
    mock_client, mock_auth = mock_github
    mock_select_task.return_value = "pr_review"
    runner = CliRunner()
    
    # 3. Test running non-interactively (repos specified via CLI), task not specified -> prompts for task
    result = runner.invoke(cli, ["run", "-r", "owner/repo"])
    assert result.exit_code == 0
    mock_select_task.assert_called_once()
    mock_run_pipeline.assert_called_once()
    config_passed = mock_run_pipeline.call_args[1]["config"]
    assert config_passed.task == "pr_review"

@patch("git2llm.cli.run_pipeline")
@patch("git2llm.cli.select_task")
def test_cli_non_interactive_with_task_specified(
    mock_select_task,
    mock_run_pipeline,
    mock_github
):
    mock_client, mock_auth = mock_github
    runner = CliRunner()
    
    # 4. Test running non-interactively with task specified
    result = runner.invoke(cli, ["run", "-r", "owner/repo", "-t", "all"])
    assert result.exit_code == 0
    mock_select_task.assert_not_called()
    mock_run_pipeline.assert_called_once()
    config_passed = mock_run_pipeline.call_args[1]["config"]
    assert config_passed.task == "all"

@patch("git2llm.cli.run_pipeline")
@patch("git2llm.cli.select_task")
def test_cli_non_interactive_with_config_file_no_task(
    mock_select_task,
    mock_run_pipeline,
    mock_github,
    tmp_path
):
    mock_client, mock_auth = mock_github
    
    # Create a temporary config YAML file
    config_data = {
        "task": "issue_to_patch",
        "filter": {
            "min_pr_body_words": 15
        }
    }
    cfg_file = tmp_path / "custom_config.yaml"
    with open(cfg_file, "w") as f:
        yaml.safe_dump(config_data, f)
        
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "-r", "owner/repo", "--config", str(cfg_file)])
    assert result.exit_code == 0
    mock_select_task.assert_not_called()
    mock_run_pipeline.assert_called_once()
    config_passed = mock_run_pipeline.call_args[1]["config"]
    assert config_passed.task == "issue_to_patch"

@patch("git2llm.cli.run_pipeline")
@patch("git2llm.cli.select_branches")
@patch("git2llm.cli.select_task")
def test_cli_limit_and_branch_prompt(
    mock_select_task,
    mock_select_branches,
    mock_run_pipeline,
    mock_github
):
    mock_client, mock_auth = mock_github
    mock_select_task.return_value = "commit_message"
    
    # Mock some branches to trigger the branch selection
    mock_branch = MagicMock()
    mock_branch.name = "feature-xyz"
    mock_client.get_repo.return_value.get_branches.return_value = [mock_branch]
    
    mock_select_branches.return_value = ["feature-xyz"]
    
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "-r", "owner/repo", "-n", "42"])
    
    assert result.exit_code == 0
    mock_select_branches.assert_called_once_with(["feature-xyz"])
    mock_select_task.assert_called_once()
    mock_run_pipeline.assert_called_once()
    config_passed = mock_run_pipeline.call_args[1]["config"]
    assert config_passed.collection.max_commits_per_repo == 42
    assert config_passed.collection.max_prs_per_repo == 42
    assert config_passed.collection.branches == ["feature-xyz"]

