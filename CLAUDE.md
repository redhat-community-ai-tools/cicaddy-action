# cicaddy-action Development Guidelines

## Project Overview
GitHub Action that wraps cicaddy for running AI agent tasks in GitHub Actions workflows. The `cicaddy-github` plugin extends cicaddy with GitHub-specific agents, tools, and configuration.

## Architecture
- **Plugin system**: Uses cicaddy's entry_points for agent registration, settings loading, CLI args, env vars, and validation
- **Local tools**: Git operations defined with `@tool` decorator, registered via `ToolRegistry` — no MCP server needed
- **Container-based action**: Dockerfile + entrypoint.sh maps GitHub Action inputs to cicaddy env vars

## Key Commands
- `uv pip install -e ".[test]"` — Install with test dependencies
- `pytest tests/ -q --cov=src/cicaddy_github` — Run tests with coverage
- `pre-commit run --all-files` — Run all linters
- `docker build -t cicaddy-action:test .` — Build Docker image

## Code Style
- Python 3.11+ with type hints
- Ruff for linting and formatting (line-length 100)
- Google-style docstrings
- Async methods for I/O operations
- Follow cicaddy plugin patterns from gitlab-agent-task

## Testing
- Use pytest with pytest-asyncio
- Mock external APIs (PyGithub, subprocess calls)
- Test files in `tests/unit/`
- Fixtures in `tests/conftest.py`

## Release Checklist
- When bumping the version for a release, also update all `cicaddy-action@vX.Y.Z` version references in `README.md` and `.claude/skills/cicaddy-action/SKILL.md` to match the new version.

## PR Review Workflow Security
- The PR review workflow uses `pull_request_target` so secrets are available for fork PRs.
- Internal PRs (same repo) run automatically; fork PRs require the `safe-to-review` label.
- The label is auto-removed on `synchronize` (new pushes from forks) to prevent TOCTOU bypasses.
- The workflow never checks out or executes untrusted PR code — cicaddy fetches the diff via the GitHub API.

## Reference Repos
- [cicaddy core](https://github.com/waynesun09/cicaddy)
