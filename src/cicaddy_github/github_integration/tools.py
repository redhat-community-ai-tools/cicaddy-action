"""Local tools for LLM agents — git operations for changelog and analysis.

These are local tools registered via cicaddy's @tool decorator and ToolRegistry.
They run as subprocess calls in the container, no MCP server needed.
"""

import logging
import os
import subprocess

from cicaddy.tools import tool

from cicaddy_github.validation import validate_git_ref, validate_positive_int

logger = logging.getLogger(__name__)


def _get_working_dir() -> str:
    """Get the git working directory from environment or default."""
    return os.getenv("LOCAL_TOOLS_WORKING_DIR", os.getenv("GITHUB_WORKSPACE", os.getcwd()))


def _run_git(args: list[str]) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True,
        cwd=_get_working_dir(),
    )
    return result.stdout.strip()


@tool
def get_recent_tags(limit: int = 5) -> str:
    """Get the most recent git tags sorted by version.

    Args:
        limit: Maximum number of tags to return
    """
    try:
        validate_positive_int(limit, "limit")
        output = _run_git(["tag", "--sort=-version:refname", f"--count={limit}"])
        if not output:
            return "No tags found in this repository."
        return output
    except subprocess.CalledProcessError as e:
        return f"Error getting tags: {e.stderr}"


@tool
def get_tag_diff(from_tag: str, to_tag: str = "HEAD") -> str:
    """Get commit messages between two git tags.

    Args:
        from_tag: Start tag
        to_tag: End tag or HEAD
    """
    try:
        validate_git_ref(from_tag, "from_tag")
        validate_git_ref(to_tag, "to_tag")
        output = _run_git(["log", f"{from_tag}..{to_tag}", "--oneline", "--no-merges"])
        if not output:
            return f"No commits found between {from_tag} and {to_tag}."
        return output
    except subprocess.CalledProcessError as e:
        return f"Error getting tag diff: {e.stderr}"


@tool
def get_diff_stat(from_tag: str, to_tag: str = "HEAD") -> str:
    """Get file change statistics between two git tags.

    Args:
        from_tag: Start tag
        to_tag: End tag or HEAD
    """
    try:
        validate_git_ref(from_tag, "from_tag")
        validate_git_ref(to_tag, "to_tag")
        output = _run_git(["diff", "--stat", f"{from_tag}..{to_tag}"])
        if not output:
            return f"No file changes found between {from_tag} and {to_tag}."
        return output
    except subprocess.CalledProcessError as e:
        return f"Error getting diff stat: {e.stderr}"


@tool
def get_release_notes(tag: str) -> str:
    """Get GitHub release notes for a tag via PyGithub API.

    Args:
        tag: The release tag to look up
    """
    token = os.getenv("GITHUB_TOKEN")
    repository = os.getenv("GITHUB_REPOSITORY")

    if not token or not repository:
        return "GITHUB_TOKEN and GITHUB_REPOSITORY must be set to fetch release notes."

    try:
        from github import Auth, Github

        auth = Auth.Token(token)
        gh = Github(auth=auth)
        repo = gh.get_repo(repository)
        release = repo.get_release(tag)
        body = release.body or "No release notes content."
        gh.close()
        return body
    except Exception as e:
        return f"No release found for tag '{tag}': {e}"


@tool
def get_commit_log(since_days: int = 30) -> str:
    """Get commit log for the last N days (fallback when no tags exist).

    Args:
        since_days: Number of days to look back
    """
    try:
        validate_positive_int(since_days, "since_days")
        output = _run_git(["log", f"--since={since_days} days ago", "--oneline", "--no-merges"])
        if not output:
            return f"No commits found in the last {since_days} days."
        return output
    except subprocess.CalledProcessError as e:
        return f"Error getting commit log: {e.stderr}"


def get_all_tools() -> list:
    """Return all git tools for registration with ToolRegistry."""
    return [get_recent_tags, get_tag_diff, get_diff_stat, get_release_notes, get_commit_log]
