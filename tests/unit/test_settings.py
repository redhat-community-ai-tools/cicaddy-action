"""Tests for cicaddy-github settings configuration."""

import os
from unittest.mock import patch


class TestSettingsValidation:
    """Test settings loading and validation."""

    def test_context_safety_factor_empty_string(self):
        """Empty string CONTEXT_SAFETY_FACTOR defaults to 0.85."""
        env = {
            "CONTEXT_SAFETY_FACTOR": "",
            "AI_PROVIDER": "gemini",
            "AI_MODEL": "gemini-2.5-flash",
            "MCP_SERVERS_CONFIG": "[]",
        }
        with patch.dict(os.environ, env, clear=False):
            from cicaddy_github.config.settings import load_settings

            settings = load_settings()
            assert settings.context_safety_factor == 0.85

    def test_context_safety_factor_valid_value(self):
        """Valid CONTEXT_SAFETY_FACTOR is accepted."""
        env = {
            "CONTEXT_SAFETY_FACTOR": "0.75",
            "AI_PROVIDER": "gemini",
            "AI_MODEL": "gemini-2.5-flash",
            "MCP_SERVERS_CONFIG": "[]",
        }
        with patch.dict(os.environ, env, clear=False):
            from cicaddy_github.config.settings import load_settings

            settings = load_settings()
            assert settings.context_safety_factor == 0.75

    def test_context_safety_factor_invalid_value(self):
        """Non-numeric CONTEXT_SAFETY_FACTOR falls back to 0.85."""
        env = {
            "CONTEXT_SAFETY_FACTOR": "invalid",
            "AI_PROVIDER": "gemini",
            "AI_MODEL": "gemini-2.5-flash",
            "MCP_SERVERS_CONFIG": "[]",
        }
        with patch.dict(os.environ, env, clear=False):
            from cicaddy_github.config.settings import load_settings

            settings = load_settings()
            assert settings.context_safety_factor == 0.85

    def test_context_safety_factor_out_of_range_low(self):
        """CONTEXT_SAFETY_FACTOR below 0.5 falls back to 0.85."""
        env = {
            "CONTEXT_SAFETY_FACTOR": "0.3",
            "AI_PROVIDER": "gemini",
            "AI_MODEL": "gemini-2.5-flash",
            "MCP_SERVERS_CONFIG": "[]",
        }
        with patch.dict(os.environ, env, clear=False):
            from cicaddy_github.config.settings import load_settings

            settings = load_settings()
            assert settings.context_safety_factor == 0.85

    def test_context_safety_factor_out_of_range_high(self):
        """CONTEXT_SAFETY_FACTOR above 0.97 falls back to 0.85."""
        env = {
            "CONTEXT_SAFETY_FACTOR": "1.5",
            "AI_PROVIDER": "gemini",
            "AI_MODEL": "gemini-2.5-flash",
            "MCP_SERVERS_CONFIG": "[]",
        }
        with patch.dict(os.environ, env, clear=False):
            from cicaddy_github.config.settings import load_settings

            settings = load_settings()
            assert settings.context_safety_factor == 0.85

    def test_context_safety_factor_not_set(self):
        """Missing CONTEXT_SAFETY_FACTOR env var uses default 0.85."""
        env = {
            "AI_PROVIDER": "gemini",
            "AI_MODEL": "gemini-2.5-flash",
            "MCP_SERVERS_CONFIG": "[]",
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("CONTEXT_SAFETY_FACTOR", None)
            from cicaddy_github.config.settings import load_settings

            settings = load_settings()
            assert settings.context_safety_factor == 0.85

    def test_max_execution_time_empty_string(self):
        """Empty string MAX_EXECUTION_TIME defaults to 600."""
        env = {
            "MAX_EXECUTION_TIME": "",
            "AI_PROVIDER": "gemini",
            "AI_MODEL": "gemini-2.5-flash",
            "MCP_SERVERS_CONFIG": "[]",
        }
        with patch.dict(os.environ, env, clear=False):
            from cicaddy_github.config.settings import load_settings

            settings = load_settings()
            assert settings.max_execution_time == 600

    def test_max_execution_time_valid_value(self):
        """Valid MAX_EXECUTION_TIME is accepted."""
        env = {
            "MAX_EXECUTION_TIME": "1200",
            "AI_PROVIDER": "gemini",
            "AI_MODEL": "gemini-2.5-flash",
            "MCP_SERVERS_CONFIG": "[]",
        }
        with patch.dict(os.environ, env, clear=False):
            from cicaddy_github.config.settings import load_settings

            settings = load_settings()
            assert settings.max_execution_time == 1200

    def test_github_token_loaded(self):
        """GITHUB_TOKEN is loaded into settings."""
        env = {
            "GITHUB_TOKEN": "ghp_test_token",
            "AI_PROVIDER": "gemini",
            "AI_MODEL": "gemini-2.5-flash",
            "MCP_SERVERS_CONFIG": "[]",
        }
        with patch.dict(os.environ, env, clear=False):
            from cicaddy_github.config.settings import load_settings

            settings = load_settings()
            assert settings.github_token == "ghp_test_token"

    def test_github_repository_loaded(self):
        """GITHUB_REPOSITORY is loaded into settings."""
        env = {
            "GITHUB_REPOSITORY": "owner/repo",
            "AI_PROVIDER": "gemini",
            "AI_MODEL": "gemini-2.5-flash",
            "MCP_SERVERS_CONFIG": "[]",
        }
        with patch.dict(os.environ, env, clear=False):
            from cicaddy_github.config.settings import load_settings

            settings = load_settings()
            assert settings.github_repository == "owner/repo"

    def test_post_pr_comment_default_false(self):
        """POST_PR_COMMENT defaults to False."""
        env = {
            "AI_PROVIDER": "gemini",
            "AI_MODEL": "gemini-2.5-flash",
            "MCP_SERVERS_CONFIG": "[]",
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("POST_PR_COMMENT", None)
            from cicaddy_github.config.settings import load_settings

            settings = load_settings()
            assert settings.post_pr_comment is False

    def test_post_pr_comment_true(self):
        """POST_PR_COMMENT=true sets field to True."""
        env = {
            "POST_PR_COMMENT": "true",
            "AI_PROVIDER": "gemini",
            "AI_MODEL": "gemini-2.5-flash",
            "MCP_SERVERS_CONFIG": "[]",
        }
        with patch.dict(os.environ, env, clear=False):
            from cicaddy_github.config.settings import load_settings

            settings = load_settings()
            assert settings.post_pr_comment is True

    def test_submit_review_default_false(self):
        """SUBMIT_REVIEW defaults to False."""
        env = {
            "AI_PROVIDER": "gemini",
            "AI_MODEL": "gemini-2.5-flash",
            "MCP_SERVERS_CONFIG": "[]",
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("SUBMIT_REVIEW", None)
            from cicaddy_github.config.settings import load_settings

            settings = load_settings()
            assert settings.submit_review is False

    def test_submit_review_true(self):
        """SUBMIT_REVIEW=true sets field to True."""
        env = {
            "SUBMIT_REVIEW": "true",
            "AI_PROVIDER": "gemini",
            "AI_MODEL": "gemini-2.5-flash",
            "MCP_SERVERS_CONFIG": "[]",
        }
        with patch.dict(os.environ, env, clear=False):
            from cicaddy_github.config.settings import load_settings

            settings = load_settings()
            assert settings.submit_review is True
