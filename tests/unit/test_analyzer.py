"""Tests for GitHubAnalyzer git operations."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from cicaddy_github.github_integration.analyzer import GitHubAnalyzer


@pytest.fixture
def mock_github():
    """Create a mock GitHub API."""
    with patch("cicaddy_github.github_integration.analyzer.Github") as mock_gh_cls:
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        mock_gh_cls.return_value = mock_gh
        yield mock_gh, mock_repo


@pytest.fixture
def analyzer(mock_github):
    """Create an analyzer with mocked GitHub API."""
    return GitHubAnalyzer(
        token="test-token",
        repository="owner/repo",
        working_dir="/tmp/test-repo",
    )


class TestGetRecentTags:
    """Test tag retrieval."""

    @patch("subprocess.run")
    def test_get_recent_tags_returns_list(self, mock_run, analyzer):
        mock_run.return_value = MagicMock(stdout="v0.3.0\nv0.2.0\nv0.1.0\n", returncode=0)
        tags = analyzer.get_recent_tags(limit=3)
        assert tags == ["v0.3.0", "v0.2.0", "v0.1.0"]

    @patch("subprocess.run")
    def test_get_recent_tags_empty_repo(self, mock_run, analyzer):
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        tags = analyzer.get_recent_tags()
        assert tags == []

    @patch("subprocess.run")
    def test_get_recent_tags_git_failure(self, mock_run, analyzer):
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        tags = analyzer.get_recent_tags()
        assert tags == []


class TestGetTagDiff:
    """Test tag diff retrieval."""

    @patch("subprocess.run")
    def test_get_tag_diff_returns_commits(self, mock_run, analyzer):
        mock_run.return_value = MagicMock(
            stdout="abc123 feat: add new feature\ndef456 fix: bug fix\n",
            returncode=0,
        )
        result = analyzer.get_tag_diff("v0.1.0", "v0.2.0")
        assert "feat: add new feature" in result
        assert "fix: bug fix" in result

    @patch("subprocess.run")
    def test_get_tag_diff_invalid_tag(self, mock_run, analyzer):
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        result = analyzer.get_tag_diff("invalid", "HEAD")
        assert result == ""


class TestGetDiffStat:
    """Test diff stat retrieval."""

    @patch("subprocess.run")
    def test_get_diff_stat_output(self, mock_run, analyzer):
        stat_output = (
            " src/main.py | 10 +++++++---\n 2 files changed, 7 insertions(+), 3 deletions(-)"
        )
        mock_run.return_value = MagicMock(stdout=stat_output, returncode=0)
        result = analyzer.get_diff_stat("v0.1.0", "v0.2.0")
        assert "src/main.py" in result
        assert "insertions" in result

    @patch("subprocess.run")
    def test_get_diff_stat_git_failure(self, mock_run, analyzer):
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        result = analyzer.get_diff_stat("v0.1.0", "v0.2.0")
        assert result == ""


class TestGetReleaseNotes:
    """Test release notes retrieval."""

    def test_get_release_notes_existing(self, analyzer, mock_github):
        _, mock_repo = mock_github
        mock_release = MagicMock()
        mock_release.body = "## What's Changed\n- Feature A\n- Bug fix B"
        mock_repo.get_release.return_value = mock_release

        result = analyzer.get_release_notes("v0.2.0")
        assert "Feature A" in result

    def test_get_release_notes_not_found(self, analyzer, mock_github):
        _, mock_repo = mock_github
        mock_repo.get_release.side_effect = Exception("Not found")

        result = analyzer.get_release_notes("v999.0.0")
        assert result is None


class TestGetCommitLog:
    """Test date-based commit log."""

    @patch("subprocess.run")
    def test_get_commit_log_returns_output(self, mock_run, analyzer):
        mock_run.return_value = MagicMock(
            stdout="abc123 feat: something\ndef456 fix: something else\n",
            returncode=0,
        )
        result = analyzer.get_commit_log(since_days=7)
        assert "feat: something" in result

    @patch("subprocess.run")
    def test_get_commit_log_empty(self, mock_run, analyzer):
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        result = analyzer.get_commit_log(since_days=1)
        assert result == ""


class TestPullRequestOperations:
    """Test PR-related operations."""

    @pytest.mark.asyncio
    async def test_get_pull_request_diff(self, analyzer, mock_github):
        _, mock_repo = mock_github
        mock_pr = MagicMock()
        mock_file = MagicMock()
        mock_file.filename = "src/main.py"
        mock_file.patch = "@@ -1,3 +1,4 @@\n+new line"
        mock_pr.get_files.return_value = [mock_file]
        mock_repo.get_pull.return_value = mock_pr

        result = await analyzer.get_pull_request_diff(42)
        assert "src/main.py" in result
        assert "+new line" in result

    @pytest.mark.asyncio
    async def test_get_pull_request_data(self, analyzer, mock_github):
        _, mock_repo = mock_github
        mock_pr = MagicMock()
        mock_pr.title = "Test PR"
        mock_pr.body = "Description"
        mock_pr.user.login = "testuser"
        mock_pr.base.ref = "main"
        mock_pr.head.ref = "feature"
        mock_pr.state = "open"
        mock_pr.number = 42
        mock_repo.get_pull.return_value = mock_pr

        result = await analyzer.get_pull_request_data(42)
        assert result["title"] == "Test PR"
        assert result["author"]["name"] == "testuser"
        assert result["target_branch"] == "main"
