"""Tests for cicaddy-github plugin entry points."""

import os
from unittest.mock import patch


class TestRegisterAgents:
    """Test agent registration."""

    @patch("cicaddy.agent.factory.AgentFactory")
    def test_register_agents_registers_pr_agent(self, mock_factory):
        from cicaddy_github.plugin import register_agents

        register_agents()
        calls = mock_factory.register.call_args_list
        agent_names = [c[0][0] for c in calls]
        assert "github_pr" in agent_names

    @patch("cicaddy.agent.factory.AgentFactory")
    def test_register_agents_registers_task_agent(self, mock_factory):
        from cicaddy_github.plugin import register_agents

        register_agents()
        calls = mock_factory.register.call_args_list
        agent_names = [c[0][0] for c in calls]
        assert "github_task" in agent_names

    @patch("cicaddy.agent.factory.AgentFactory")
    def test_register_agents_registers_detector(self, mock_factory):
        from cicaddy_github.plugin import register_agents

        register_agents()
        mock_factory.register_detector.assert_called_once()
        _, kwargs = mock_factory.register_detector.call_args
        assert kwargs.get("priority") == 40


class TestGetCliArgs:
    """Test CLI argument mappings."""

    def test_get_cli_args_returns_list(self):
        from cicaddy_github.plugin import get_cli_args

        args = get_cli_args()
        assert isinstance(args, list)
        assert len(args) >= 2

    def test_get_cli_args_has_pr_number(self):
        from cicaddy_github.plugin import get_cli_args

        args = get_cli_args()
        cli_args = [a.cli_arg for a in args]
        assert "--pr-number" in cli_args

    def test_get_cli_args_has_github_repo(self):
        from cicaddy_github.plugin import get_cli_args

        args = get_cli_args()
        cli_args = [a.cli_arg for a in args]
        assert "--github-repo" in cli_args


class TestGetEnvVars:
    """Test environment variable listing."""

    def test_get_env_vars_returns_list(self):
        from cicaddy_github.plugin import get_env_vars

        env_vars = get_env_vars()
        assert isinstance(env_vars, list)

    def test_get_env_vars_contains_github_token(self):
        from cicaddy_github.plugin import get_env_vars

        env_vars = get_env_vars()
        assert "GITHUB_TOKEN" in env_vars

    def test_get_env_vars_contains_github_repository(self):
        from cicaddy_github.plugin import get_env_vars

        env_vars = get_env_vars()
        assert "GITHUB_REPOSITORY" in env_vars

    def test_get_env_vars_contains_all_required_vars(self):
        from cicaddy_github.plugin import get_env_vars

        env_vars = get_env_vars()
        expected = [
            "GITHUB_TOKEN",
            "GITHUB_REPOSITORY",
            "GITHUB_REF",
            "GITHUB_EVENT_NAME",
            "GITHUB_SHA",
            "GITHUB_RUN_ID",
        ]
        for var in expected:
            assert var in env_vars


class TestValidate:
    """Test configuration validation."""

    def test_validate_missing_token_for_pr_agent(self):
        from cicaddy_github.plugin import validate

        config = {"AGENT_TYPE": "github_pr"}
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GITHUB_TOKEN", None)
            errors, warnings = validate(config)
        assert any("GITHUB_TOKEN" in e for e in errors)

    def test_validate_token_present(self):
        from cicaddy_github.plugin import validate

        config = {"GITHUB_TOKEN": "ghp_test123"}
        errors, warnings = validate(config)
        assert not any("GITHUB_TOKEN" in e for e in errors)

    def test_validate_missing_repo_for_pr_agent(self):
        from cicaddy_github.plugin import validate

        config = {
            "AGENT_TYPE": "github_pr",
            "GITHUB_TOKEN": "ghp_test123",
        }
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GITHUB_REPOSITORY", None)
            errors, warnings = validate(config)
        assert any("GITHUB_REPOSITORY" in e for e in errors)

    def test_validate_no_errors_for_task_agent_without_token(self):
        from cicaddy_github.plugin import validate

        config = {"AGENT_TYPE": "github_task"}
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GITHUB_TOKEN", None)
            errors, warnings = validate(config)
        assert not any("GITHUB_TOKEN" in e for e in errors)
        assert any("GITHUB_TOKEN" in w for w in warnings)
