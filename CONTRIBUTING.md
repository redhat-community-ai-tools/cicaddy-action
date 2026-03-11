# Contributing to cicaddy-action

Thank you for your interest in contributing! This guide will help you get started.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/redhat-community-ai-tools/cicaddy-action.git
cd cicaddy-action

# Install with test dependencies
uv pip install -e ".[test]"

# Install pre-commit hooks
pre-commit install
```

## Running Tests

```bash
pytest tests/ -q --cov=src/cicaddy_github
```

## Linting

```bash
pre-commit run --all-files
```

## Submitting Changes

1. Fork the repository and create a feature branch
2. Make your changes with clear, focused commits
3. Ensure all tests pass and linters are clean
4. Submit a pull request with a clear description of the changes

## Reporting Issues

Please use [GitHub Issues](https://github.com/redhat-community-ai-tools/cicaddy-action/issues)
to report bugs or request features. Include:

- Steps to reproduce the issue
- Expected vs actual behavior
- Relevant logs or error messages

## Code Style

- Python 3.11+ with type hints
- Ruff for linting and formatting (line-length 100)
- Google-style docstrings
- Async methods for I/O operations

## License

By contributing, you agree that your contributions will be licensed under the
Apache-2.0 License.
