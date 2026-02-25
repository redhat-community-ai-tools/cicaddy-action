"""Shared test fixtures for cicaddy-github tests."""

import asyncio

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Set minimal environment variables for testing."""
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("JSON_LOGS", "false")
    monkeypatch.setenv("SSL_VERIFY", "false")
    monkeypatch.setenv("MCP_SERVERS_CONFIG", "[]")
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("AI_MODEL", "gemini-2.5-flash")


@pytest.fixture
def github_env_vars(monkeypatch):
    """Set GitHub Actions environment variables for testing."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_123456789")
    monkeypatch.setenv("GITHUB_REPOSITORY", "redhat-community-ai-tools/cicaddy-action")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("GITHUB_SHA", "abc123def456")
    monkeypatch.setenv("GITHUB_RUN_ID", "12345")


@pytest.fixture
def pr_env_vars(monkeypatch, github_env_vars):
    """Set PR-specific environment variables for testing."""
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_PR_NUMBER", "42")
