import pytest
from datetime import datetime, timezone
from git2llm.models import CommitRecord, FileChange
from git2llm.config import FilterConfig
from git2llm.filters.hard_exclusions import check_hard_exclusions
from git2llm.filters.structural import check_structural_commit
from git2llm.filters.content_quality import check_content_quality
from git2llm.filters.dedup import Deduplicator

@pytest.fixture
def base_commit():
    return CommitRecord(
        sha="a1b2c3d4",
        repo="owner/repo",
        message_subject="Fix authentication bug in JWT handler",
        message_body="Resolves security issue by checking token expiry date correctly.",
        author="John Doe",
        author_email="john@doe.com",
        timestamp=datetime.now(timezone.utc),
        files_changed=[
            FileChange(
                filename="src/auth.py",
                change_type="MODIFY",
                diff="@@ -42,3 +42,5 @@\n-    return jwt.decode(token)\n+    return jwt.decode(token, options={'verify_exp': True})",
                additions=1,
                deletions=1,
                language="python"
            )
        ],
        total_additions=1,
        total_deletions=1,
        is_merge=False,
        parent_shas=["parent123"]
    )

@pytest.fixture
def default_config():
    return FilterConfig()

def test_valid_commit_passes(base_commit, default_config):
    # Test that a normal high-quality commit passes hard exclusions and structural checks
    passed1, reason1 = check_hard_exclusions(base_commit, default_config)
    assert passed1 is True
    
    passed2, reason2 = check_structural_commit(base_commit, default_config)
    assert passed2 is True
    
    passed3, score, reason3 = check_content_quality(base_commit, default_config)
    assert passed3 is True
    assert score >= default_config.min_content_score

def test_merge_commit_excluded(base_commit, default_config):
    base_commit.is_merge = True
    passed, reason = check_hard_exclusions(base_commit, default_config)
    assert passed is False
    assert "is_merge" in reason

def test_bot_author_excluded(base_commit, default_config):
    base_commit.author = "dependabot[bot]"
    passed, reason = check_hard_exclusions(base_commit, default_config)
    assert passed is False
    assert "is_bot" in reason

def test_binary_only_excluded(base_commit, default_config):
    base_commit.files_changed = [
        FileChange(
            filename="assets/logo.png",
            change_type="MODIFY",
            diff="",
            additions=0,
            deletions=0,
            language=None
        )
    ]
    passed, reason = check_hard_exclusions(base_commit, default_config)
    assert passed is False
    assert "binary_only" in reason

def test_lockfile_only_excluded(base_commit, default_config):
    base_commit.files_changed = [
        FileChange(
            filename="poetry.lock",
            change_type="MODIFY",
            diff="lockfile content",
            additions=100,
            deletions=50,
            language="toml"
        )
    ]
    passed, reason = check_hard_exclusions(base_commit, default_config)
    assert passed is False
    assert "lockfile_only" in reason

def test_short_message_excluded(base_commit, default_config):
    base_commit.message_subject = "fix"
    base_commit.message_body = ""
    # Hard exclusions should catch empty/trivial
    passed, reason = check_hard_exclusions(base_commit, default_config)
    assert passed is False
    assert "empty_or_trivial" in reason
    
    # Let's test a message that has 3 words (fails min_commit_message_words = 5)
    base_commit.message_subject = "fix auth bug"
    passed, reason = check_structural_commit(base_commit, default_config)
    assert passed is False
    assert "message_too_short" in reason

def test_wip_message_excluded(base_commit, default_config):
    base_commit.message_subject = "WIP: fix auth bug"
    passed, reason = check_hard_exclusions(base_commit, default_config)
    assert passed is False
    assert "wip_message" in reason

def test_deduplicator(base_commit):
    dedup = Deduplicator(threshold=0.60, method="minhash")
    
    text1 = "This is a longer test message to check if near duplication works properly with MinHash LSH."
    diff1 = "@@ -1,5 +1,5 @@\n-line 1\n-line 2\n+line 1 modified\n+line 2 modified"
    
    text3 = "This is a longer test message to check if near duplication works nicely with MinHash LSH."
    
    # First time: unique
    is_dup1 = dedup.add_and_check("rec1", text1, diff1)
    assert is_dup1 is False
    
    # Second time with same content: duplicate
    is_dup2 = dedup.add_and_check("rec2", text1, diff1)
    assert is_dup2 is True
    
    # Near duplicate check
    is_dup3 = dedup.add_and_check("rec3", text3, diff1)
    assert is_dup3 is True

