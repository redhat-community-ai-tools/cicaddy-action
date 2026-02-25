"""Tests for GitHub agent type detection."""

import os
from unittest.mock import MagicMock, patch


class TestDetectGitHubAgentType:
    """Test agent type detection from GITHUB_* env vars."""

    def test_pull_request_event_returns_github_pr(self):
        """GITHUB_EVENT_NAME=pull_request returns github_pr."""
        from cicaddy_github.github_integration.detector import _detect_github_agent_type

        settings = MagicMock()
        settings.github_pr_number = None
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "pull_request"}):
            result = _detect_github_agent_type(settings)
        assert result == "github_pr"

    def test_push_event_returns_none(self):
        """GITHUB_EVENT_NAME=push returns None (falls through to TaskAgent)."""
        from cicaddy_github.github_integration.detector import _detect_github_agent_type

        settings = MagicMock()
        settings.github_pr_number = None
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "push"}):
            result = _detect_github_agent_type(settings)
        assert result is None

    def test_schedule_event_returns_none(self):
        """GITHUB_EVENT_NAME=schedule returns None."""
        from cicaddy_github.github_integration.detector import _detect_github_agent_type

        settings = MagicMock()
        settings.github_pr_number = None
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule"}):
            result = _detect_github_agent_type(settings)
        assert result is None

    def test_workflow_dispatch_returns_none(self):
        """GITHUB_EVENT_NAME=workflow_dispatch returns None."""
        from cicaddy_github.github_integration.detector import _detect_github_agent_type

        settings = MagicMock()
        settings.github_pr_number = None
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_dispatch"}):
            result = _detect_github_agent_type(settings)
        assert result is None

    def test_pr_number_in_settings_returns_github_pr(self):
        """PR number in settings returns github_pr as fallback."""
        from cicaddy_github.github_integration.detector import _detect_github_agent_type

        settings = MagicMock()
        settings.github_pr_number = "42"
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "push"}):
            result = _detect_github_agent_type(settings)
        assert result == "github_pr"

    def test_no_event_name_returns_none(self):
        """Missing GITHUB_EVENT_NAME returns None."""
        from cicaddy_github.github_integration.detector import _detect_github_agent_type

        settings = MagicMock()
        settings.github_pr_number = None
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GITHUB_EVENT_NAME", None)
            result = _detect_github_agent_type(settings)
        assert result is None
