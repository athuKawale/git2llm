import pytest
from datetime import datetime, timezone
from git2llm.models import CommitRecord, FileChange, PRRecord, ReviewComment
from git2llm.formatters import (
    format_commit_to_alpaca,
    format_issue_pr_to_alpaca,
    format_pr_to_sharegpt
)

@pytest.fixture
def dummy_commit():
    return CommitRecord(
        sha="123456",
        repo="owner/repo",
        message_subject="Fix index out of bounds error",
        message_body="Checks boundaries of array index before accessing.",
        author="Alice",
        author_email="alice@dev.com",
        timestamp=datetime.now(timezone.utc),
        files_changed=[
            FileChange(
                filename="main.py",
                change_type="MODIFY",
                diff="@@ -10,3 +10,5 @@\n-val = arr[idx]\n+if 0 <= idx < len(arr):\n+    val = arr[idx]",
                additions=2,
                deletions=1,
                language="python"
            )
        ],
        total_additions=2,
        total_deletions=1,
        is_merge=False,
        parent_shas=["parent"]
    )

@pytest.fixture
def dummy_pr():
    return PRRecord(
        number=42,
        repo="owner/repo",
        title="Add validation logic to API requests",
        body="Implements basic input check to prevent server crashes.",
        diff="@@ -1,5 +1,6 @@\n+def validate(req):\n+    assert req is not None",
        review_comments=[
            ReviewComment(
                path="api.py",
                diff_hunk="@@ -1,5 +1,6 @@",
                body="Consider using a schema validator instead of raw asserts.",
                author="bob"
            )
        ],
        linked_issue_numbers=[101],
        linked_issue_bodies=["Issue #101:\nAPI crashes on empty requests."],
        labels=["enhancement"],
        merged_at=datetime.now(timezone.utc)
    )

def test_format_commit_to_alpaca(dummy_commit):
    res = format_commit_to_alpaca(dummy_commit, score=0.9)
    assert res["instruction"] is not None
    assert "main.py" in res["input"]
    assert res["output"] == "Fix index out of bounds error"
    assert res["_meta"]["repo"] == "owner/repo"
    assert res["_meta"]["score"] == 0.9

def test_format_issue_pr_to_alpaca(dummy_pr):
    res = format_issue_pr_to_alpaca(dummy_pr, score=0.85)
    assert "Issue #101" in res["input"]
    assert "validate" in res["output"]
    assert res["_meta"]["task"] == "issue_to_patch"
    assert res["_meta"]["score"] == 0.85

def test_format_pr_to_sharegpt(dummy_pr):
    res = format_pr_to_sharegpt(dummy_pr, score=0.95)
    assert len(res["conversations"]) == 3
    assert res["conversations"][0]["from"] == "system"
    assert res["conversations"][1]["from"] == "human"
    assert res["conversations"][2]["from"] == "gpt"
    assert "Consider using a schema validator" in res["conversations"][2]["value"]
    assert res["_meta"]["pr_number"] == 42

def test_format_issue_pr_to_alpaca_comment_stripping(dummy_pr):
    dummy_pr.body = "<!-- template comment -->Actual description of the PR."
    dummy_pr.linked_issue_bodies = ["<!-- issue template -->Issue details."]
    
    res = format_issue_pr_to_alpaca(dummy_pr, score=0.8)
    
    # Assert that HTML comments are stripped
    assert "template comment" not in res["input"]
    assert "issue template" not in res["input"]
    assert "Actual description of the PR" in res["input"]
    assert "Issue details" in res["input"]
