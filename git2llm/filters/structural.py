from typing import Tuple, Optional
from git2llm.models import CommitRecord, PRRecord
from git2llm.config import FilterConfig

def count_words(text: str) -> int:
    if not text:
        return 0
    return len(text.strip().split())

def get_total_diff_lines(commit: CommitRecord) -> int:
    total = 0
    for f in commit.files_changed:
        if f.diff:
            total += len(f.diff.splitlines())
    return total

# Gerrit / DCO / GitHub commit trailers to strip before checking message length
_TRAILER_PREFIXES = (
    "Change-Id:", "Reviewed-on:", "Reviewed-by:", "Auto-Submit:",
    "LUCI-TryBot-Result:", "Cq-Include-Trybots:", "Commit-Queue:",
    "Signed-off-by:", "Co-authored-by:", "Closes:", "Fixes:",
    "See:", "Related:", "Refs:", "Cc:", "Acked-by:", "Tested-by:",
    "cherry picked from", "(cherry picked from",
)

def _strip_trailers(body: str) -> str:
    """Strip standard commit trailers from a commit message body."""
    if not body:
        return body
    lines = body.splitlines()
    result_lines = []
    in_trailer_block = False
    for line in lines:
        stripped = line.strip()
        is_trailer = any(stripped.startswith(p) for p in _TRAILER_PREFIXES)
        if is_trailer:
            in_trailer_block = True
            continue
        if in_trailer_block and not stripped:
            # Skip blank lines within a trailer block
            continue
        if not is_trailer:
            in_trailer_block = False
        result_lines.append(line)
    return "\n".join(result_lines).strip()

def check_structural_commit(commit: CommitRecord, config: FilterConfig) -> Tuple[bool, Optional[str]]:
    """
    Run Stage 2: Structural Quality Checks for commits.
    Returns (passed, reason_if_failed).
    """
    # 2.1 Commit message length/word count — strip trailers before checking
    # so that repos using Gerrit (golang, chromium, etc.) aren't penalized
    clean_body = _strip_trailers(commit.message_body)
    full_message = f"{commit.message_subject}\n{clean_body}".strip()
    words = count_words(full_message)
    if words < config.min_commit_message_words:
        return False, "structural:message_too_short"
        
    if len(full_message) > config.max_commit_message_chars:
        return False, "structural:message_too_long"

    # 2.3 File count
    files_count = len(commit.files_changed)
    if files_count < config.min_files_changed:
        return False, "structural:too_few_files"
    if files_count > config.max_files_changed:
        return False, "structural:too_many_files"

    # 2.2 Diff size
    total_diff_lines = get_total_diff_lines(commit)
    if total_diff_lines < config.min_diff_lines:
        return False, "structural:diff_too_small"
    if total_diff_lines > config.max_diff_lines:
        return False, "structural:diff_too_large"

    return True, None

def check_structural_pr(pr: PRRecord, config: FilterConfig) -> Tuple[bool, Optional[str]]:
    """
    Run Stage 2: Structural Quality Checks for PRs.
    Returns (passed, reason_if_failed).
    """
    # 2.4 PR body length
    body_words = count_words(pr.body)
    if body_words < config.min_pr_body_words:
        return False, "structural:pr_body_too_short"

    # Diff size
    if pr.diff:
        diff_lines = len(pr.diff.splitlines())
        if diff_lines < config.min_diff_lines:
            return False, "structural:pr_diff_too_small"
        if diff_lines > config.max_diff_lines:
            return False, "structural:pr_diff_too_large"
    else:
        return False, "structural:pr_diff_missing"

    return True, None
