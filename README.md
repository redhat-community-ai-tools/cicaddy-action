# cicaddy-action

GitHub Action that wraps [cicaddy](https://github.com/redhat-community-ai-tools/cicaddy) for running AI agent tasks in GitHub Actions workflows.

## Features

- **AI-powered PR reviews** with optional Context7 MCP for up-to-date library documentation
- **Changelog report generation** from git tag diffs and release notes
- **Multiple AI providers**: Gemini, OpenAI, Claude
- **Secret redaction** via detect-secrets for safe public outputs
- **DSPy YAML task definitions** for customizable analysis workflows

## Quick Start

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

      - uses: redhat-community-ai-tools/cicaddy-action@v0
        with:
          ai_provider: gemini
          ai_model: gemini-2.5-flash
          ai_api_key: ${{ secrets.AI_API_KEY }}
          task_file: tasks/changelog_report.yml
```

### AI PR Review

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

      - uses: redhat-community-ai-tools/cicaddy-action@v0
        with:
          ai_provider: gemini
          ai_model: gemini-3-flash-preview
          ai_api_key: ${{ secrets.AI_API_KEY }}
          task_file: tasks/pr_review.yml
          post_pr_comment: 'true'
          github_token: ${{ secrets.GITHUB_TOKEN }}
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

## Development

```bash
# Install
uv pip install -e ".[test]"

# Test
pytest tests/ -q --cov=src/cicaddy_github

# Lint
pre-commit run --all-files

# Docker
docker build -t cicaddy-action:test .
```

## License

Apache-2.0
