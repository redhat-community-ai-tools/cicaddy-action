"""GitHub repository analyzer using PyGithub API and local git commands."""

import logging
import subprocess

from github import Auth, Github

logger = logging.getLogger(__name__)


class GitHubAnalyzer:
    """Analyzer for GitHub repositories using PyGithub and local git commands."""

    def __init__(self, token: str, repository: str, working_dir: str = "."):
        """Initialize the GitHub analyzer.

        Args:
            token: GitHub API token.
            repository: Repository in owner/name format.
            working_dir: Local git working directory.
        """
        self.repository = repository
        self.working_dir = working_dir

        auth = Auth.Token(token)
        self.github = Github(auth=auth)
        self.repo = self.github.get_repo(repository)

    def _run_git(self, args: list[str]) -> str:
        """Run a git command and return stdout.

        Args:
            args: Git command arguments (without 'git' prefix).

        Returns:
            Command stdout as string.

        Raises:
            subprocess.CalledProcessError: If git command fails.
        """
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=True,
            cwd=self.working_dir,
        )
        return result.stdout.strip()

    def get_recent_tags(self, limit: int = 5) -> list[str]:
        """Get the most recent git tags sorted by version.

        Args:
            limit: Maximum number of tags to return.

        Returns:
            List of tag names, most recent first.
        """
        try:
            output = self._run_git(["tag", "--sort=-version:refname", f"--count={limit}"])
            if not output:
                return []
            return output.split("\n")
        except subprocess.CalledProcessError:
            logger.warning("Failed to get tags from git")
            return []

    def get_tag_diff(self, from_tag: str, to_tag: str = "HEAD") -> str:
        """Get commit messages between two git tags.

        Args:
            from_tag: Start tag.
            to_tag: End tag or HEAD.

        Returns:
            Commit log between tags.
        """
        try:
            return self._run_git(["log", f"{from_tag}..{to_tag}", "--oneline", "--no-merges"])
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get tag diff {from_tag}..{to_tag}: {e}")
            return ""

    def get_diff_stat(self, from_tag: str, to_tag: str = "HEAD") -> str:
        """Get file change statistics between two git tags.

        Args:
            from_tag: Start tag.
            to_tag: End tag or HEAD.

        Returns:
            Diff stat output showing files changed.
        """
        try:
            return self._run_git(["diff", "--stat", f"{from_tag}..{to_tag}"])
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get diff stat {from_tag}..{to_tag}: {e}")
            return ""

    def get_release_notes(self, tag: str) -> str | None:
        """Get GitHub release notes for a tag via PyGithub API.

        Args:
            tag: The release tag to look up.

        Returns:
            Release body text, or None if no release exists.
        """
        try:
            release = self.repo.get_release(tag)
            return release.body
        except Exception:
            logger.debug(f"No release found for tag {tag}")
            return None

    def get_commit_log(self, since_days: int = 30) -> str:
        """Get commit log for the last N days.

        Args:
            since_days: Number of days to look back.

        Returns:
            Commit log output.
        """
        try:
            return self._run_git(
                ["log", f"--since={since_days} days ago", "--oneline", "--no-merges"]
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get commit log: {e}")
            return ""

    async def get_pull_request_diff(self, pr_number: int, context_lines: int = 3) -> str:
        """Get pull request diff content via PyGithub.

        Args:
            pr_number: Pull request number.
            context_lines: Number of context lines in diff.

        Returns:
            Combined diff content from all changed files.
        """
        pr = self.repo.get_pull(pr_number)
        files = pr.get_files()

        diff_parts = []
        for f in files:
            diff_parts.append(f"--- a/{f.filename}")
            diff_parts.append(f"+++ b/{f.filename}")
            if f.patch:
                diff_parts.append(f.patch)
            diff_parts.append("")

        return "\n".join(diff_parts)

    async def get_pull_request_data(self, pr_number: int) -> dict:
        """Get pull request metadata.

        Args:
            pr_number: Pull request number.

        Returns:
            Dict with PR title, description, author, branches.
        """
        pr = self.repo.get_pull(pr_number)
        return {
            "title": pr.title,
            "description": pr.body or "",
            "author": {"name": pr.user.login},
            "target_branch": pr.base.ref,
            "source_branch": pr.head.ref,
            "state": pr.state,
            "number": pr.number,
        }

    async def post_pr_comment(self, pr_number: int, body: str) -> None:
        """Post a comment on a pull request.

        Args:
            pr_number: Pull request number.
            body: Comment body text.
        """
        pr = self.repo.get_pull(pr_number)
        pr.create_issue_comment(body)
        logger.info(f"Posted comment on PR #{pr_number}")

    def close(self):
        """Close the GitHub API connection."""
        self.github.close()
