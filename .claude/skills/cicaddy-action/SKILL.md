---
name: cicaddy-action
description: >
  Use this skill when working with cicaddy-action, the GitHub Action that wraps
  cicaddy for running AI agent tasks in GitHub Actions workflows. Covers the
  action inputs, Docker entrypoint, plugin architecture, task definitions, and
  local development.
---

# cicaddy-action

GitHub Action that wraps [cicaddy](https://github.com/waynesun09/cicaddy)
for running AI agent tasks in GitHub Actions workflows. The `cicaddy-github`
plugin extends cicaddy with GitHub-specific agents, tools, and configuration.

## Working Directory

- **Repository root**: `cicaddy-action/` (project root)
- **Plugin source**: `src/cicaddy_github/`
- **Task definitions**: `tasks/`
- **GitHub workflows**: `.github/workflows/`
- **Docker files**: `Dockerfile`, `entrypoint.sh`
- **Action definition**: `action.yml`

## Project Structure

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
  .github/workflows/
    ci.yml                    # Lint, test (3.11-3.13), docker build
    pr-review.yml             # AI code review on PRs (uses ./action)
    changelog.yml             # Changelog report on releases
    release.yml               # PyPI publish
```

## Key Commands

```bash
# Install with test dependencies
uv pip install -e ".[test]"

# Run tests with coverage
pytest tests/ -q --cov=src/cicaddy_github

# Run all linters (pre-commit)
pre-commit run --all-files

# Build Docker image
docker build -t cicaddy-action:test .

# Test Docker image
docker run --rm --entrypoint cicaddy cicaddy-action:test --version
```

## GitHub Secrets

AI API keys must be configured in GitHub repository settings
(Settings > Secrets and variables > Actions). Two approaches work:

**Option 1: Generic secret via `ai_api_key` input (recommended)**

Set `AI_API_KEY` as a GitHub secret. The entrypoint maps it to the correct
provider-specific env var (`GEMINI_API_KEY`, `OPENAI_API_KEY`, or
`ANTHROPIC_API_KEY`) based on the `ai_provider` input.

```yaml
with:
  ai_provider: gemini
  ai_api_key: ${{ secrets.AI_API_KEY }}
```

**Option 2: Provider-specific secret via `env:`**

Set the provider-specific secret directly (e.g. `GEMINI_API_KEY`) and pass
it as an environment variable. Cicaddy reads these env vars directly.

```yaml
with:
  ai_provider: gemini
env:
  GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
```

| Secret | Required | Description |
|--------|----------|-------------|
| `AI_API_KEY` | Yes* | Generic AI provider API key (used via `ai_api_key` input) |
| `GEMINI_API_KEY` | Yes* | Gemini API key (alternative, passed via `env:`) |
| `OPENAI_API_KEY` | Yes* | OpenAI API key (alternative, passed via `env:`) |
| `ANTHROPIC_API_KEY` | Yes* | Anthropic API key (alternative, passed via `env:`) |
| `CONTEXT7_API_KEY` | No | API key for Context7 MCP server (optional) |

*One of `AI_API_KEY` or the provider-specific key is required.

`GITHUB_TOKEN` is provided automatically by GitHub Actions.

## Action Inputs

All inputs use **underscores** (not hyphens) so GitHub Actions Docker containers
can reference them as bash variables (`INPUT_AI_PROVIDER`, `INPUT_AI_API_KEY`, etc.).

| Input | Required | Description |
|-------|----------|-------------|
| `ai_provider` | Yes | `gemini`, `openai`, `claude` |
| `ai_model` | Yes | Model identifier |
| `ai_api_key` | Yes* | AI provider API key (mapped to provider-specific env var) |
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
3. Resolves `AI_TASK_FILE` and `REPORT_TEMPLATE` to absolute paths (required
   because step 5 changes the working directory)
4. Extracts `GITHUB_PR_NUMBER` from `GITHUB_REF` (`refs/pull/<N>/merge`)
5. Creates `.cicaddy/` subdirectory and `cd`s into it (cicaddy writes reports
   to `../` relative to cwd; this ensures `../` resolves to the writable workspace)
6. Runs `cicaddy run`

### Known Pitfalls

- **Relative paths break after `cd .cicaddy/`**: Any file path input (task file,
  report template) must be resolved to an absolute path before the `cd`. The
  entrypoint handles this with a `_to_abs` helper. If new file-path inputs are
  added, they must also use this helper.
- **Secrets in workflow `run:` blocks**: Never use `${{ secrets.* }}` directly
  in `run:` shell blocks. Pass secrets via `env:` to avoid literal interpolation
  in logs. See `.github/workflows/pr-review.yml` for the correct pattern.

## Plugin Architecture

The `cicaddy-github` package registers with cicaddy via `pyproject.toml` entry points:

```toml
[project.entry-points."cicaddy.agents"]
github = "cicaddy_github.plugin:register_agents"

[project.entry-points."cicaddy.settings_loader"]
github = "cicaddy_github.config.settings:load_settings"

[project.entry-points."cicaddy.cli_args"]
github = "cicaddy_github.plugin:get_cli_args"

[project.entry-points."cicaddy.env_vars"]
github = "cicaddy_github.plugin:get_env_vars"

[project.entry-points."cicaddy.validators"]
github = "cicaddy_github.plugin:validate"
```

### Registered Agents

| Type | Class | Triggered by |
|------|-------|--------------|
| `github_pr` | `GitHubPRAgent` | `GITHUB_EVENT_NAME=pull_request` + `GITHUB_PR_NUMBER` |
| `github_task` | `GitHubTaskAgent` | `GITHUB_EVENT_NAME` present but not a PR |

### Settings

`Settings` extends `CoreSettings` with GitHub-specific fields:

- `github_token`, `github_repository`, `github_ref`, `github_event_name`
- `github_sha`, `github_run_id`, `github_pr_number`
- `post_pr_comment` (bool)

All loaded from environment variables via `load_settings()`.

## DSPy Task Files

Task YAML files define analysis prompts. Inputs use `{{VAR}}` placeholders
resolved from environment variables.

```yaml
name: pr_code_review
type: code_review
version: "1.0"

persona: >
  expert code reviewer

tools:
  servers:
    - local
  required_tools:
    - read_file
    - glob_files

output_format: markdown

context: |
  Review the PR diff for the repository...
```

## Workflow Usage

```yaml
- uses: redhat-community-ai-tools/cicaddy-action@v0.3.0
  with:
    ai_provider: gemini
    ai_model: gemini-3-flash-preview
    ai_api_key: ${{ secrets.AI_API_KEY }}
    task_file: tasks/pr_review.yml
    post_pr_comment: 'true'
```

## Running Locally

Cicaddy can run locally to review PRs without GitHub Actions. Create an env
file and use `uv run cicaddy run --env-file <file>`.

### Env File Template (PR Review)

```bash
# AI Provider
AI_PROVIDER=gemini
AI_MODEL=gemini-3-flash-preview
GEMINI_API_KEY=<key>

# GitHub Configuration
GITHUB_TOKEN=<token>            # gh auth token
GITHUB_REPOSITORY=owner/repo
GITHUB_EVENT_NAME=pull_request
GITHUB_PR_NUMBER=42

# Agent Settings
POST_PR_COMMENT=true
ENABLE_LOCAL_TOOLS=true
LOCAL_TOOLS_WORKING_DIR=.

# Optional: MCP servers
MCP_SERVERS_CONFIG=[{"name": "context7", "protocol": "http", "endpoint": "https://mcp.context7.com/mcp", "headers": {"CONTEXT7_API_KEY": "<key>"}}]

LOG_LEVEL=INFO
```

### Key Commands

```bash
# Install plugin in editable mode (uses live code)
uv pip install -e ".[test]"

# Run a PR review
uv run cicaddy run --env-file .env.my-review

# Validate configuration
uv run cicaddy validate --env-file .env.my-review
```

### Agent Type Detection

The agent type is auto-detected by `_detect_github_agent_type` in
`src/cicaddy_github/github_integration/detector.py` (registered at priority 40):
- `GITHUB_EVENT_NAME=pull_request` → `github_pr`
- `GITHUB_PR_NUMBER` set (fallback) → `github_pr`
- Otherwise → falls through to core detectors

### Additional Env Vars

- `AI_TASK_FILE`: Path to DSPy YAML task file for custom workflows
- `GIT_DIFF_CONTEXT_LINES`: Number of context lines in diffs (default: 10)

### MCP Server Config Format

JSON array. Each server object has:
- `name` (string): Server identifier
- `protocol` (string): `http`, `sse`, `stdio`, or `websocket`
- `endpoint` (string): Server URL
- `headers` (object, optional): HTTP headers (e.g. API keys)

### Notes

- **Never commit env files with secrets.** Use `.env.*` pattern (already in `.gitignore`)
- `POST_PR_COMMENT=true` requires a token with write access to pull requests
  (`repo` scope includes this; for fine-grained tokens, enable "Pull requests: Write")
- The `github_pr` agent updates its PR comment in-place on re-runs
- Use `gh auth token` to generate a GitHub token quickly

## Code Style

- Python 3.11+ with type hints
- Ruff for linting and formatting (line-length 100)
- Google-style docstrings
- Async methods for I/O operations
- `@tool` decorator for local tool definitions
- pytest with pytest-asyncio for testing
