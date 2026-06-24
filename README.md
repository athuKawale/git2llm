# git2llm — GitHub to LLM Fine-Tuning Dataset Generator

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
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
   - **Stage 2 (Structural)**: Filters based on message word count, diff lines (prevents too small/large diffs), and changed file count.
   - **Stage 3 (Scoring)**: Evaluates message informativeness and V-DO (Verb-Direct Object) imperative start patterns (e.g. *Add*, *Fix*, *Refactor*).
   - **Stage 4 (Deduplication)**: Eliminates identical or near-duplicate commits/diffs using MinHash LSH (Jaccard similarity).
5. **Output Schemas**: Formats datasets directly into **Alpaca** (`instruction`/`input`/`output`) or **ShareGPT** (`conversations` list) format.

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

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) or details in project metadata.
