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


class TestPostPRComment:
    """Test PR comment posting and update-in-place."""

    @pytest.mark.asyncio
    async def test_creates_new_comment_without_marker(self, analyzer, mock_github):
        """Without a marker, always creates a new comment."""
        _, mock_repo = mock_github
        mock_pr = MagicMock()
        mock_repo.get_pull.return_value = mock_pr

        await analyzer.post_pr_comment(42, "new body")

        mock_pr.create_issue_comment.assert_called_once_with("new body")

    @pytest.mark.asyncio
    async def test_creates_new_comment_when_no_existing(self, analyzer, mock_github):
        """With a marker but no existing comment, creates a new one."""
        _, mock_repo = mock_github
        mock_pr = MagicMock()
        mock_pr.get_issue_comments.return_value = []
        mock_repo.get_pull.return_value = mock_pr

        await analyzer.post_pr_comment(42, "new body", comment_marker="## Bot")

        mock_pr.create_issue_comment.assert_called_once_with("new body")

    @pytest.mark.asyncio
    async def test_updates_existing_comment_in_place(self, analyzer, mock_github):
        """Existing bot comment is edited, not deleted and recreated."""
        _, mock_repo = mock_github
        mock_pr = MagicMock()

        old_comment = MagicMock()
        old_comment.body = "## Bot\n\nold analysis"
        old_comment.id = 99
        mock_pr.get_issue_comments.return_value = [old_comment]
        mock_repo.get_pull.return_value = mock_pr

        await analyzer.post_pr_comment(42, "## Bot\n\nnew analysis", comment_marker="## Bot")

        old_comment.edit.assert_called_once()
        mock_pr.create_issue_comment.assert_not_called()

    @pytest.mark.asyncio
    async def test_updated_body_contains_collapsed_previous(self, analyzer, mock_github):
        """The edited body collapses the old analysis in a <details> block."""
        _, mock_repo = mock_github
        mock_pr = MagicMock()

        old_comment = MagicMock()
        old_comment.body = "## Bot\n\nold analysis"
        old_comment.id = 99
        mock_pr.get_issue_comments.return_value = [old_comment]
        mock_repo.get_pull.return_value = mock_pr

        await analyzer.post_pr_comment(42, "## Bot\n\nnew analysis", comment_marker="## Bot")

        edited_body = old_comment.edit.call_args[0][0]
        assert "## Bot\n\nnew analysis" in edited_body
        assert "<summary><b>Previous analyses</b></summary>" in edited_body
        assert "old analysis" in edited_body

    @pytest.mark.asyncio
    async def test_ignores_unrelated_comments(self, analyzer, mock_github):
        """Unrelated comments are not touched."""
        _, mock_repo = mock_github
        mock_pr = MagicMock()

        other = MagicMock()
        other.body = "LGTM!"
        mock_pr.get_issue_comments.return_value = [other]
        mock_repo.get_pull.return_value = mock_pr

        await analyzer.post_pr_comment(42, "## Bot\n\nnew", comment_marker="## Bot")

        other.edit.assert_not_called()
        mock_pr.create_issue_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_comment_with_none_body(self, analyzer, mock_github):
        """Comment with None body is safely skipped."""
        _, mock_repo = mock_github
        mock_pr = MagicMock()

        null_comment = MagicMock()
        null_comment.body = None
        mock_pr.get_issue_comments.return_value = [null_comment]
        mock_repo.get_pull.return_value = mock_pr

        await analyzer.post_pr_comment(42, "## Bot\n\nnew", comment_marker="## Bot")

        null_comment.edit.assert_not_called()
        mock_pr.create_issue_comment.assert_called_once()


class TestBuildUpdatedBody:
    """Test the history collapsing logic."""

    def test_first_update_collapses_old_body(self):
        old = "## Bot\n\nfirst analysis\n\n---\nfooter"
        new = "## Bot\n\nsecond analysis\n\n---\nfooter"

        result = GitHubAnalyzer._build_updated_body(old, new)

        assert result.startswith("## Bot\n\nsecond analysis")
        assert "<summary><b>Previous analyses</b></summary>" in result
        assert "first analysis" in result

    def test_preserves_existing_history(self):
        """Multiple updates accumulate history inside the collapsed block."""
        first = "## Bot\n\nfirst"
        second = GitHubAnalyzer._build_updated_body(first, "## Bot\n\nsecond")
        third = GitHubAnalyzer._build_updated_body(second, "## Bot\n\nthird")

        assert third.startswith("## Bot\n\nthird")
        assert "second" in third
        assert "first" in third
        assert third.count("<summary><b>Previous analyses</b></summary>") == 1

    def test_strips_footer_from_collapsed_history(self):
        """Footer is removed from old content before collapsing."""
        old = "## Bot\n\nold analysis\n\n---\n*Generated with bot*"
        new = "## Bot\n\nnew analysis\n\n---\n*Generated with bot*"

        result = GitHubAnalyzer._build_updated_body(old, new)

        # The collapsed history should not contain the footer
        history_start = result.index("<summary>")
        history_section = result[history_start:]
        assert "*Generated with bot*" not in history_section
        # But the new body's footer is preserved at the top level
        assert result.startswith("## Bot\n\nnew analysis")

    def test_truncates_when_exceeding_max_length(self):
        """History is dropped when result exceeds character limit."""
        old = "## Bot\n\n" + "x" * 40_000
        new = "## Bot\n\n" + "y" * 40_000

        result = GitHubAnalyzer._build_updated_body(old, new)

        # Combined would exceed 65,000 so history should be dropped
        assert result == new
        assert "Previous analyses" not in result
