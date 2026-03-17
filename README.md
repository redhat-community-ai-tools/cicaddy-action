# cicaddy-action

GitHub Action that wraps [cicaddy](https://github.com/waynesun09/cicaddy) for running AI agent tasks in GitHub Actions workflows.

## Features

- **AI-powered PR reviews** with optional Context7 MCP for up-to-date library documentation
- **Changelog report generation** from git tag diffs and release notes
- **Multiple AI providers**: Gemini, OpenAI, Claude
- **Secret redaction** via detect-secrets for safe public outputs
- **DSPy YAML task definitions** for customizable analysis workflows

## Quick Start

### AI PR Review

This example uses the `pull_request` trigger, which works for in-repo PRs
(branches pushed to the same repository). For fork PR support, see
`.github/workflows/pr-review.yml` which uses `pull_request_target` with
a `safe-to-review` label gate.

```yaml
name: PR Review

on:
  pull_request:
    types: [opened, synchronize]

permissions:
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: redhat-community-ai-tools/cicaddy-action@v0.3.1
        with:
          ai_provider: gemini
          ai_model: gemini-3-flash-preview
          ai_api_key: ${{ secrets.AI_API_KEY }}
          task_file: tasks/pr_review.yml
          post_pr_comment: 'true'
```

### Changelog Report on Release

```yaml
name: Generate Changelog

on:
  release:
    types: [published]

jobs:
  changelog:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: redhat-community-ai-tools/cicaddy-action@v0.3.1
        with:
          ai_provider: gemini
          ai_model: gemini-3-flash-preview
          ai_api_key: ${{ secrets.AI_API_KEY }}
          task_file: tasks/changelog_report.yml
```

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `ai_provider` | Yes | AI provider: `gemini`, `openai`, `claude` |
| `ai_model` | Yes | Model identifier |
| `ai_api_key` | Yes | AI provider API key |
| `task_file` | No | Path to DSPy YAML task file |
| `task_prompt` | No | Inline task prompt (alternative to task_file) |
| `report_template` | No | Path to custom HTML report template |
| `mcp_servers_config` | No | JSON array of MCP server configs |
| `slack_webhook_url` | No | Slack webhook URL for notifications |
| `post_pr_comment` | No | Post results as PR comment (default: `false`) |
| `github_token` | No | GitHub token (default: `${{ github.token }}`) |

## Outputs

| Output | Description |
|--------|-------------|
| `report_html` | Path to generated HTML report |
| `report_json` | Path to JSON analysis result |
| `summary` | Brief text summary |

## Custom Tasks

Create DSPy YAML task files to define custom analysis workflows. See `tasks/changelog_report.yml` and `tasks/pr_review.yml` for examples.

## Local Development

### Running cicaddy locally

You can run cicaddy locally to review PRs without GitHub Actions. This is useful
for testing changes to the plugin or reviewing PRs in other repositories.

**1. Install the plugin in editable mode:**

```bash
uv pip install -e ".[test]"
```

**2. Create an env file** (e.g. `.env.my-review`):

```bash
# AI Provider
AI_PROVIDER=gemini
AI_MODEL=gemini-3-flash-preview
GEMINI_API_KEY=<your-gemini-api-key>

# GitHub Configuration
GITHUB_TOKEN=<your-github-token>
GITHUB_REPOSITORY=owner/repo
GITHUB_EVENT_NAME=pull_request
GITHUB_PR_NUMBER=42

# Agent Settings
POST_PR_COMMENT=true
ENABLE_LOCAL_TOOLS=true
LOCAL_TOOLS_WORKING_DIR=.

# Optional: MCP servers (e.g. Context7 for library docs)
MCP_SERVERS_CONFIG=[{"name": "context7", "protocol": "http", "endpoint": "https://mcp.context7.com/mcp", "headers": {"CONTEXT7_API_KEY": "<your-key>"}}]

# Logging
LOG_LEVEL=INFO
```

**3. Generate a GitHub token:**

The token needs `repo` scope for private repos or `public_repo` for public repos.
When `POST_PR_COMMENT=true`, the token must also have write access to pull requests
(the `repo` scope includes this; for fine-grained tokens, enable "Pull requests: Write").

```bash
# Use your existing gh CLI token
gh auth token
```

> **Warning:** Never commit env files containing secrets. The `.env.*` pattern is
> already in `.gitignore`, but if you use a different naming convention (e.g. `.env`),
> make sure it is also ignored.

**4. Run the review:**

```bash
uv run cicaddy run --env-file .env.my-review
```

The agent auto-detects `github_pr` type from the env vars, fetches the PR diff,
runs AI analysis, and optionally posts a comment on the PR.

**5. Validate configuration** (optional):

```bash
uv run cicaddy validate --env-file .env.my-review
```

### Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `AI_PROVIDER` | Yes | `gemini`, `openai`, or `claude` |
| `AI_MODEL` | Yes | Model identifier (e.g. `gemini-3-flash-preview`) |
| `GEMINI_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Yes | API key matching the provider |
| `GITHUB_TOKEN` | Yes | GitHub personal access token |
| `GITHUB_REPOSITORY` | Yes | Target repo in `owner/repo` format |
| `GITHUB_EVENT_NAME` | No | Set to `pull_request` for auto-detection (optional if `GITHUB_PR_NUMBER` is set) |
| `GITHUB_PR_NUMBER` | Yes | PR number to review |
| `POST_PR_COMMENT` | No | Post results as PR comment (`true`/`false`) |
| `AI_TASK_FILE` | No | Path to DSPy YAML task file for custom workflows |
| `GIT_DIFF_CONTEXT_LINES` | No | Number of context lines in diffs (default: `10`) |
| `ENABLE_LOCAL_TOOLS` | No | Enable local git tools (`true`/`false`) |
| `LOCAL_TOOLS_WORKING_DIR` | No | Working directory for local tools |
| `MCP_SERVERS_CONFIG` | No | JSON array of MCP server configurations |
| `LOG_LEVEL` | No | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

### Build & Test

```bash
# Run tests with coverage
pytest tests/ -q --cov=src/cicaddy_github

# Run all linters (pre-commit)
pre-commit run --all-files

# Build Docker image
docker build -t cicaddy-action:test .
```

## License

Apache-2.0
