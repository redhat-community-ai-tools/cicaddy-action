"""Configuration for cicaddy-github (GitHub-specific extension of cicaddy)."""

import logging
import os
from typing import Any

from cicaddy.config.settings import CoreSettings
from pydantic import AliasChoices, Field
from pydantic_settings import SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(CoreSettings):
    """Application settings with GitHub Actions platform-specific fields.

    Extends CoreSettings with GitHub-specific configuration such as
    tokens, repository info, event names, and other CI variables.
    """

    model_config = SettingsConfigDict(extra="ignore")

    # GitHub configuration (uses built-in Actions variables)
    github_token: str = Field(
        default="",
        validation_alias=AliasChoices("GITHUB_TOKEN"),
        description="GitHub API token for repository access",
    )
    github_repository: str = Field(
        default="",
        validation_alias=AliasChoices("GITHUB_REPOSITORY"),
        description="Repository in owner/name format",
    )
    github_ref: str = Field(
        default="",
        validation_alias=AliasChoices("GITHUB_REF"),
        description="Git ref that triggered the workflow",
    )
    github_event_name: str = Field(
        default="",
        validation_alias=AliasChoices("GITHUB_EVENT_NAME"),
        description="Name of the event that triggered the workflow",
    )
    github_sha: str = Field(
        default="",
        validation_alias=AliasChoices("GITHUB_SHA"),
        description="Commit SHA that triggered the workflow",
    )
    github_run_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GITHUB_RUN_ID"),
        description="Unique ID for the workflow run",
    )
    github_pr_number: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GITHUB_PR_NUMBER"),
        description="Pull request number",
    )
    post_pr_comment: bool = Field(
        default=False,
        validation_alias=AliasChoices("POST_PR_COMMENT"),
        description="Whether to post analysis results as PR comment",
    )
    submit_review: bool = Field(
        default=False,
        validation_alias=AliasChoices("SUBMIT_REVIEW"),
        description="Whether to submit a formal PR review (APPROVE or REQUEST_CHANGES)",
    )
    run_govulncheck: bool = Field(
        default=False,
        validation_alias=AliasChoices("RUN_GOVULNCHECK"),
        description="Whether to run govulncheck for vulnerability reachability analysis",
    )
    dep_review_severity_threshold: str = Field(
        default="minor",
        validation_alias=AliasChoices("DEP_REVIEW_SEVERITY_THRESHOLD"),
        description="Minimum semver bump to analyze: 'minor' or 'major'",
    )


def load_settings() -> Settings:
    """Load settings from environment variables with GitHub Actions defaults."""

    # Handle MCP_SERVERS_CONFIG - default to empty array if missing
    current_mcp_config = os.getenv("MCP_SERVERS_CONFIG")
    if not current_mcp_config:
        os.environ["MCP_SERVERS_CONFIG"] = "[]"

    # Explicitly pass environment variables to work around Pydantic env reading issues
    env_data: dict[str, Any] = {}

    # GitHub configuration
    if os.getenv("GITHUB_TOKEN"):
        env_data["github_token"] = os.getenv("GITHUB_TOKEN")
    if os.getenv("GITHUB_REPOSITORY"):
        env_data["github_repository"] = os.getenv("GITHUB_REPOSITORY")
    if os.getenv("GITHUB_REF"):
        env_data["github_ref"] = os.getenv("GITHUB_REF")
    if os.getenv("GITHUB_EVENT_NAME"):
        env_data["github_event_name"] = os.getenv("GITHUB_EVENT_NAME")
    if os.getenv("GITHUB_SHA"):
        env_data["github_sha"] = os.getenv("GITHUB_SHA")
    if os.getenv("GITHUB_RUN_ID"):
        env_data["github_run_id"] = os.getenv("GITHUB_RUN_ID")
    if os.getenv("GITHUB_PR_NUMBER"):
        env_data["github_pr_number"] = os.getenv("GITHUB_PR_NUMBER")

    # Post PR comment flag
    post_pr = os.getenv("POST_PR_COMMENT", "").strip()
    if post_pr:
        env_data["post_pr_comment"] = post_pr.lower() in ("true", "1", "yes")

    # Submit formal PR review flag
    submit_review = os.getenv("SUBMIT_REVIEW", "").strip()
    if submit_review:
        env_data["submit_review"] = submit_review.lower() in ("true", "1", "yes")

    # Dep review configuration
    run_govulncheck = os.getenv("RUN_GOVULNCHECK", "").strip()
    if run_govulncheck:
        env_data["run_govulncheck"] = run_govulncheck.lower() in ("true", "1", "yes")

    dep_threshold = os.getenv("DEP_REVIEW_SEVERITY_THRESHOLD", "").strip()
    if dep_threshold:
        env_data["dep_review_severity_threshold"] = dep_threshold

    # AI provider configuration
    if os.getenv("AI_PROVIDER"):
        env_data["ai_provider"] = os.getenv("AI_PROVIDER")
    if os.getenv("AI_MODEL"):
        env_data["ai_model"] = os.getenv("AI_MODEL")

    # AI API keys
    if os.getenv("GEMINI_API_KEY"):
        env_data["gemini_api_key"] = os.getenv("GEMINI_API_KEY")
    if os.getenv("OPENAI_API_KEY"):
        env_data["openai_api_key"] = os.getenv("OPENAI_API_KEY")
    if os.getenv("ANTHROPIC_API_KEY"):
        env_data["anthropic_api_key"] = os.getenv("ANTHROPIC_API_KEY")

    # MCP server configuration
    if os.getenv("MCP_SERVERS_CONFIG"):
        env_data["mcp_servers_config"] = os.getenv("MCP_SERVERS_CONFIG")

    # Slack configuration
    if os.getenv("SLACK_WEBHOOK_URL"):
        env_data["slack_webhook_url"] = os.getenv("SLACK_WEBHOOK_URL")

    # Agent configuration
    if os.getenv("AI_TASK_PROMPT"):
        env_data["review_prompt"] = os.getenv("AI_TASK_PROMPT")
    if os.getenv("AI_TASK_FILE"):
        env_data["task_file"] = os.getenv("AI_TASK_FILE")
    if os.getenv("ANALYSIS_FOCUS"):
        env_data["analysis_focus"] = os.getenv("ANALYSIS_FOCUS")

    # Git configuration
    git_diff_context = os.getenv("GIT_DIFF_CONTEXT_LINES")
    if git_diff_context:
        env_data["git_diff_context_lines"] = int(git_diff_context)

    # Local tools configuration
    if os.getenv("ENABLE_LOCAL_TOOLS", "").strip():
        env_data["enable_local_tools"] = os.getenv("ENABLE_LOCAL_TOOLS", "").lower().strip() in (
            "true",
            "1",
            "yes",
        )
    if os.getenv("LOCAL_TOOLS_WORKING_DIR"):
        env_data["local_tools_working_dir"] = os.getenv("LOCAL_TOOLS_WORKING_DIR")

    # Execution configuration
    max_exec_env = os.getenv("MAX_EXECUTION_TIME")
    if max_exec_env == "":
        os.environ.pop("MAX_EXECUTION_TIME", None)
    elif max_exec_env:
        try:
            max_exec_time = int(max_exec_env)
            if 60 <= max_exec_time <= 7200:
                env_data["max_execution_time"] = max_exec_time
            else:
                logger.warning(
                    f"MAX_EXECUTION_TIME {max_exec_time} out of range [60, 7200], using default 600"
                )
                os.environ.pop("MAX_EXECUTION_TIME", None)
                env_data["max_execution_time"] = 600
        except ValueError:
            logger.warning(f"Invalid MAX_EXECUTION_TIME value '{max_exec_env}', using default 600")
            os.environ.pop("MAX_EXECUTION_TIME", None)
            env_data["max_execution_time"] = 600

    context_safety_env = os.getenv("CONTEXT_SAFETY_FACTOR")
    if context_safety_env == "":
        os.environ.pop("CONTEXT_SAFETY_FACTOR", None)
    elif context_safety_env:
        try:
            safety_factor = float(context_safety_env)
            if 0.5 <= safety_factor <= 0.97:
                env_data["context_safety_factor"] = safety_factor
            else:
                logger.warning(
                    f"CONTEXT_SAFETY_FACTOR {safety_factor} out of range [0.5, 0.97], "
                    "using default 0.85"
                )
                os.environ.pop("CONTEXT_SAFETY_FACTOR", None)
                env_data["context_safety_factor"] = 0.85
        except ValueError:
            logger.warning(
                f"Invalid CONTEXT_SAFETY_FACTOR value '{context_safety_env}', using default 0.85"
            )
            os.environ.pop("CONTEXT_SAFETY_FACTOR", None)
            env_data["context_safety_factor"] = 0.85

    # Logging configuration
    if os.getenv("LOG_LEVEL"):
        env_data["log_level"] = os.getenv("LOG_LEVEL")

    # Report configuration
    if os.getenv("REPORT_TEMPLATE"):
        env_data["report_template"] = os.getenv("REPORT_TEMPLATE")

    return Settings(**env_data)
