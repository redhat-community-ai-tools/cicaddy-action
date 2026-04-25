# cicaddy-action

GitHub Action that wraps [cicaddy](https://github.com/waynesun09/cicaddy) for running AI agent tasks in GitHub Actions workflows.

## Features

- **AI-powered PR reviews** with optional Context7 MCP for up-to-date library documentation
- **Sub-agent delegation** for parallel specialized reviews (security, architecture, performance, etc.)
- **Go dependency impact analysis** for Go dependency update PRs with risk classification
- **Changelog report generation** from git tag diffs and release notes
- **Multiple AI providers**: Gemini, OpenAI, Claude, Claude via Vertex AI
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
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0

      - uses: redhat-community-ai-tools/cicaddy-action@main
        with:
          ai_provider: gemini
          ai_model: gemini-3-flash-preview
          ai_api_key: ${{ secrets.AI_API_KEY }}
          task_file: tasks/pr_review.yml
          post_pr_comment: 'true'
        env:
          DELEGATION_MODE: auto
```

> **Sub-Agent Delegation**: When `DELEGATION_MODE` is set to `auto`, the agent uses AI-powered triage to analyze the PR diff and spawns specialized sub-agents in parallel (e.g., code quality, security, performance). Each sub-agent runs with a focused scope and reduced token budget, and their results are aggregated into a single unified review. This produces deeper, more structured reviews compared to single-agent mode. Set `DELEGATION_MODE` to `none` to use a single agent instead. See [docs/delegation.md](docs/delegation.md) for details.

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
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0

      - uses: redhat-community-ai-tools/cicaddy-action@main
        with:
          ai_provider: gemini
          ai_model: gemini-3-flash-preview
          ai_api_key: ${{ secrets.AI_API_KEY }}
          task_file: tasks/changelog_report.yml
```

### Go Dependency Impact Analysis

Analyze Go dependency update PRs (e.g. from Renovate or Dependabot) with
AI-assisted risk classification. The agent collects dependency diffs,
usage analysis (via `go mod why`/`go mod graph`), upstream changelogs,
and security advisories, then posts a structured impact assessment as a
PR comment.

```yaml
name: Go Dependency Impact Analysis

on:
  pull_request:
    paths:
      - 'go.mod'
      - 'go.sum'

permissions:
  contents: read
  pull-requests: write

jobs:
  dep-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-go@v6
        with:
          go-version: '1.22'
      - uses: redhat-community-ai-tools/cicaddy-action@main
        with:
          ai_provider: gemini
          ai_model: gemini-3-flash-preview
          ai_api_key: ${{ secrets.AI_API_KEY }}
          task_file: tasks/go_dep_impact_review.yml
          post_pr_comment: 'true'
          run_govulncheck: 'true'
        env:
          AGENT_TASKS: go_dep_review
```

The `AGENT_TASKS: go_dep_review` env var activates the Go dependency review
agent instead of the default PR code review agent. The `run_govulncheck`
input enables vulnerability reachability analysis (requires Go and
govulncheck installed in the runner).

See [docs/providers.md](docs/providers.md) for provider-specific configuration including Claude via Vertex AI (GCP), OpenAI, and Anthropic API setup.

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `ai_provider` | Yes | AI provider: `gemini`, `openai`, `claude`, `anthropic-vertex` |
| `ai_model` | Yes | Model identifier |
| `ai_api_key` | No | AI provider API key (not needed for `anthropic-vertex`) |
| `vertex_project_id` | No | GCP project ID (required for `anthropic-vertex`) |
| `google_cloud_location` | No | Vertex AI location (default: `global`) |
| `task_file` | No | Path to DSPy YAML task file |
| `task_prompt` | No | Inline task prompt (alternative to task_file) |
| `report_template` | No | Path to custom HTML report template |
| `mcp_servers_config` | No | JSON array of MCP server configs |
| `slack_webhook_url` | No | Slack webhook URL for notifications |
| `post_pr_comment` | No | Post results as PR comment (default: `false`) |
| `submit_review` | No | Submit formal PR review with APPROVE/REQUEST_CHANGES (default: `false`) |
| `run_govulncheck` | No | Run govulncheck for vulnerability reachability analysis (default: `false`) |
| `dep_review_severity_threshold` | No | Minimum semver bump to analyze: `minor` or `major` (default: `minor`) |
| `delegation_mode` | No | Enable AI-powered sub-agent delegation: `none` (default) or `auto` |
| `max_sub_agents` | No | Maximum concurrent sub-agents, 1-10 (default: `3`) |
| `github_token` | No | GitHub token (default: `${{ github.token }}`) |

## Outputs

| Output | Description |
|--------|-------------|
| `report_html` | Path to generated HTML report |
| `report_json` | Path to JSON analysis result |
| `summary` | Brief text summary |

## Custom Tasks

Create DSPy YAML task files to define custom analysis workflows. See `tasks/` for examples:
- `tasks/pr_review.yml` — AI code review
- `tasks/changelog_report.yml` — Changelog generation
- `tasks/go_dep_impact_review.yml` — Go dependency impact analysis

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
| `AI_PROVIDER` | Yes | `gemini`, `openai`, `claude`, or `anthropic-vertex` |
| `AI_MODEL` | Yes | Model identifier (e.g. `gemini-3-flash-preview`) |
| `GEMINI_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Yes* | API key matching the provider (*not needed for `anthropic-vertex`) |
| `ANTHROPIC_VERTEX_PROJECT_ID` | No | GCP project ID (required for `anthropic-vertex`) |
| `GOOGLE_CLOUD_LOCATION` | No | Vertex AI location (default: `global`) |
| `GITHUB_TOKEN` | Yes | GitHub personal access token |
| `GITHUB_REPOSITORY` | Yes | Target repo in `owner/repo` format |
| `GITHUB_EVENT_NAME` | No | Set to `pull_request` for auto-detection (optional if `GITHUB_PR_NUMBER` is set) |
| `GITHUB_PR_NUMBER` | Yes | PR number to review |
| `POST_PR_COMMENT` | No | Post results as PR comment (`true`/`false`) |
| `AGENT_TASKS` | No | Agent task type (e.g. `go_dep_review` for Go dependency analysis) |
| `DELEGATION_MODE` | No | `auto` for AI-powered sub-agent delegation, `none` for single-agent (default: `none`) |
| `MAX_SUB_AGENTS` | No | Max concurrent sub-agents for delegation, 1-10 (default: `3`) |
| `SUB_AGENT_MAX_ITERS` | No | Max iterations per sub-agent, 1-15 (default: `5`) |
| `AI_TASK_FILE` | No | Path to DSPy YAML task file for custom workflows |
| `RUN_GOVULNCHECK` | No | Run govulncheck for reachability analysis (`true`/`false`) |
| `DELEGATION_MODE` | No | `none` or `auto` for sub-agent delegation |
| `MAX_SUB_AGENTS` | No | Maximum concurrent sub-agents (default: `3`) |
| `SUB_AGENT_MAX_ITERS` | No | Max iterations per sub-agent (default: `10`) |
| `DELEGATION_AGENTS_DIR` | No | Custom agent YAML directory (default: `.agents/delegation`) |
| `DELEGATION_AGENTS` | No | JSON config for inline custom sub-agents |
| `TRIAGE_PROMPT` | No | Custom triage instructions |
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
