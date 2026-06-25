# git2llm — GitHub to LLM Fine-Tuning Dataset Generator

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Build Status](https://img.shields.io/badge/tests-passed-green.svg)](#testing)

`git2llm` is a plug-and-play CLI tool and Python library that authenticates with GitHub, discovers repositories, mines commits, pull requests, issues, and tags in parallel, applies aggressive multi-stage quality filters, and generates clean JSONL datasets in Alpaca or ShareGPT format ready to drop into Unsloth, LLaMA-Factory, or Axolotl.

---

## Technology Stack

The project relies on the following key dependencies:
- **Core Engine**: Python `>=3.10`
- **Git Mining**: `pydriller` (shallow clones and commits traversal)
- **GitHub API Client**: `pygithub` (pull requests, issues, and release notes)
- **CLI & TUI**: `click` (CLI parser), `inquirerpy` (interactive checkbox prompts), `rich` (logging and progress visualizer)
- **Data & Configuration**: `pydantic` v2 (data validation and configuration models), `pyyaml` (YAML profiles)
- **Algorithms**: `datasketch` (MinHash LSH deduplication), `tenacity` (exponential backoff retry helper)
- **Environment**: `uv` package manager

---

## Project Architecture

`git2llm` is structured to minimize GitHub API consumption by performing commit mining locally via shallow clones, reserving GitHub REST API calls for PR and issue metadata.

```
                  ┌─────────────────────────────────────────┐
                  │               git2llm CLI               │
                  └────────────────────┬────────────────────┘
                                       │
                       ┌───────────────▼───────────────┐
                       │          Auth Layer           │
                       │   (PAT or OAuth Device Flow)  │
                       └───────────────┬───────────────┘
                                       │ token
                       ┌───────────────▼───────────────┐
                       │     Repo Discovery & TUI      │
                       └───────────────┬───────────────┘
                                       │ repositories
                       ┌───────────────▼───────────────┐
                       │     Orchestrator Thread Pool  │
                       └──┬─────────────────────────┬──┘
                          │                         │
                 ┌────────▼────────┐       ┌────────▼────────┐
                 │ Commit Collector│       │  PR Collector   │
                 │  (PyDriller)    │       │  (PyGithub API) │
                 └────────┬────────┘       └────────┬────────┘
                          │                         │
                          └────────────┬────────────┘
                                       │ raw records
                       ┌───────────────▼───────────────┐
                       │     Quality Filter Pipeline   │
                       │  - Stage 1: Hard Exclusions   │
                       │  - Stage 2: Structural Checks │
                       │  - Stage 3: Content Scoring   │
                       │  - Stage 4: MinHash Dedup     │
                       └───────────────┬───────────────┘
                                       │ clean records
                       ┌───────────────▼───────────────┐
                       │       Schema Formatter        │
                       │     (Alpaca / ShareGPT)       │
                       └───────────────┬───────────────┘
                                       │
                       ┌───────────────▼───────────────┐
                       │       DatasetWriter           │
                       │ (dataset.jsonl & run_report)  │
                       └───────────────────────────────┘
```

---

## Key Features

1. **Authentication Options**: Supports GitHub Personal Access Token (PAT) or GitHub OAuth Device Flow (enter a code in your browser, no local browser launch required).
2. **Interactive Selection**: Discovers all org and personal repositories and presents an interactive checkbox list in the terminal.
3. **Data Collectors**:
   - **Commits**: Clones shallow copy (`--depth=500 --filter=blob:none`) and mines commit messages and patches.
   - **Pull Requests**: Gathers merged PRs, inline review comments, and associated diff hunks.
   - **Issues**: Resolves linked issues from PR bodies to extract problem descriptions.
   - **Tags**: Gathers release notes for version changelog generation tasks.
4. **4-Stage Quality Pipeline**:
   - **Stage 1 (Exclusions)**: Ignores merge commits, bot authors, revert commits, binary/lockfiles, and draft/WIP messages.
   - **Stage 2 (Structural)**: Filters based on message/PR word count, diff lines (prevents too small/large diffs), changed file count, and minimum issue description length (`min_issue_to_patch_words`).
   - **Stage 3 (Scoring & Alignment)**: Evaluates message informativeness, V-DO (Verb-Direct Object) imperative start patterns (e.g., *Add*, *Fix*, *Refactor*), and semantic overlap between commit messages and code diffs (`min_alignment_score`).
   - **Stage 4 (Deduplication)**: Eliminates identical or near-duplicate commits/diffs using MinHash LSH (Jaccard similarity).
5. **Output Schemas**: Formats datasets directly into **Alpaca** (`instruction`/`input`/`output`) or **ShareGPT** (`conversations` list) format.
6. **Context Optimization (`issue_to_patch`)**: Combines PR titles, descriptions, and linked issues while stripping HTML comment templates, and enforces a configurable minimum word count constraint (`min_issue_to_patch_words`) to ensure high-quality fine-tuning samples.

---

## Project Structure

```
git2llm/
├── configs/
│   ├── default.yaml            # Standard pipeline filtering settings
│   ├── permissive.yaml         # Loose filtering constraints
│   └── strict.yaml             # Highly strict constraints (academic standard)
├── git2llm/
│   ├── auth/                   # PAT/OAuth login and token caching
│   ├── collectors/             # PyDriller/PyGithub mining algorithms
│   ├── discovery/              # Repository lister and checkbox TUI
│   ├── filters/                # Stages 1 to 4 quality pipeline
│   ├── formatters/             # Alpaca and ShareGPT template engines
│   ├── cli.py                  # Click CLI entry point
│   ├── config.py               # Pydantic configuration loader
│   ├── models.py               # Standardized data objects
│   ├── orchestrator.py         # Multi-threaded repository orchestrator
│   ├── writer.py               # Output files and run stats writer
│   └── utils/                  # Git and API rate-limiting utilities
├── tests/
│   ├── integration/            # Mocked end-to-end integration tests
│   └── unit/                   # Heuristic and filtering unit tests
├── pyproject.toml              # Build settings and dependencies
└── README.md
```

---

## Dataset Generation Tasks

`git2llm` supports generating datasets for three primary training tasks. Each task generates standard instruction tuning records (available in Alpaca or ShareGPT format):

### 1. `commit_message`
- **Purpose**: Trains models to generate conventional commit messages from code changes.
- **Pipeline Flow**: Traverses commits locally, filters out merges/bots/reverts, evaluates imperative verb usage, and checks semantic alignment.
- **Command**:
  ```bash
  uv run git2llm run -r owner/repo -t commit_message --format [alpaca|sharegpt]
  ```
- **Configuration Params (YAML / Profiles)**:
  - `min_commit_message_words` (default: `5`): Minimum words required in the commit message.
  - `max_commit_message_chars` (default: `500`): Maximum characters allowed.
  - `min_content_score` (default: `0.5`): Minimum score based on verb start, informativeness, and language.
  - `min_alignment_score` (default: `0.15`): Hard filter requiring minimum token overlap between the commit message and the diff.
  - `require_verb_start` (default: `true`): Requires the commit message to start with an imperative verb (e.g. *Add*, *Fix*, *Refactor*).
- **Dataset Structure (Alpaca)**:
  - **Instruction**: `"You are an expert software engineer. Given a code diff, write a clear and informative commit message."`
  - **Input**: The unified git diff.
  - **Output**: The conventional commit subject line.

### 2. `pr_review`
- **Purpose**: Trains models to perform code reviews and write inline feedback comments.
- **Pipeline Flow**: Gathers merged PRs, collects inline review comments with their diff hunks, and filters out short description PRs.
- **Command**:
  ```bash
  uv run git2llm run -r owner/repo -t pr_review --format [alpaca|sharegpt]
  ```
- **Configuration Params (YAML / Profiles)**:
  - `min_pr_body_words` (default: `20`): Discards PRs where the description is too short.
  - `dedup_threshold` (default: `0.85`): Removes near-duplicate PR diffs using MinHash LSH.
- **Dataset Structure (ShareGPT)**:
  - **Conversations**:
    - `system`: Code review system prompt.
    - `human`: PR title, description, and the full PR diff.
    - `gpt`: Inline review comments, formatted with paths, contextual diff hunks, and review feedback.

### 3. `issue_to_patch`
- **Purpose**: Trains autonomous coding agents to generate patches/diffs from issue descriptions and PR descriptions.
- **Pipeline Flow**: Gathers PRs and their linked issues, strips out HTML templates, merges description texts, and validates length.
- **Command**:
  ```bash
  uv run git2llm run -r owner/repo -t issue_to_patch --format [alpaca|sharegpt]
  ```
- **Configuration Params (YAML / Profiles)**:
  - `min_issue_to_patch_words` (default: `20`): Discards examples where the combined description context is too short.
  - `require_linked_issue` (default: `false`): If `true`, only processes PRs that have explicitly linked issues.
  - `min_diff_lines` (default: `3`): Minimum lines required in the diff patch.
  - `max_diff_lines` (default: `500`): Maximum lines allowed in the patch.
- **Dataset Structure (Alpaca)**:
  - **Instruction**: `"You are an expert software engineer. Given the issue description and the current state of the relevant file(s), produce a minimal, correct git patch that resolves the issue."`
  - **Input**: The combined PR title, PR description body, and linked issue bodies (with HTML comments stripped).
  - **Output**: The unified patch/diff.

---

## Getting Started

### Prerequisites

Ensure you have Git and Python `>=3.10` installed. Using `uv` is highly recommended.

### Installation

Clone the repository and install it in editable mode:

```bash
uv pip install -e .
```

### Setup Environment

Create a `.env` file (see `.env.example` as a template):

```bash
cp .env.example .env
```

Define your token:
```env
GIT2LLM_TOKEN=your_personal_access_token_here
```

### CLI Command Options

You can invoke the CLI directly using the registered script name:

```bash
# Verify installation
uv run git2llm --help
```

#### 1. Authenticate

```bash
# Save your personal access token locally
uv run git2llm auth --token ghp_yourtokenhere
```

#### 2. Run Generation Pipeline

```bash
# Run interactively (will prompt to pick repos, and then prompt to pick branches)
uv run git2llm run --format sharegpt

# Run with a built-in profile preset (default, strict, permissive)
uv run git2llm run -r owner/repo1 --profile permissive

# Run with a custom config file
uv run git2llm run \
  -r owner/repo1 -r owner/repo2 \
  -b main -b develop \
  --format alpaca \
  --task commit_message \
  --config configs/strict.yaml \
  --output ./dataset_outputs
```

#### 3. Initialize Custom Configuration File

If you want to customize configuration parameters, generate a starter YAML file from one of the built-in profiles:

```bash
# Generate a starter configuration file from the permissive profile
uv run git2llm init-config permissive -o configs/my_custom_config.yaml
```

You can then customize `configs/my_custom_config.yaml` and run the pipeline using the `--config` option pointing to it.

#### 4. Split Dataset

After generating a dataset (e.g. `git2llm_output/dataset.jsonl`), you can split it into training (`train.jsonl`) and evaluation (`eval.jsonl`) files:

```bash
# Split with default 10% evaluation set and shuffle enabled
uv run git2llm split git2llm_output/dataset.jsonl

# Split with a specific 20% eval ratio and random seed
uv run git2llm split git2llm_output/dataset.jsonl --eval-ratio 0.2 --seed 1234
```

Options:
* `-r, --eval-ratio FLOAT`: Proportion of dataset to assign to evaluation (default: `0.1`).
* `-s, --seed INTEGER`: Random seed for shuffling reproducibility (default: `42`).
* `-o, --output-dir PATH`: Target output directory (defaults to same folder as input file).
* `--shuffle / --no-shuffle`: Toggle shuffling of records before splitting (default: `True`).

---

## Development Workflow

1. Install development dependencies:
   ```bash
   uv add --dev pytest pytest-asyncio
   ```
2. Make your edits inside `git2llm/`.
3. Create corresponding test fixtures in `tests/`.
4. Submit pull requests following **Conventional Commit** conventions (e.g. `feat: add tag collector`).

---

## Testing

Run all unit and integration test suites:

```bash
uv run pytest
```

---

## Coding Standards

- **Code Style**: Follow PEP 8 guidelines. Format code using standard tools (such as Ruff or Black).
- **Validation**: All configuration profiles and API contracts are defined using Pydantic v2 models.
- **Commits**: Follow Conventional Commits format (`feat: ...`, `fix: ...`, `refactor: ...`) for all development contributions.

---

## Contributing

1. Fork the repository and create a new branch.
2. Ensure new features are covered by unit or integration tests.
3. Verify that all tests pass (`uv run pytest`) before opening a pull request.

---

## License

This project is licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
