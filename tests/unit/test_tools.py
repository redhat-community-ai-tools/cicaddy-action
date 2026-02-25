"""Tests for local git tools."""

import subprocess
from unittest.mock import MagicMock, patch

from cicaddy_github.github_integration.tools import (
    get_all_tools,
    get_commit_log,
    get_diff_stat,
    get_recent_tags,
    get_release_notes,
    get_tag_diff,
)


class TestGetRecentTags:
    """Test get_recent_tags tool."""

    @patch("cicaddy_github.github_integration.tools._run_git")
    def test_returns_tags(self, mock_git):
        mock_git.return_value = "v0.3.0\nv0.2.0\nv0.1.0"
        result = get_recent_tags(limit=3)
        assert "v0.3.0" in result
        assert "v0.2.0" in result

    @patch("cicaddy_github.github_integration.tools._run_git")
    def test_no_tags_found(self, mock_git):
        mock_git.return_value = ""
        result = get_recent_tags()
        assert "No tags found" in result

    @patch("cicaddy_github.github_integration.tools._run_git")
    def test_git_error(self, mock_git):
        mock_git.side_effect = subprocess.CalledProcessError(1, "git", stderr="fatal: error")
        result = get_recent_tags()
        assert "Error" in result


class TestGetTagDiff:
    """Test get_tag_diff tool."""

    @patch("cicaddy_github.github_integration.tools._run_git")
    def test_returns_diff(self, mock_git):
        mock_git.return_value = "abc123 feat: new feature\ndef456 fix: bug"
        result = get_tag_diff(from_tag="v0.1.0", to_tag="v0.2.0")
        assert "feat: new feature" in result

    @patch("cicaddy_github.github_integration.tools._run_git")
    def test_no_commits(self, mock_git):
        mock_git.return_value = ""
        result = get_tag_diff(from_tag="v0.1.0", to_tag="v0.1.0")
        assert "No commits found" in result

    @patch("cicaddy_github.github_integration.tools._run_git")
    def test_default_to_tag_is_head(self, mock_git):
        mock_git.return_value = "abc123 commit"
        get_tag_diff(from_tag="v0.1.0")
        mock_git.assert_called_once_with(["log", "v0.1.0..HEAD", "--oneline", "--no-merges"])


class TestGetDiffStat:
    """Test get_diff_stat tool."""

    @patch("cicaddy_github.github_integration.tools._run_git")
    def test_returns_stat(self, mock_git):
        mock_git.return_value = " src/main.py | 10 ++++---\n 1 file changed"
        result = get_diff_stat(from_tag="v0.1.0")
        assert "src/main.py" in result

    @patch("cicaddy_github.github_integration.tools._run_git")
    def test_no_changes(self, mock_git):
        mock_git.return_value = ""
        result = get_diff_stat(from_tag="v0.1.0")
        assert "No file changes" in result


class TestGetReleaseNotes:
    """Test get_release_notes tool."""

    @patch.dict(
        "os.environ",
        {
            "GITHUB_TOKEN": "test-token",
            "GITHUB_REPOSITORY": "owner/repo",
        },
    )
    @patch("github.Github")
    def test_returns_notes(self, mock_gh_cls):
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_release = MagicMock()
        mock_release.body = "Release notes content"
        mock_repo.get_release.return_value = mock_release
        mock_gh.get_repo.return_value = mock_repo
        mock_gh_cls.return_value = mock_gh

        result = get_release_notes(tag="v0.1.0")
        assert "Release notes content" in result

    @patch.dict("os.environ", {}, clear=False)
    def test_missing_env_vars(self):
        import os

        os.environ.pop("GITHUB_TOKEN", None)
        os.environ.pop("GITHUB_REPOSITORY", None)
        result = get_release_notes(tag="v0.1.0")
        assert "must be set" in result


class TestGetCommitLog:
    """Test get_commit_log tool."""

    @patch("cicaddy_github.github_integration.tools._run_git")
    def test_returns_log(self, mock_git):
        mock_git.return_value = "abc123 feat: something"
        result = get_commit_log(since_days=7)
        assert "feat: something" in result

    @patch("cicaddy_github.github_integration.tools._run_git")
    def test_no_commits(self, mock_git):
        mock_git.return_value = ""
        result = get_commit_log(since_days=1)
        assert "No commits found" in result


class TestGetAllTools:
    """Test tool listing."""

    def test_returns_all_tools(self):
        tools = get_all_tools()
        assert len(tools) == 5

    def test_tools_are_tool_instances(self):
        from cicaddy.tools.decorator import Tool

        tools = get_all_tools()
        for t in tools:
            assert isinstance(t, Tool)
