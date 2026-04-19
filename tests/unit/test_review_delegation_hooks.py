"""Tests for review agent delegation hook forwarding to cicaddy core."""

from unittest.mock import MagicMock

import pytest
from cicaddy.delegation.registry import SubAgentSpec
from cicaddy.delegation.triage import DelegationEntry, DelegationPlan

from cicaddy_github.github_integration.agents import (
    GitHubGoDepReviewAgent,
    GitHubPRAgent,
)

# _post_process_plan exists in cicaddy core >= 0.9.0 (PR #50).
# CI may install an older release; skip tests that depend on it.
_has_post_process = hasattr(
    __import__("cicaddy.agent.base_review_agent", fromlist=["BaseReviewAgent"]).BaseReviewAgent,
    "_post_process_plan",
)
_skip_no_post_process = pytest.mark.skipif(
    not _has_post_process,
    reason="cicaddy core missing _post_process_plan (needs >= 0.9.0)",
)


def _make_pr_agent():
    """Create a minimal GitHubPRAgent with mocked settings."""
    settings = MagicMock()
    settings.github_pr_number = "123"
    agent = GitHubPRAgent.__new__(GitHubPRAgent)
    agent.settings = settings
    agent.pr_number = "123"
    return agent


def _make_dep_review_agent():
    """Create a minimal GitHubGoDepReviewAgent with mocked settings."""
    settings = MagicMock()
    agent = GitHubGoDepReviewAgent.__new__(GitHubGoDepReviewAgent)
    agent.settings = settings
    agent.pr_number = "456"
    return agent


class TestPRAgentDelegationHooks:
    """Verify GitHubPRAgent delegation hooks forward to cicaddy core."""

    def test_get_agent_type_returns_review(self):
        agent = _make_pr_agent()
        assert agent._get_agent_type() == "review"

    def test_get_delegation_context_extracts_diff(self):
        agent = _make_pr_agent()
        context = {
            "diff": ("diff --git a/main.go b/main.go\n+import fmt\n"),
            "diff_lines": 2,
            "analysis_type": "pull_request",
            "pull_request": {"title": "Fix bug"},
        }
        result = agent._get_delegation_context(context)
        assert "diff" in result
        assert result["changed_files"] == ["main.go"]
        assert result["analysis_type"] == "pull_request"

    @_skip_no_post_process
    def test_post_process_plan_injects_general_reviewer(self):
        agent = _make_pr_agent()
        plan = DelegationPlan(
            entries=[
                DelegationEntry(
                    agent_name="security-reviewer",
                    categories=["security"],
                    rationale="test",
                    priority=10,
                )
            ]
        )
        registry = {
            "security-reviewer": SubAgentSpec(
                name="security-reviewer",
                persona="sec",
                description="Security review",
                categories=["security"],
                priority=10,
                agent_type="review",
            ),
            "general-reviewer": SubAgentSpec(
                name="general-reviewer",
                persona="eng",
                description="General review",
                categories=["code_quality"],
                priority=100,
                agent_type="review",
            ),
        }

        result = agent._post_process_plan(plan, registry)
        names = [e.agent_name for e in result.entries]
        assert "general-reviewer" in names
        assert len(result.entries) == 2

    @_skip_no_post_process
    def test_post_process_plan_no_duplicate(self):
        agent = _make_pr_agent()
        plan = DelegationPlan(
            entries=[
                DelegationEntry(
                    agent_name="general-reviewer",
                    categories=["code_quality"],
                    rationale="test",
                    priority=100,
                )
            ]
        )
        registry = {
            "general-reviewer": SubAgentSpec(
                name="general-reviewer",
                persona="eng",
                description="General review",
                categories=["code_quality"],
                priority=100,
                agent_type="review",
            ),
        }

        result = agent._post_process_plan(plan, registry)
        assert len(result.entries) == 1


class TestGoDepReviewAgentDelegationHooks:
    """Verify GitHubGoDepReviewAgent delegation hooks forward to cicaddy core."""

    def test_get_agent_type_returns_review(self):
        agent = _make_dep_review_agent()
        assert agent._get_agent_type() == "review"

    def test_get_delegation_context_extracts_diff(self):
        agent = _make_dep_review_agent()
        context = {
            "diff": ("diff --git a/go.mod b/go.mod\n+require example.com/pkg v1.2.0\n"),
            "diff_lines": 2,
            "analysis_type": "go_dependency_review",
        }
        result = agent._get_delegation_context(context)
        assert result["changed_files"] == ["go.mod"]
        assert result["analysis_type"] == "go_dependency_review"
