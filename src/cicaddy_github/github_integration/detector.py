"""GitHub-specific agent type detection for cicaddy plugin."""

import os

from cicaddy.utils.logger import get_logger

logger = get_logger(__name__)


def _detect_github_agent_type(settings) -> str | None:
    """Detect GitHub-specific agent types from Actions environment variables."""
    event = os.getenv("GITHUB_EVENT_NAME")

    # Check for explicit dep_review agent task
    agent_tasks = os.getenv("AGENT_TASKS", "")
    if "dep_review" in agent_tasks:
        if event in ("pull_request", "pull_request_target"):
            logger.info(f"Detected dep review context: AGENT_TASKS={agent_tasks}")
            return "github_dep_review"
        pr_number = getattr(settings, "github_pr_number", None)
        if pr_number:
            logger.info(f"Dep review with PR number in settings: {pr_number}")
            return "github_dep_review"

    if event in ("pull_request", "pull_request_target"):
        logger.info(f"Detected pull request context: GITHUB_EVENT_NAME={event}")
        return "github_pr"

    # Check for PR number in settings as fallback
    pr_number = getattr(settings, "github_pr_number", None)
    if pr_number:
        logger.info(f"Found PR number in settings: {pr_number}")
        return "github_pr"

    return None
