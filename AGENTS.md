# cicaddy-action Development Guidelines

## Project Overview

GitHub Action that wraps cicaddy for running AI agent tasks in GitHub Actions workflows. The `cicaddy-github` plugin extends cicaddy with GitHub-specific agents, tools, and configuration.

## Architecture

### Plugin System

This package registers itself with cicaddy's plugin system via entry points in `pyproject.toml`:

- `cicaddy.agents` — registers GitHub-specific agents (e.g., `GitHubPRAgent`, `GitHubTaskAgent`)
- `cicaddy.settings_loader` — provides GitHub settings loader
- `cicaddy.cli_args` / `cicaddy.env_vars` / `cicaddy.validators` — CLI and config extensions

### Agent Registration

```python
# src/cicaddy_github/plugin.py
def register_agents():
    from cicaddy.agent.factory import AgentFactory
    from cicaddy_github.github_integration.agents import GitHubPRAgent, GitHubTaskAgent
    from cicaddy_github.github_integration.detector import _detect_github_agent_type

    AgentFactory.register("github_pr", GitHubPRAgent)
    AgentFactory.register("github_task", GitHubTaskAgent)
    AgentFactory.register_detector(_detect_github_agent_type, priority=40)
```

Detector priority 40 ensures GitHub detection runs before cicaddy's built-in CI detector at priority 50.

### Project Structure

```
cicaddy-action/
  action.yml                  # GitHub Action definition (inputs/outputs)
  Dockerfile                  # Container image (python:3.12-slim + uv)
  entrypoint.sh               # Maps GitHub Action inputs to cicaddy env vars
  pyproject.toml              # Package config (cicaddy-github plugin)
  tasks/
    pr_review.yml             # DSPy task for PR code review
    changelog_report.yml      # DSPy task for changelog generation
  src/cicaddy_github/
    plugin.py                 # Entry points: register_agents, get_cli_args, etc.
    config/settings.py        # Settings class extending CoreSettings
    github_integration/
      agents.py               # GitHubPRAgent, GitHubTaskAgent
      analyzer.py             # PyGithub wrapper (diff, PR data, comments)
      detector.py             # Auto-detect agent type from GitHub env
      tools.py                # Git operations (@tool decorated)
    security/
      leak_detector.py        # Secret redaction via detect-secrets
```

### Key Subpackages

| Package | Purpose |
|---------|---------|
| `src/cicaddy_github/github_integration/` | GitHub API client, agents, analyzers, tools |
| `src/cicaddy_github/config/` | GitHub settings (token, repository, PR number) |
| `src/cicaddy_github/security/` | Secret detection and redaction |
| `src/cicaddy_github/plugin.py` | Entry point registration for cicaddy plugin system |
| `tasks/` | DSPy task definitions for PR review and changelog generation |

### Dependencies

- Depends on `cicaddy>=0.8.0` (core library) and `PyGithub>=2.1.0`
- Follows the same agent/factory patterns as the core library
- Extends `BaseAIAgent` from cicaddy

## Agent Types

| Type | Class | Trigger |
|------|-------|---------|
| `github_pr` | `GitHubPRAgent` | `GITHUB_EVENT_NAME=pull_request` + `GITHUB_PR_NUMBER` |
| `github_task` | `GitHubTaskAgent` | `GITHUB_EVENT_NAME` present but not a PR |

## Sub-Agent Delegation (v0.5.0+)

Requires cicaddy>=0.8.0. When `DELEGATION_MODE=auto`, the parent agent's `analyze()` method delegates to specialized sub-agents:

1. **Triage** — AI analyzes the PR diff/context and selects reviewers
2. **Parallel Execution** — Selected sub-agents run concurrently with focused prompts
3. **Aggregation** — Results merged into a single PR comment with per-agent sections

### Plugin Hooks

The cicaddy-github plugin provides:

- `cicaddy.delegation_blocked_tools` entry point — blocks GitHub write operations (posting comments, submitting reviews, merging PRs, etc.) so sub-agents only perform analysis
- Delegation metadata in PR comments — shows which agents ran, success/failure counts, and execution time in a collapsible details block

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DELEGATION_MODE` | `none` | `none` or `auto` |
| `MAX_SUB_AGENTS` | `3` | Max concurrent sub-agents (1-10) |
| `SUB_AGENT_MAX_ITERS` | `5` | Iterations per sub-agent (1-15) |
| `DELEGATION_AGENTS_DIR` | `.agents/delegation` | Custom agent YAML directory |
| `TRIAGE_PROMPT` | (empty) | Custom triage instructions |

Action inputs: `delegation_mode`, `max_sub_agents`
CLI flags: `--delegation-mode auto --max-sub-agents 2`

See cicaddy's [sub-agent delegation docs](https://github.com/waynesun09/cicaddy/blob/main/docs/sub-agent-delegation.md) for built-in agents, custom YAML format, and tool filtering.

## Action Inputs

All inputs use **underscores** (not hyphens) for Docker container compatibility:

| Input | Required | Description |
|-------|----------|-------------|
| `ai_provider` | Yes | `gemini`, `openai`, `claude`, `anthropic-vertex` |
| `ai_model` | Yes | Model identifier |
| `ai_api_key` | No* | AI provider API key (not needed for `anthropic-vertex`) |
| `vertex_project_id` | No | GCP project ID (required for `anthropic-vertex`) |
| `cloud_ml_region` | No | Vertex AI region (default: `us-east5`) |
| `task_file` | No | Path to DSPy YAML task file |
| `task_prompt` | No | Inline task prompt |
| `post_pr_comment` | No | Post results as PR comment (default: `false`) |
| `github_token` | No | GitHub token (default: `${{ github.token }}`) |
| `mcp_servers_config` | No | JSON array of MCP server configs |
| `slack_webhook_url` | No | Slack webhook URL |
| `report_template` | No | Custom HTML report template path |

*Not required if provider-specific key is set via `env:`.

## Entrypoint Flow

`entrypoint.sh` bridges GitHub Action inputs to cicaddy environment:

1. Exports `AI_PROVIDER` and `AI_MODEL` from `INPUT_*` vars
2. Maps `INPUT_AI_API_KEY` to provider-specific env var (`GEMINI_API_KEY`, etc.)
3. Resolves `AI_TASK_FILE` and `REPORT_TEMPLATE` to absolute paths
4. Extracts `GITHUB_PR_NUMBER` from `GITHUB_REF` (`refs/pull/<N>/merge`)
5. Creates `.cicaddy/` subdirectory and `cd`s into it (cicaddy writes reports to `../`)
6. Runs `cicaddy run`

## Code Quality

- Run `pre-commit run --files <changed-files>` before committing
- Run `uv run pytest tests/ -q --cov=src/cicaddy_github` before committing (must pass all tests)
- Prefer shared/utility modules over code duplication
- Follow type hints, Google-style docstrings, async where appropriate

## Git Workflow

- **Sign commits**: `git commit -s` (DCO sign-off required)
- Only commit files modified in current session
- **No "Generated with Claude Code"** or **"Co-Authored-By"** in commits, PR descriptions
- Ask permission before pushing to remote

## Python

- Use `uv` for package management
- Always use virtual environments
- Dev install: `uv pip install -e ".[test]"`
- Run tests: `uv run pytest tests/ -q --cov=src/cicaddy_github`
- Type checking: `uv run ty check` (if available)
- Format: `pre-commit run ruff-format --files <changed-files>`

## Docker

- Build Docker image: `docker build -t cicaddy-action:test .`
- Test Docker image: `docker run --rm --entrypoint cicaddy cicaddy-action:test --version`

## Running Locally

Create an env file and use `uv run cicaddy run --env-file <file>`:

```bash
# AI Provider
AI_PROVIDER=gemini
AI_MODEL=gemini-3-flash-preview
GEMINI_API_KEY=<key>

# GitHub Configuration
GITHUB_TOKEN=<token>
GITHUB_REPOSITORY=owner/repo
GITHUB_EVENT_NAME=pull_request
GITHUB_PR_NUMBER=42

# Agent Settings
POST_PR_COMMENT=true
ENABLE_LOCAL_TOOLS=true
LOCAL_TOOLS_WORKING_DIR=.

LOG_LEVEL=INFO
```

Run with: `uv run cicaddy run --env-file .env.my-review`

## PR Review Workflow Security

- The PR review workflow uses `pull_request_target` so secrets are available for fork PRs
- Internal PRs (same repo) run automatically; fork PRs require the `safe-to-review` label
- The label is auto-removed on `synchronize` (new pushes from forks) to prevent TOCTOU bypasses
- The workflow never checks out or executes untrusted PR code — cicaddy fetches the diff via the GitHub API

## Release Checklist

- **Bump `version` in `pyproject.toml` BEFORE tagging** — the release workflow builds from the checked-out source, so the `pyproject.toml` version must match the git tag
- When bumping the version, also update all `cicaddy-action@vX.Y.Z` version references in `README.md` and skills to match the new version
- Run full test suite: `uv run pytest tests/ -q --cov=src/cicaddy_github`
- Create release with `gh release create v<version>`
- PyPI publish is automated via `.github/workflows/release.yml`
