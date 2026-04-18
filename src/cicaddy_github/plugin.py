"""Entry point callables for cicaddy plugin registration."""


def register_agents():
    """Register GitHub agents and detector with cicaddy.

    GitHubPRAgent and GitHubTaskAgent are registered here because they
    require GitHub-specific functionality (PyGithub API, PR comments).
    TaskAgent stays in cicaddy core — it doesn't need GitHub API.
    """
    from cicaddy.agent.factory import AgentFactory

    from cicaddy_github.github_integration.agents import (
        GitHubGoDepReviewAgent,
        GitHubPRAgent,
        GitHubTaskAgent,
    )
    from cicaddy_github.github_integration.detector import _detect_github_agent_type

    AgentFactory.register("github_pr", GitHubPRAgent)
    AgentFactory.register("github_task", GitHubTaskAgent)
    AgentFactory.register("github_go_dep_review", GitHubGoDepReviewAgent)
    AgentFactory.register_detector(_detect_github_agent_type, priority=40)


def get_cli_args():
    """Return additional CLI argument mappings."""
    from cicaddy.cli.arg_mapping import ArgMapping

    return [
        ArgMapping(
            cli_arg="--pr-number",
            env_var="GITHUB_PR_NUMBER",
            help_text="GitHub pull request number",
        ),
        ArgMapping(
            cli_arg="--github-repo",
            env_var="GITHUB_REPOSITORY",
            help_text="GitHub repository (owner/name)",
        ),
    ]


def get_env_vars():
    """Return additional environment variable names."""
    return [
        "GITHUB_TOKEN",
        "GITHUB_REPOSITORY",
        "GITHUB_REF",
        "GITHUB_EVENT_NAME",
        "GITHUB_SHA",
        "GITHUB_RUN_ID",
    ]


def config_section(config, mask_fn, sensitive_vars):
    """Display GitHub Settings in config show."""
    print("\n[GitHub Settings]")
    for var in [
        "GITHUB_TOKEN",
        "GITHUB_REPOSITORY",
        "GITHUB_REF",
        "GITHUB_EVENT_NAME",
        "GITHUB_SHA",
        "GITHUB_RUN_ID",
    ]:
        value = config.get(var)
        if var in sensitive_vars:
            print(f"  {var}: {mask_fn(value)}")
        else:
            print(f"  {var}: {value or '(not set)'}")


def get_delegation_blocked_tools() -> set[str]:
    """Return tool names that delegation sub-agents must NOT use.

    These are write/mutating operations on the GitHub platform that only
    the parent agent should perform (posting comments, submitting reviews, etc.).
    """
    return {
        # GitHub analyzer mutating methods
        "post_pr_comment",
        "submit_pr_review",
        # Common GitHub MCP server write tools
        "create_issue_comment",
        "create_pull_request_review",
        "update_pull_request",
        "merge_pull_request",
        "create_issue",
        "update_issue",
        "close_issue",
        "add_labels",
        "remove_labels",
        "create_branch",
        "delete_branch",
        # Pipeline, tag, and release operations
        "create_workflow_dispatch",
        "cancel_workflow_run",
        "create_tag",
        "delete_tag",
        "create_release",
        "delete_release",
        # Comment mutation tools
        "update_issue_comment",
        "delete_issue_comment",
        # Notification tools
        "send_slack_message",
    }


def validate(config):
    """Validate GitHub-specific configuration."""
    import os

    errors, warnings = [], []
    print("\n[GitHub Integration]")

    # Check GITHUB_TOKEN
    token = config.get("GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
    agent_type = config.get("AGENT_TYPE")
    if token:
        from cicaddy.cli.env_loader import mask_sensitive_value

        print(f"  GITHUB_TOKEN: {mask_sensitive_value(token)} ✓")
    elif agent_type in ("github_pr",):
        errors.append("GITHUB_TOKEN is required for PR agents")
        print("  GITHUB_TOKEN: (not set) ✗")
    else:
        warnings.append("GITHUB_TOKEN not set")
        print("  GITHUB_TOKEN: (not set) ~")

    # Check repository
    repo = config.get("GITHUB_REPOSITORY") or os.getenv("GITHUB_REPOSITORY")
    if repo:
        print(f"  GITHUB_REPOSITORY: {repo} ✓")
    elif agent_type in ("github_pr",):
        errors.append("GITHUB_REPOSITORY is required for PR agents")
        print("  GITHUB_REPOSITORY: (not set) ✗")

    # Check PR number for PR agent
    pr_number = config.get("GITHUB_PR_NUMBER") or os.getenv("GITHUB_PR_NUMBER")
    if agent_type == "github_pr":
        if pr_number:
            print(f"  GITHUB_PR_NUMBER: {pr_number} ✓")
        else:
            errors.append("GITHUB_PR_NUMBER is required for PR agent")
            print("  GITHUB_PR_NUMBER: (not set) ✗")

    return errors, warnings
