"""Tests for Go dependency impact review tools and agent."""

import json
import os
import subprocess
import urllib.error
from unittest.mock import MagicMock, patch

import pytest  # noqa: F401 — used by pytest.raises and pytest.mark

from cicaddy_github.github_integration.go_dep_review_tools import (
    _extract_owner_repo,
    _github_api_post,
    _validate_repository,
    get_all_go_dep_review_tools,
    get_dependency_diff,
    get_dependency_usage,
    get_security_advisories,
    get_upstream_changelog,
    run_govulncheck,
)


class TestGetDependencyDiff:
    """Test get_dependency_diff tool."""

    @patch.dict(
        "os.environ",
        {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_TOKEN": "test-token"},
    )
    @patch("cicaddy_github.github_integration.go_dep_review_tools._github_api_get")
    def test_returns_dependency_changes(self, mock_api_get):
        mock_api_get.return_value = json.dumps(
            [
                {
                    "change_type": "updated",
                    "ecosystem": "go",
                    "name": "golang.org/x/net",
                    "version": "0.21.0",
                    "package_url": "pkg:golang/golang.org/x/net@0.21.0",
                    "source_repository_url": "https://github.com/golang/net",
                    "license": "BSD-3-Clause",
                    "vulnerabilities": [],
                }
            ]
        ).encode()

        result = get_dependency_diff(base_ref="main", head_ref="feature")
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["name"] == "golang.org/x/net"
        assert data[0]["change_type"] == "updated"

    @patch.dict("os.environ", {}, clear=False)
    def test_missing_repository(self):
        os.environ.pop("GITHUB_REPOSITORY", None)
        result = get_dependency_diff(base_ref="main", head_ref="feature")
        assert "GITHUB_REPOSITORY" in result

    def test_invalid_ref(self):
        with pytest.raises(ValueError, match="Invalid git"):
            get_dependency_diff(base_ref="main;rm -rf /", head_ref="feature")

    @patch.dict(
        "os.environ",
        {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_TOKEN": "test-token"},
    )
    @patch("cicaddy_github.github_integration.go_dep_review_tools._github_api_get")
    def test_with_vulnerabilities(self, mock_api_get):
        mock_api_get.return_value = json.dumps(
            [
                {
                    "change_type": "updated",
                    "ecosystem": "go",
                    "name": "golang.org/x/crypto",
                    "version": "0.17.0",
                    "package_url": "pkg:golang/golang.org/x/crypto@0.17.0",
                    "source_repository_url": "https://github.com/golang/crypto",
                    "license": "BSD-3-Clause",
                    "vulnerabilities": [
                        {
                            "severity": "high",
                            "advisory_ghsa_id": "GHSA-test-1234",
                            "advisory_summary": "SSH vulnerability",
                        }
                    ],
                }
            ]
        ).encode()

        result = get_dependency_diff(base_ref="main", head_ref="fix-deps")
        data = json.loads(result)
        assert len(data[0]["vulnerabilities"]) == 1
        assert data[0]["vulnerabilities"][0]["severity"] == "high"


class TestGetDependencyUsage:
    """Test get_dependency_usage tool."""

    @patch("cicaddy_github.github_integration.go_dep_review_tools._get_working_dir")
    @patch("subprocess.run")
    @patch("os.path.isfile", return_value=True)
    def test_returns_usage_info(self, mock_isfile, mock_run, mock_wd):
        mock_wd.return_value = "/workspace"
        # go mod why
        mock_run.side_effect = [
            MagicMock(
                stdout="# golang.org/x/net\nmy-project\ngolang.org/x/net/http2",
                stderr="",
                returncode=0,
            ),
            # go mod graph
            MagicMock(
                stdout="my-project golang.org/x/net@v0.21.0\n",
                stderr="",
                returncode=0,
            ),
        ]
        result = get_dependency_usage(module_name="golang.org/x/net")
        data = json.loads(result)
        assert "go_mod_why" in data
        assert "golang.org/x/net" in data["go_mod_why"]
        assert "dependency_graph" in data

    def test_invalid_module_name_shell_chars(self):
        result = get_dependency_usage(module_name="foo;rm -rf /")
        assert "Invalid" in result

    def test_invalid_module_name_newline(self):
        result = get_dependency_usage(module_name="foo\nbar")
        assert "Invalid" in result

    def test_invalid_module_name_whitespace(self):
        result = get_dependency_usage(module_name="foo bar")
        assert "Invalid" in result

    def test_invalid_module_name_tab(self):
        result = get_dependency_usage(module_name="foo\tbar")
        assert "Invalid" in result

    def test_valid_module_name_with_tilde(self):
        """Go module names can contain ~ (used in v2+ paths)."""
        # Should not be rejected by validation
        # (will fail at go mod why since no go.mod, but that's OK)
        with (
            patch(
                "cicaddy_github.github_integration.go_dep_review_tools._get_working_dir",
                return_value="/workspace",
            ),
            patch("os.path.isfile", return_value=False),
        ):
            result = get_dependency_usage(module_name="example.com/mod~v2")
        assert "No go.mod" in result

    def test_empty_module_name(self):
        result = get_dependency_usage(module_name="")
        assert "Error" in result

    @patch("cicaddy_github.github_integration.go_dep_review_tools._get_working_dir")
    @patch("os.path.isfile", return_value=False)
    def test_no_go_mod(self, mock_isfile, mock_wd):
        mock_wd.return_value = "/workspace"
        result = get_dependency_usage(module_name="golang.org/x/net")
        assert "No go.mod" in result


class TestGetUpstreamChangelog:
    """Test get_upstream_changelog tool."""

    @patch("cicaddy_github.github_integration.go_dep_review_tools._github_api_get")
    def test_fetches_release_notes(self, mock_api_get):
        mock_api_get.return_value = json.dumps(
            {
                "body": "## What's Changed\n- Fixed a bug\n- Added feature",
            }
        ).encode()

        result = get_upstream_changelog(
            repo_url="https://github.com/golang/net",
            old_version="v0.17.0",
            new_version="v0.21.0",
        )
        data = json.loads(result)
        assert data["source"] == "github_release"
        assert "Fixed a bug" in data["body"]

    def test_missing_parameters(self):
        result = get_upstream_changelog(repo_url="", old_version="v1.0", new_version="v2.0")
        assert "Error" in result

    @patch("cicaddy_github.github_integration.go_dep_review_tools._github_api_get")
    @patch("cicaddy_github.github_integration.go_dep_review_tools._fetch_generated_notes")
    @patch("cicaddy_github.github_integration.go_dep_review_tools._fetch_release_notes")
    def test_falls_back_to_commits(self, mock_release, mock_generated, mock_api_get):
        """When release and generated notes fail, falls back to commits."""
        mock_release.return_value = None
        mock_generated.return_value = None
        mock_api_get.return_value = json.dumps(
            {
                "total_commits": 5,
                "commits": [
                    {"commit": {"message": "fix: some bug"}},
                    {"commit": {"message": "feat: new thing"}},
                ],
            }
        ).encode()

        result = get_upstream_changelog(
            repo_url="https://github.com/owner/repo",
            old_version="v1.0.0",
            new_version="v1.1.0",
        )
        data = json.loads(result)
        assert data["source"] == "commit_comparison"


class TestGetSecurityAdvisories:
    """Test get_security_advisories tool."""

    @patch("cicaddy_github.github_integration.go_dep_review_tools._github_api_get")
    def test_returns_advisories(self, mock_api_get):
        mock_api_get.return_value = json.dumps(
            [
                {
                    "ghsa_id": "GHSA-test-1234",
                    "cve_id": "CVE-2024-1234",
                    "summary": "SSH vulnerability in x/crypto",
                    "severity": "high",
                    "cvss": {"score": 8.1},
                    "published_at": "2024-01-15T00:00:00Z",
                    "html_url": "https://github.com/advisories/GHSA-test-1234",
                    "vulnerabilities": [
                        {
                            "package": {"name": "golang.org/x/crypto"},
                            "vulnerable_version_range": "< 0.17.0",
                            "patched_versions": "0.17.0",
                        }
                    ],
                }
            ]
        ).encode()

        result = get_security_advisories(
            ecosystem="go",
            package_name="golang.org/x/crypto",
            version="0.16.0",
        )
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["ghsa_id"] == "GHSA-test-1234"
        assert data[0]["severity"] == "high"
        assert data[0]["cvss_score"] == 8.1

    @patch("cicaddy_github.github_integration.go_dep_review_tools._github_api_get")
    def test_no_advisories_found(self, mock_api_get):
        mock_api_get.return_value = b"[]"

        result = get_security_advisories(ecosystem="go", package_name="safe/package")
        data = json.loads(result)
        assert data["status"] == "clean"

    def test_missing_params(self):
        result = get_security_advisories(ecosystem="", package_name="")
        assert "Error" in result


class TestRunGovulncheck:
    """Test run_govulncheck tool."""

    @patch("shutil.which", return_value=None)
    def test_skipped_when_not_installed(self, mock_which):
        result = run_govulncheck()
        data = json.loads(result)
        assert data["status"] == "skipped"
        assert "not installed" in data["reason"]

    @patch("cicaddy_github.github_integration.go_dep_review_tools._get_working_dir")
    @patch("os.path.isfile", return_value=False)
    @patch("shutil.which", return_value="/usr/bin/govulncheck")
    def test_skipped_no_go_mod(self, mock_which, mock_isfile, mock_wd):
        mock_wd.return_value = "/workspace"
        result = run_govulncheck()
        data = json.loads(result)
        assert data["status"] == "skipped"

    @patch("cicaddy_github.github_integration.go_dep_review_tools._get_working_dir")
    @patch("os.path.isfile", return_value=True)
    @patch("shutil.which", return_value="/usr/bin/govulncheck")
    @patch("subprocess.run")
    def test_runs_successfully(self, mock_run, mock_which, mock_isfile, mock_wd):
        mock_wd.return_value = "/workspace"
        mock_run.return_value = MagicMock(
            stdout='{"vulns": []}',
            stderr="",
            returncode=0,
        )
        result = run_govulncheck()
        data = json.loads(result)
        assert data["status"] == "completed"

    @patch("cicaddy_github.github_integration.go_dep_review_tools._get_working_dir")
    @patch("os.path.isfile", return_value=True)
    @patch("shutil.which", return_value="/usr/bin/govulncheck")
    @patch("subprocess.run")
    def test_handles_vulns_found(self, mock_run, mock_which, mock_isfile, mock_wd):
        mock_wd.return_value = "/workspace"
        mock_run.return_value = MagicMock(
            stdout='{"vulns": [{"id": "GO-2024-001"}]}',
            stderr="",
            returncode=3,  # exit code 3 = vulns found
        )
        result = run_govulncheck()
        data = json.loads(result)
        assert data["status"] == "completed"

    @patch("cicaddy_github.github_integration.go_dep_review_tools._get_working_dir")
    @patch("os.path.isfile", return_value=True)
    @patch("shutil.which", return_value="/usr/bin/govulncheck")
    @patch("subprocess.run")
    def test_handles_timeout(self, mock_run, mock_which, mock_isfile, mock_wd):
        mock_wd.return_value = "/workspace"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="govulncheck", timeout=300)
        result = run_govulncheck()
        data = json.loads(result)
        assert data["status"] == "error"
        assert "timed out" in data["reason"]


class TestExtractOwnerRepo:
    """Test _extract_owner_repo helper."""

    def test_github_url(self):
        assert _extract_owner_repo("https://github.com/golang/net") == "golang/net"

    def test_github_url_with_git(self):
        assert _extract_owner_repo("https://github.com/owner/repo.git") == "owner/repo"

    def test_github_url_with_trailing_slash(self):
        assert _extract_owner_repo("https://github.com/owner/repo/") == "owner/repo"

    def test_owner_repo_format(self):
        assert _extract_owner_repo("owner/repo") == "owner/repo"

    def test_invalid_url(self):
        assert _extract_owner_repo("not-a-url") is None

    def test_non_github_url(self):
        assert _extract_owner_repo("https://gitlab.com/owner/repo") is None


class TestGetAllDepReviewTools:
    """Test tool listing."""

    def test_returns_all_tools(self):
        tools = get_all_go_dep_review_tools()
        assert len(tools) == 5

    def test_tools_are_tool_instances(self):
        from cicaddy.tools.decorator import Tool

        tools = get_all_go_dep_review_tools()
        for t in tools:
            assert isinstance(t, Tool)


class TestGoDepReviewDetector:
    """Test agent type detection for go_dep_review."""

    def test_go_dep_review_with_pull_request_event(self):
        from cicaddy_github.github_integration.detector import _detect_github_agent_type

        settings = MagicMock()
        settings.github_pr_number = None
        with patch.dict(
            os.environ,
            {"GITHUB_EVENT_NAME": "pull_request", "AGENT_TASKS": "go_dep_review"},
        ):
            result = _detect_github_agent_type(settings)
        assert result == "github_go_dep_review"

    def test_go_dep_review_with_pr_number_fallback(self):
        from cicaddy_github.github_integration.detector import _detect_github_agent_type

        settings = MagicMock()
        settings.github_pr_number = "42"
        with patch.dict(
            os.environ,
            {"GITHUB_EVENT_NAME": "push", "AGENT_TASKS": "go_dep_review"},
        ):
            result = _detect_github_agent_type(settings)
        assert result == "github_go_dep_review"

    def test_go_dep_review_without_pr_context(self):
        """go_dep_review without PR context falls through to None."""
        from cicaddy_github.github_integration.detector import _detect_github_agent_type

        settings = MagicMock()
        settings.github_pr_number = None
        with patch.dict(
            os.environ,
            {"GITHUB_EVENT_NAME": "push", "AGENT_TASKS": "go_dep_review"},
        ):
            result = _detect_github_agent_type(settings)
        assert result is None

    def test_code_review_unaffected_by_go_dep_review(self):
        """Without AGENT_TASKS=go_dep_review, PR events still return github_pr."""
        from cicaddy_github.github_integration.detector import _detect_github_agent_type

        settings = MagicMock()
        settings.github_pr_number = None
        with patch.dict(
            os.environ,
            {"GITHUB_EVENT_NAME": "pull_request", "AGENT_TASKS": "code_review"},
        ):
            result = _detect_github_agent_type(settings)
        assert result == "github_pr"


class TestGitHubGoDepReviewAgent:
    """Test GitHubGoDepReviewAgent class."""

    def test_session_id(self):
        from cicaddy_github.github_integration.agents import GitHubGoDepReviewAgent

        settings = MagicMock()
        settings.github_pr_number = "42"
        agent = GitHubGoDepReviewAgent(settings=settings)
        assert agent.get_session_id() == "go_dep_review_42"

    def test_session_id_unknown(self):
        from cicaddy_github.github_integration.agents import GitHubGoDepReviewAgent

        settings = MagicMock()
        settings.github_pr_number = None
        agent = GitHubGoDepReviewAgent(settings=settings)
        assert agent.get_session_id() == "go_dep_review_unknown"

    def test_comment_marker_is_unique(self):
        from cicaddy_github.github_integration.agents import (
            BOT_COMMENT_MARKER_GO_DEP_REVIEW,
            BOT_COMMENT_MARKER_PR_REVIEW,
        )

        assert BOT_COMMENT_MARKER_GO_DEP_REVIEW != BOT_COMMENT_MARKER_PR_REVIEW
        assert "go-dep-review" in BOT_COMMENT_MARKER_GO_DEP_REVIEW

    def test_format_dep_review_comment(self):
        from cicaddy_github.github_integration.agents import (
            BOT_COMMENT_MARKER_GO_DEP_REVIEW,
            GitHubGoDepReviewAgent,
        )

        settings = MagicMock()
        settings.github_pr_number = "42"
        agent = GitHubGoDepReviewAgent(settings=settings)

        analysis_result = {"ai_analysis": "## Risk: LOW\nAll deps are safe."}
        comment = agent._format_dep_review_comment(analysis_result)

        assert comment.startswith(BOT_COMMENT_MARKER_GO_DEP_REVIEW)
        assert "Risk: LOW" in comment
        assert "Dependency Impact Analysis" in comment
        assert "cicaddy-footer" in comment

    @pytest.mark.asyncio
    async def test_get_analysis_context(self):
        from cicaddy_github.github_integration.agents import GitHubGoDepReviewAgent

        settings = MagicMock()
        settings.github_pr_number = "42"
        agent = GitHubGoDepReviewAgent(settings=settings)
        agent.platform_analyzer = None

        with patch.dict(
            os.environ,
            {
                "GITHUB_REPOSITORY": "owner/repo",
                "GITHUB_REF": "refs/pull/42/merge",
                "GITHUB_SHA": "abc123",
            },
        ):
            context = await agent.get_analysis_context()

        assert context["analysis_type"] == "go_dependency_review"
        assert context["pr_number"] == "42"
        assert context["repository"] == "owner/repo"

    @pytest.mark.asyncio
    async def test_send_notifications_posts_comment(self):
        from unittest.mock import AsyncMock

        from cicaddy_github.github_integration.agents import GitHubGoDepReviewAgent

        settings = MagicMock()
        settings.github_pr_number = "42"
        settings.post_pr_comment = True
        agent = GitHubGoDepReviewAgent(settings=settings)

        mock_analyzer = MagicMock()
        mock_analyzer.post_pr_comment = AsyncMock()
        agent.platform_analyzer = mock_analyzer

        with patch.object(
            GitHubGoDepReviewAgent.__bases__[0],
            "send_notifications",
            new_callable=AsyncMock,
        ):
            await agent.send_notifications(
                report={},
                analysis_result={"ai_analysis": "## Risk: LOW"},
            )

        mock_analyzer.post_pr_comment.assert_called_once()
        call_args = mock_analyzer.post_pr_comment.call_args
        assert call_args[0][0] == 42
        assert "Risk: LOW" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_send_notifications_sanitizes_output(self):
        from unittest.mock import AsyncMock

        from cicaddy_github.github_integration.agents import GitHubGoDepReviewAgent

        settings = MagicMock()
        settings.github_pr_number = "42"
        settings.post_pr_comment = False
        agent = GitHubGoDepReviewAgent(settings=settings)
        agent.platform_analyzer = None

        agent.leak_detector = MagicMock()
        agent.leak_detector.sanitize_text.return_value = "sanitized"

        with patch.object(
            GitHubGoDepReviewAgent.__bases__[0],
            "send_notifications",
            new_callable=AsyncMock,
        ):
            analysis_result = {"ai_analysis": "secret_token_here"}
            await agent.send_notifications(report={}, analysis_result=analysis_result)

        agent.leak_detector.sanitize_text.assert_called_once_with("secret_token_here")
        assert analysis_result["ai_analysis"] == "sanitized"


class TestValidateRepository:
    """Test _validate_repository helper."""

    def test_valid_repo(self):
        assert _validate_repository("owner/repo") is None

    def test_valid_repo_with_dots(self):
        assert _validate_repository("my-org/my.repo") is None

    def test_empty_repo(self):
        error = _validate_repository("")
        assert error is not None
        assert "not set" in error

    def test_invalid_format_no_slash(self):
        error = _validate_repository("justrepo")
        assert error is not None
        assert "Invalid" in error

    def test_invalid_format_path_traversal(self):
        error = _validate_repository("../../../etc/passwd")
        assert error is not None
        assert "Invalid" in error

    @patch.dict(
        "os.environ",
        {"GITHUB_REPOSITORY": "bad format!", "GITHUB_TOKEN": "t"},
    )
    def test_invalid_repo_in_get_dependency_diff(self):
        result = get_dependency_diff(base_ref="main", head_ref="dev")
        assert "Invalid" in result


class TestGitHubApiPost:
    """Test _github_api_post helper."""

    @patch("urllib.request.urlopen")
    def test_posts_json_payload(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"body": "notes"}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = _github_api_post(
            "/repos/owner/repo/releases/generate-notes",
            {"Accept": "application/vnd.github+json"},
            b'{"tag_name": "v1.0"}',
        )
        assert b"notes" in result

        # Verify the request was constructed correctly
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.method == "POST"
        assert req.data == b'{"tag_name": "v1.0"}'
        assert "application/json" in req.get_header("Content-type")

    @patch("urllib.request.urlopen")
    def test_raises_on_http_error(self, mock_urlopen):
        from email.message import Message

        hdrs = Message()
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://api.github.com/test",
            422,
            "Unprocessable",
            hdrs,
            None,
        )
        with pytest.raises(urllib.error.HTTPError):
            _github_api_post("/test", {}, b"{}")
