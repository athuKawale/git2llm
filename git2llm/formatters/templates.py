COMMIT_TO_MESSAGE_INSTRUCTION = (
    "You are an expert software engineer. Given a code diff, write a clear and informative commit message.\n"
    "The commit message should:\n"
    "- Start with an imperative verb (Add, Fix, Refactor, Update, Remove, etc.)\n"
    "- Be concise (≤72 chars for the subject line)\n"
    "- Explain *what* changed and *why*, not *how*"
)

ISSUE_TO_PATCH_INSTRUCTION = (
    "You are an expert software engineer. Given the issue description and the current state of the relevant file(s), "
    "produce a minimal, correct git patch that resolves the issue."
)

PR_REVIEW_INSTRUCTION = (
    "You are an expert code reviewer. Review the following pull request diff and provide specific, actionable feedback."
)
