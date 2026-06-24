import re
import os
from typing import Tuple, Optional
from git2llm.models import CommitRecord
from git2llm.config import FilterConfig

REVERT_PATTERN = re.compile(r'^revert\s+"?.+?"?\s*$', re.IGNORECASE)

BOT_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'bot$', r'\[bot\]', r'github-actions', r'dependabot',
        r'renovate', r'snyk-bot', r'greenkeeper', r'semantic-release',
        r'codecov', r'allcontributors', r'auto-commit', r'ci-bot'
    ]
]

TEXT_EXTENSIONS = {
    '.py', '.js', '.ts', '.go', '.java', '.rb', '.rs', '.cpp', '.c', '.h', '.cs', '.md',
    '.html', '.css', '.sh', '.yml', '.yaml', '.json', '.xml', '.txt', '.sql', '.toml',
    '.ini', '.cfg', '.conf', '.php', '.pl', '.pm', '.kt', '.swift', '.m', '.gradle',
    '.properties', '.bat', '.cmd', '.ps1', '.lock'
}

LOCKFILE_PATTERNS = [
    'package-lock.json', 'yarn.lock', 'pipfile.lock',
    'poetry.lock', 'go.sum', 'cargo.lock', '.lock',
    '__pycache__', '.pyc', 'node_modules/', 'dist/', 'build/'
]

WIP_PATTERN = re.compile(
    r'^(wip|draft|todo|fixup!|squash!|temp|test commit|debugging)',
    re.IGNORECASE
)

VERSION_BUMP_PATTERN = re.compile(
    r'^(bump|chore\(release\)|release|version)[\s:].*(v?\d+\.\d+)',
    re.IGNORECASE
)

VERSION_FILES = {
    'package.json', 'pyproject.toml', 'cargo.toml', 'setup.py', 
    'pom.xml', 'build.gradle', 'version.txt', 'version.py', 'setup.cfg'
}

URL_ONLY = re.compile(r'^https?://\S+$')
TICKET_ONLY = re.compile(r'^[a-z]+-\d+$', re.IGNORECASE)

def check_hard_exclusions(commit: CommitRecord, config: FilterConfig) -> Tuple[bool, Optional[str]]:
    """
    Run Stage 1: Hard Exclusions.
    Returns (passed, reason_if_failed).
    """
    # 1.1 Merge commits
    if config.exclude_merge_commits:
        if commit.is_merge or len(commit.parent_shas) > 1 or commit.message_subject.lower().startswith(("merge branch", "merge pull request", "merge ")):
            return False, "hard_exclusion:is_merge"

    # 1.2 Revert commits
    if config.exclude_revert_commits:
        if REVERT_PATTERN.match(commit.message_subject.strip()):
            return False, "hard_exclusion:is_revert"

    # 1.3 Bot / automated authors
    if config.exclude_bot_authors:
        author_string = f"{commit.author} {commit.author_email or ''}".lower()
        if any(p.search(author_string) for p in BOT_PATTERNS):
            return False, "hard_exclusion:is_bot"

    # 1.4 Binary-only changes
    if config.exclude_binary_only:
        if not commit.files_changed:
            return False, "hard_exclusion:no_files"
        has_text_file = any(
            os.path.splitext(f.filename)[1].lower() in TEXT_EXTENSIONS
            for f in commit.files_changed
        )
        if not has_text_file:
            return False, "hard_exclusion:binary_only"

    # 1.5 Lock file / auto-generated file only
    if commit.files_changed:
        is_only_lock_or_generated = True
        for f in commit.files_changed:
            filename = f.filename.lower()
            if not any(pat in filename for pat in LOCKFILE_PATTERNS):
                is_only_lock_or_generated = False
                break
        if is_only_lock_or_generated:
            return False, "hard_exclusion:lockfile_only"

    # 1.6 Empty or trivially short commit message
    subj_stripped = commit.message_subject.strip()
    if not subj_stripped or subj_stripped.lower() in {".", "-", "fix", "update", "wip", "commit"}:
        return False, "hard_exclusion:empty_or_trivial_message"

    # 1.7 WIP / Draft commits
    if config.exclude_wip_messages:
        if WIP_PATTERN.match(subj_stripped):
            return False, "hard_exclusion:wip_message"

    # 1.8 Version bump only commits
    if VERSION_BUMP_PATTERN.match(subj_stripped):
        if not commit.files_changed:
            return False, "hard_exclusion:version_bump_only"
        all_version_files = all(
            os.path.basename(f.filename).lower() in VERSION_FILES
            for f in commit.files_changed
        )
        if all_version_files:
            return False, "hard_exclusion:version_bump_only"

    # 1.9 Commit message is a URL or ticket ID only
    if URL_ONLY.match(subj_stripped):
        return False, "hard_exclusion:url_only_message"
    if TICKET_ONLY.match(subj_stripped):
        return False, "hard_exclusion:ticket_only_message"

    return True, None
