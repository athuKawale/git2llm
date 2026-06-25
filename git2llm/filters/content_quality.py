import re
import os
from typing import Tuple, List, Optional
from git2llm.models import CommitRecord
from git2llm.config import FilterConfig

IMPERATIVE_VERBS = {
    'add', 'fix', 'update', 'remove', 'refactor', 'improve', 'change',
    'implement', 'handle', 'support', 'move', 'rename', 'replace',
    'clean', 'extract', 'introduce', 'avoid', 'prevent', 'allow',
    'enable', 'disable', 'simplify', 'optimize', 'correct', 'resolve',
    'ensure', 'revert', 'migrate', 'deprecate', 'bump', 'configure',
    'create', 'delete', 'make', 'use', 'set', 'get', 'write', 'read',
    'run', 'load', 'save', 'check', 'validate', 'verify', 'show', 'hide'
}

STOP_WORDS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'if', 'then', 'else', 'for',
    'to', 'in', 'on', 'at', 'by', 'from', 'with', 'about', 'as', 'into',
    'of', 'is', 'it', 'its', 'this', 'that', 'these', 'those', 'are', 'was'
}

def verb_start_score(message: str) -> float:
    """Check if message starts with an imperative verb.
    
    Handles both:
    - Plain: 'Fix crash in parser'
    - Scoped: 'runtime: fix crash in parser'  (Go, Linux kernel style)
    - Conventional: 'fix(scope): description'
    """
    subject = message.strip()
    if not subject:
        return 0.0

    # Strip conventional commit type prefix: 'fix(scope):' or 'feat:'
    subject = re.sub(r'^\w+\([^)]*\):\s*', '', subject)
    # Strip plain scope prefix: 'runtime:', 'cmd/link:', 'net/http:' etc.
    subject = re.sub(r'^[\w/.-]+:\s+', '', subject)

    words = subject.split()
    if not words:
        return 0.0
    # Strip non-alpha characters from first word (like dots, colons, brackets)
    first_word = re.sub(r'[^a-zA-Z]', '', words[0]).lower()

    # Handle third person (e.g. "fixes" -> "fix")
    if first_word.endswith('es') and first_word[:-2] in IMPERATIVE_VERBS:
        return 1.0
    if first_word.endswith('s') and not first_word.endswith('ss') and first_word[:-1] in IMPERATIVE_VERBS:
        return 1.0

    return 1.0 if first_word in IMPERATIVE_VERBS else 0.0

def informativeness_score(message: str, commit: CommitRecord) -> float:
    subj = commit.message_subject.strip()
    words = [w.lower() for w in subj.split() if w.isalnum()]
    
    if len(words) < 3:
        return 0.2
        
    # If the message is just generic words
    generic_phrases = {
        ('fix', 'bug'), ('update', 'code'), ('clean', 'up'),
        ('fix', 'issue'), ('minor', 'fix'), ('update', 'readme')
    }
    for i in range(len(words) - 1):
        if (words[i], words[i+1]) in generic_phrases:
            return 0.3
            
    # Check if message subject is just filename
    for f in commit.files_changed:
        basename = os.path.basename(f.filename).lower()
        if subj.lower() == basename or subj.lower() == f.filename.lower():
            return 0.1
            
    return 1.0

def alignment_score(message: str, commit: CommitRecord) -> float:
    # Lowercase and tokenise message
    subj_tokens = {w.lower() for w in message.split() if len(w) > 3 and w.lower() not in STOP_WORDS}
    if not subj_tokens:
        return 1.0  # Default to 1.0 if no searchable terms
        
    # Collect words from changed file names and diffs
    diff_text = ""
    for f in commit.files_changed:
        diff_text += f" {f.filename} {f.diff or ''}"
    diff_text_lower = diff_text.lower()
    
    matches = 0
    for token in subj_tokens:
        # Strip punctuation from token
        clean_token = re.sub(r'\W+', '', token)
        if clean_token and clean_token in diff_text_lower:
            matches += 1
            
    return float(matches) / len(subj_tokens)

def language_bonus(commit: CommitRecord) -> float:
    # Boost if has standard source code languages, penalise if only yaml/json/markdown
    has_code = False
    for f in commit.files_changed:
        if f.language and f.language not in {"yaml", "json", "markdown"}:
            has_code = True
            break
    return 1.0 if has_code else 0.5

def check_content_quality(commit: CommitRecord, config: FilterConfig) -> Tuple[bool, float, Optional[str]]:
    """
    Run Stage 3: Content Quality Scoring.
    Returns (passed, score, reason_if_failed).
    """
    msg = commit.message_subject
    
    v_score = verb_start_score(msg)
    i_score = informativeness_score(msg, commit)
    a_score = alignment_score(msg, commit)
    l_score = language_bonus(commit)
    
    score = (
        0.3 * v_score +
        0.3 * i_score +
        0.2 * a_score +
        0.2 * l_score
    )
    
    # Alignment check
    min_align = getattr(config, "min_alignment_score", 0.0)
    if a_score < min_align:
        return False, score, "content_quality:alignment_below_threshold"

    # Optional constraint: require verb start (V-DO pattern)
    if config.require_verb_start and v_score < 1.0:
        return False, score, "content_quality:no_verb_start"
        
    if score < config.min_content_score:
        return False, score, "content_quality:score_below_threshold"
        
    return True, score, None
