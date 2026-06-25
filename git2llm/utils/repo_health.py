"""
repo_health.py — Pre-flight checks for GitHub repos before PR collection.

Detects repos that use external code review systems (Gerrit, Phabricator, etc.)
where GitHub is just a read-only mirror with no real merged PRs.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from github import Github

# Known external review systems and their detection signals
_EXTERNAL_SYSTEMS = [
    {
        "name": "Gerrit",
        "signals": [
            "go-review.googlesource.com",
            "chromium-review.googlesource.com",
            "android-review.googlesource.com",
            "gerrit-review.googlesource.com",
            "review.openstack.org",
            "gerrit.",
            "Reviewed-on: https://",
            "Change-Id: I",
        ],
        "bot_patterns": [r"gopherbot", r"gerrit-bot", r"chromium-bot"],
        "doc_url": "https://gerrit-review.googlesource.com/",
    },
    {
        "name": "Phabricator",
        "signals": [
            "phabricator",
            "phab.llvm.org",
            "differential revision",
            "D[0-9]+",          # Phabricator revision IDs
        ],
        "bot_patterns": [r"phab-bot", r"phabricator-bot"],
        "doc_url": "https://www.phacility.com/phabricator/",
    },
    {
        "name": "GitLab MR",
        "signals": [
            "gitlab.com/.*/-/merge_requests/",
            "This PR was opened from a GitLab",
        ],
        "bot_patterns": [r"gitlab-bot"],
        "doc_url": "https://gitlab.com",
    },
    {
        "name": "Internal Review Tool",
        "signals": [
            "internally reviewed",
            "reviewed internally",
            "internal review",
        ],
        "bot_patterns": [],
        "doc_url": None,
    },
]


@dataclass
class RepoHealthResult:
    repo_name: str
    merge_rate: float          # Fraction of sampled closed PRs that were merged
    total_sampled: int
    merged_count: int
    external_system: Optional[str] = None   # e.g. "Gerrit", "Phabricator"
    system_doc_url: Optional[str] = None
    bot_usernames: list = field(default_factory=list)
    example_signals: list = field(default_factory=list)

    @property
    def is_github_native(self) -> bool:
        """True if PRs are reviewed and merged natively on GitHub."""
        return self.external_system is None and self.merge_rate >= 0.15

    @property
    def confidence(self) -> str:
        if self.external_system and self.merge_rate < 0.05:
            return "high"
        if self.merge_rate < 0.10:
            return "medium"
        return "low"


def check_repo_pr_health(
    github_client: Github,
    repo_name: str,
    sample_size: int = 30,
) -> RepoHealthResult:
    """
    Sample the most recent closed PRs to detect if the repo uses an external
    code review system. Returns a RepoHealthResult with findings.

    Args:
        github_client: Authenticated PyGithub client.
        repo_name: Full repo name, e.g. 'golang/go'.
        sample_size: Number of closed PRs to sample (more = more accurate).
    """
    try:
        repo = github_client.get_repo(repo_name)
    except Exception:
        # If we can't even fetch the repo, skip health check
        return RepoHealthResult(
            repo_name=repo_name,
            merge_rate=1.0,
            total_sampled=0,
            merged_count=0,
        )

    pulls = repo.get_pulls(state="closed", sort="updated", direction="desc")

    merged_count = 0
    total = 0
    detected_system: Optional[str] = None
    system_url: Optional[str] = None
    bot_usernames: set = set()
    example_signals: list = []

    for pr in pulls:
        if total >= sample_size:
            break
        total += 1

        if pr.merged_at is not None:
            merged_count += 1
            continue

        # PR is closed-without-merge — inspect for external review signals
        body = (pr.body or "").lower()
        title = (pr.title or "").lower()
        author_login = (pr.user.login if pr.user else "").lower()
        combined_text = f"{body} {title} {author_login}"

        for system in _EXTERNAL_SYSTEMS:
            # Check text signals
            for signal in system["signals"]:
                if signal.lower() in combined_text or re.search(signal, combined_text, re.IGNORECASE):
                    if not detected_system:
                        detected_system = system["name"]
                        system_url = system.get("doc_url")
                    if len(example_signals) < 3:
                        # Store a short snippet for user display
                        snippet = signal if len(signal) < 40 else signal[:40] + "…"
                        example_signals.append(f'"{snippet}" in PR #{pr.number}')
                    break

            # Check bot usernames
            for bot_pattern in system["bot_patterns"]:
                if re.search(bot_pattern, author_login):
                    bot_usernames.add(pr.user.login)
                    if not detected_system:
                        detected_system = system["name"]
                        system_url = system.get("doc_url")

    merge_rate = merged_count / total if total > 0 else 0.0

    return RepoHealthResult(
        repo_name=repo_name,
        merge_rate=merge_rate,
        total_sampled=total,
        merged_count=merged_count,
        external_system=detected_system,
        system_doc_url=system_url,
        bot_usernames=sorted(bot_usernames),
        example_signals=example_signals,
    )


def format_health_warning(result: RepoHealthResult) -> str:
    """Return a rich-formatted warning string for display in the CLI."""
    pct = f"{result.merge_rate * 100:.0f}%"
    lines = [
        f"[bold yellow]⚠  Repo Health Warning: {result.repo_name}[/bold yellow]",
        "",
    ]

    if result.external_system:
        lines.append(
            f"  This repo appears to use [bold]{result.external_system}[/bold] "
            f"for code reviews, not GitHub Pull Requests."
        )
        if result.system_doc_url:
            lines.append(f"  Review system: [cyan]{result.system_doc_url}[/cyan]")
    else:
        lines.append(
            "  This repo has a very low GitHub PR merge rate — it may use an "
            "external review workflow."
        )

    lines += [
        "",
        f"  Sampled [bold]{result.total_sampled}[/bold] recent closed PRs — "
        f"only [bold red]{pct}[/bold red] were merged via GitHub "
        f"({result.merged_count}/{result.total_sampled}).",
    ]

    if result.example_signals:
        lines.append("")
        lines.append("  Detection signals found:")
        for sig in result.example_signals:
            lines.append(f"    • {sig}")

    if result.bot_usernames:
        bots = ", ".join(f"@{u}" for u in result.bot_usernames[:5])
        lines.append(f"  Bot accounts detected: {bots}")

    lines += [
        "",
        "  [dim]Tasks [bold]pr_review[/bold] and [bold]issue_to_patch[/bold] "
        "require merged GitHub PRs and will likely yield [bold]0 records[/bold] "
        "for this repo.[/dim]",
        "",
        "  Suggested alternatives: [cyan]django/django[/cyan], "
        "[cyan]huggingface/transformers[/cyan], [cyan]rust-lang/rust[/cyan]",
    ]

    return "\n".join(lines)
