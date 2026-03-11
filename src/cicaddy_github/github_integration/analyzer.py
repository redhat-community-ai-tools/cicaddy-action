"""GitHub repository analyzer using PyGithub API and local git commands."""

import html
import logging
import subprocess

from github import Auth, Github

from cicaddy_github.validation import validate_git_ref

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
            if not isinstance(limit, int) or limit <= 0:
                raise ValueError(f"limit must be a positive integer, got {limit!r}")
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
            validate_git_ref(from_tag, "from_tag")
            validate_git_ref(to_tag, "to_tag")
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
            validate_git_ref(from_tag, "from_tag")
            validate_git_ref(to_tag, "to_tag")
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
            if not isinstance(since_days, int) or since_days <= 0:
                raise ValueError(f"since_days must be a positive integer, got {since_days!r}")
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
            safe_name = html.escape(f.filename, quote=True)
            diff_parts.append(f"--- a/{safe_name}")
            diff_parts.append(f"+++ b/{safe_name}")
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

    async def post_pr_comment(
        self, pr_number: int, body: str, comment_marker: str | None = None
    ) -> None:
        """Post or update a comment on a pull request.

        When *comment_marker* is provided the method looks for an existing
        comment whose body starts with that marker.  If found, the previous
        analysis is collapsed into a ``<details>`` block and the comment is
        updated in-place (similar to CodeRabbit / Qodo persistent review).
        Otherwise a new comment is created.

        Args:
            pr_number: Pull request number.
            body: Comment body text.
            comment_marker: Optional marker that identifies the bot comment
                (e.g. ``"## AI Code Review"``).
        """
        pr = self.repo.get_pull(pr_number)

        if comment_marker:
            existing = self._find_bot_comment(pr, comment_marker)
            if existing:
                updated = self._build_updated_body(existing.body, body)
                existing.edit(updated)
                logger.info(f"Updated existing comment (id={existing.id}) on PR #{pr_number}")
                return

        pr.create_issue_comment(body)
        logger.info(f"Posted comment on PR #{pr_number}")

    @staticmethod
    def _find_bot_comment(pr, marker: str):
        """Return the first issue comment whose body starts with *marker*."""
        for comment in pr.get_issue_comments():
            if comment.body and comment.body.startswith(marker):
                return comment
        return None

    # GitHub limits issue comments to 65,536 characters.
    MAX_COMMENT_LENGTH = 65_000

    FOOTER_MARKER = "<!-- cicaddy-footer -->"

    @classmethod
    def _strip_footer(cls, body: str) -> str:
        """Remove the trailing footer from a comment body.

        Looks for the unique ``<!-- cicaddy-footer -->`` marker to avoid
        accidentally stripping markdown horizontal rules in AI output.
        """
        idx = body.rfind(cls.FOOTER_MARKER)
        if idx != -1:
            return body[:idx].rstrip()
        return body.rstrip()

    @classmethod
    def _build_updated_body(cls, old_body: str, new_body: str) -> str:
        """Prepend *new_body* and collapse the previous analysis.

        Footers are stripped from old content to avoid duplication.
        If the result exceeds the GitHub character limit the oldest
        history entries are dropped.
        """
        history_tag = "\n<details>\n<summary><b>Previous analyses</b></summary>\n"

        # Strip footer from old content before collapsing
        old_content = cls._strip_footer(old_body)

        if history_tag in old_content:
            current_section, existing_history = old_content.split(history_tag, 1)
            existing_history = existing_history.rstrip()
            if existing_history.endswith("</details>"):
                existing_history = existing_history[: -len("</details>")].rstrip()
            collapsed = (
                f"{history_tag}\n{current_section.strip()}\n\n{existing_history}\n\n</details>\n"
            )
        else:
            collapsed = f"{history_tag}\n{old_content.strip()}\n\n</details>\n"

        result = f"{new_body}\n{collapsed}"

        # Truncate history if the comment exceeds the character limit
        if len(result) > cls.MAX_COMMENT_LENGTH:
            truncation_note = (
                "\n\n*[Older history truncated to stay within GitHub character limit]*"
            )
            result = f"{new_body}{truncation_note}"
            logger.warning("Comment history truncated to stay within character limit")

        return result

    def close(self):
        """Close the GitHub API connection."""
        self.github.close()
