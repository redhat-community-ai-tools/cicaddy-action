"""GitHub AI Agents for PR review and task execution."""

import os
import re
import textwrap
from typing import Any

from cicaddy.agent.base import BaseAIAgent
from cicaddy.tools import ToolRegistry
from cicaddy.utils.logger import get_logger

from cicaddy_github.config.settings import Settings
from cicaddy_github.github_integration.analyzer import GitHubAnalyzer
from cicaddy_github.github_integration.tools import get_all_tools
from cicaddy_github.security.leak_detector import LeakDetector

logger = get_logger(__name__)

BOT_COMMENT_MARKER_PR_REVIEW = "<!-- cicaddy-action:pr-review -->"

# Pattern matches fenced code blocks (possibly indented by list nesting).
_FENCED_CODE_BLOCK = re.compile(
    r"^([ \t]*(?:`{3,}|~{3,})[^\n]*)\n(.*?)\n([ \t]*(?:`{3,}|~{3,}))[ \t]*$",
    re.MULTILINE | re.DOTALL,
)


def dedent_code_blocks(text: str) -> str:
    """Remove common leading whitespace from fenced code block content.

    AI models often indent code block content to match surrounding list
    indentation.  GitHub renders that whitespace literally, so we strip
    the common prefix using ``textwrap.dedent`` while preserving relative
    indentation within the block.
    """

    def _dedent(match: re.Match) -> str:
        opener = match.group(1).lstrip()
        content = match.group(2)
        closer = match.group(3).lstrip()
        return f"{opener}\n{textwrap.dedent(content)}\n{closer}"

    return _FENCED_CODE_BLOCK.sub(_dedent, text)


# Matches output wrapped in a single ```markdown ... ``` fence.
_MARKDOWN_WRAPPER = re.compile(
    r"^\s*```(?:markdown|md)\s*\n(.*?)\n\s*```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def strip_markdown_wrapper(text: str) -> str:
    """Strip a wrapping ```markdown fence from the entire AI output.

    Some models interpret ``output_format: markdown`` as "wrap the response
    in a markdown code fence", which causes GitHub to render the comment as
    a literal code block instead of formatted markdown.
    """
    m = _MARKDOWN_WRAPPER.match(text.strip())
    if m:
        return m.group(1)
    return text


class GitHubTaskAgent(BaseAIAgent):
    """AI Agent for scheduled tasks and changelog generation."""

    def __init__(self, settings: Settings | None = None):
        super().__init__(settings)
        self.leak_detector = LeakDetector()

    async def _setup_local_tools(self):
        """Setup local tools including git operations for changelog."""
        await super()._setup_local_tools()
        if self.local_tool_registry is None:
            self.local_tool_registry = ToolRegistry(server_name="local")
        # Register git tools as local tools
        for t in get_all_tools():
            self.local_tool_registry.register(t)
        logger.info(f"Registered git tools: {self.local_tool_registry.list_tool_names()}")

    async def _setup_platform_integration(self):
        """Setup GitHub analyzer for API access."""
        token = os.getenv("GITHUB_TOKEN", "")
        repository = os.getenv("GITHUB_REPOSITORY", "")
        working_dir = getattr(self.settings, "local_tools_working_dir", None) or "."

        if token and repository:
            try:
                self.platform_analyzer = GitHubAnalyzer(
                    token=token, repository=repository, working_dir=working_dir
                )
                logger.info(f"GitHub analyzer initialized for {repository}")
            except Exception as e:
                logger.warning(f"Failed to initialize GitHub analyzer: {e}")
        else:
            logger.debug("GitHub analyzer not initialized (missing token or repository)")

    async def get_analysis_context(self) -> dict[str, Any]:
        """Get task-specific context."""
        return {
            "analysis_type": "task",
            "repository": os.getenv("GITHUB_REPOSITORY", ""),
            "ref": os.getenv("GITHUB_REF", ""),
            "sha": os.getenv("GITHUB_SHA", ""),
        }

    def build_analysis_prompt(self, context: dict[str, Any]) -> str:
        """Build analysis prompt for task execution.

        Supports DSPy YAML task definitions via AI_TASK_FILE.
        Falls back to inline prompt or default.
        """
        task_file = os.getenv("AI_TASK_FILE")
        if task_file:
            dspy_prompt = self.build_dspy_prompt(task_file, context)
            if dspy_prompt:
                return dspy_prompt

        task_prompt = os.getenv("AI_TASK_PROMPT", "")
        if task_prompt:
            return task_prompt

        return (
            "Analyze the repository and provide a summary of recent changes. "
            "Use the available git tools to gather information."
        )

    async def send_notifications(self, report: dict[str, Any], analysis_result: dict[str, Any]):
        """Send notifications via Slack (sanitized)."""
        # Sanitize outputs before sending
        if "ai_analysis" in analysis_result:
            analysis_result["ai_analysis"] = self.leak_detector.sanitize_text(
                analysis_result["ai_analysis"]
            )
        await super().send_notifications(report, analysis_result)

    def get_session_id(self) -> str:
        """Get unique session ID for this task."""
        run_id = os.getenv("GITHUB_RUN_ID", "unknown")
        return f"task_{run_id}"


class GitHubPRAgent(BaseAIAgent):
    """AI Agent specialized for pull request analysis and code review."""

    def __init__(self, settings: Settings | None = None):
        super().__init__(settings)
        self.pr_number = settings.github_pr_number if settings else os.getenv("GITHUB_PR_NUMBER")
        self.leak_detector = LeakDetector()

    async def _setup_local_tools(self):
        """Setup local tools for PR review."""
        await super()._setup_local_tools()
        if self.local_tool_registry is None:
            self.local_tool_registry = ToolRegistry(server_name="local")
        for t in get_all_tools():
            self.local_tool_registry.register(t)

    async def _setup_platform_integration(self):
        """Setup GitHub analyzer for PR access."""
        token = os.getenv("GITHUB_TOKEN", "")
        repository = os.getenv("GITHUB_REPOSITORY", "")
        working_dir = getattr(self.settings, "local_tools_working_dir", None) or "."

        if token and repository:
            try:
                self.platform_analyzer = GitHubAnalyzer(
                    token=token, repository=repository, working_dir=working_dir
                )
                logger.info(f"GitHub analyzer initialized for {repository}")
            except Exception as e:
                logger.warning(f"Failed to initialize GitHub analyzer: {e}")

    async def get_diff_content(self) -> str:
        """Get pull request diff content."""
        if not self.pr_number:
            raise ValueError("No PR number provided")
        if not self.platform_analyzer:
            raise ValueError("GitHub analyzer not initialized")

        return await self.platform_analyzer.get_pull_request_diff(
            int(self.pr_number),
            context_lines=getattr(self.settings, "git_diff_context_lines", 3),
        )

    async def get_review_context(self) -> dict[str, Any]:
        """Get pull request specific context."""
        if not self.pr_number:
            raise ValueError("No PR number provided")
        if not self.platform_analyzer:
            raise ValueError("GitHub analyzer not initialized")

        pr_data = await self.platform_analyzer.get_pull_request_data(int(self.pr_number))
        return {
            "pull_request": pr_data,
            "analysis_type": "pull_request",
            "pr_number": self.pr_number,
        }

    async def get_analysis_context(self) -> dict[str, Any]:
        """Get analysis context including PR data and diff."""
        context = await self.get_review_context()

        # Get diff content
        diff_content = await self.get_diff_content()
        context["diff"] = diff_content

        # Add repository info
        context["repository"] = os.getenv("GITHUB_REPOSITORY", "")

        return context

    def build_analysis_prompt(self, context: dict[str, Any]) -> str:
        """Build analysis prompt for PR code review.

        Supports DSPy YAML task definitions via AI_TASK_FILE.
        Falls back to built-in prompt.
        """
        task_file = os.getenv("AI_TASK_FILE")
        if task_file:
            pr_context = self._prepare_dspy_context(context)
            dspy_prompt = self.build_dspy_prompt(task_file, pr_context)
            if dspy_prompt:
                return dspy_prompt

        pr_data = context["pull_request"]
        diff_content = context["diff"]

        return f"""You are an AI agent performing pull request code review.

Repository: {context.get("repository", "Unknown")}
Pull Request: {pr_data["title"]}
Description: {pr_data.get("description", "No description")}
Author: {pr_data.get("author", {}).get("name", "Unknown")}
Target Branch: {pr_data.get("target_branch", "Unknown")}
Source Branch: {pr_data.get("source_branch", "Unknown")}

Code Changes:
```diff
{diff_content}
```

Instructions:
1. Analyze the code changes thoroughly
2. Identify bugs, security issues, and potential problems
3. Suggest improvements for code quality and maintainability
4. Provide actionable, specific feedback

Please provide your comprehensive analysis in markdown format.
"""

    def _prepare_dspy_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """Prepare context with PR-specific data for DSPy prompt building."""
        pr_context = context.copy()
        pr_data = context.get("pull_request", {})
        pr_context["pr_title"] = pr_data.get("title", "Unknown")
        pr_context["pr_description"] = pr_data.get("description", "")
        pr_context["pr_author"] = pr_data.get("author", {}).get("name", "Unknown")
        pr_context["target_branch"] = pr_data.get("target_branch", "Unknown")
        pr_context["source_branch"] = pr_data.get("source_branch", "Unknown")
        pr_context["pr_number"] = self.pr_number
        pr_context["diff_content"] = context.get("diff", "")
        return pr_context

    async def send_notifications(self, report: dict[str, Any], analysis_result: dict[str, Any]):
        """Send notifications via PR review/comment and Slack."""
        # Sanitize outputs
        if "ai_analysis" in analysis_result:
            analysis_result["ai_analysis"] = self.leak_detector.sanitize_text(
                analysis_result["ai_analysis"]
            )

        # Check if we should submit a formal review
        review_decision = self._extract_review_decision(analysis_result)
        submit_review = getattr(self.settings, "submit_pr_review", False)

        if submit_review and review_decision and self.platform_analyzer and self.pr_number:
            # Submit formal review with APPROVE, REQUEST_CHANGES, or COMMENT
            try:
                comment = self._format_pr_comment(analysis_result)
                review_info = await self.platform_analyzer.create_review(
                    int(self.pr_number), comment, event=review_decision
                )
                logger.info(
                    f"Submitted {review_decision} review to PR #{self.pr_number} "
                    f"(review_id={review_info['id']})"
                )
            except Exception as e:
                logger.error(
                    f"Failed to submit PR review: {self.leak_detector.sanitize_text(str(e))}"
                )
                logger.debug("PR review submission traceback:", exc_info=True)
        else:
            # Fallback to comment mode (updates existing bot comment in-place)
            post_comment = getattr(self.settings, "post_pr_comment", False)
            if post_comment and self.platform_analyzer and self.pr_number:
                try:
                    comment = self._format_pr_comment(analysis_result)
                    await self.platform_analyzer.post_pr_comment(
                        int(self.pr_number), comment, comment_marker=BOT_COMMENT_MARKER_PR_REVIEW
                    )
                    logger.info(f"Posted analysis to PR #{self.pr_number}")
                except Exception as e:
                    logger.error(
                        f"Failed to post PR comment: {self.leak_detector.sanitize_text(str(e))}"
                    )
                    logger.debug("PR comment post traceback:", exc_info=True)

        # Send Slack notification using parent class
        await super().send_notifications(report, analysis_result)

    def _extract_review_decision(self, analysis_result: dict[str, Any]) -> str | None:
        """Extract review decision from AI analysis result.

        Looks for 'review_decision' in the parsed outputs or attempts to
        parse it from the raw AI analysis text.

        Returns:
            One of "APPROVE", "REQUEST_CHANGES", "COMMENT", or None if not found.
        """
        # Try to get from parsed outputs first (DSPy structured output)
        outputs = analysis_result.get("outputs", {})
        if isinstance(outputs, dict) and "review_decision" in outputs:
            decision = outputs["review_decision"]
            if decision in {"APPROVE", "REQUEST_CHANGES", "COMMENT"}:
                return decision

        # Fallback: try to parse from AI analysis text
        ai_text = analysis_result.get("ai_analysis", "")
        if not ai_text:
            return None

        # Look for patterns like "review_decision: APPROVE" or "**Review Decision**: REQUEST_CHANGES"
        import re

        patterns = [
            r"review_decision\s*[:=]\s*(APPROVE|REQUEST_CHANGES|COMMENT)",
            r"\*\*review[_ ]decision\*\*\s*[:=]\s*(APPROVE|REQUEST_CHANGES|COMMENT)",
            r"decision\s*[:=]\s*(APPROVE|REQUEST_CHANGES|COMMENT)",
        ]

        for pattern in patterns:
            match = re.search(pattern, ai_text, re.IGNORECASE)
            if match:
                return match.group(1).upper()

        return None

    def _format_pr_comment(self, analysis_result: dict[str, Any]) -> str:
        """Format analysis results as a PR comment.

        The hidden marker is prepended so the bot can find and update its own
        comment later.  No heading is injected — the AI analysis output already
        contains its own structure.
        """
        comment = f"{BOT_COMMENT_MARKER_PR_REVIEW}\n"

        if "ai_analysis" in analysis_result:
            cleaned = strip_markdown_wrapper(analysis_result["ai_analysis"])
            comment += dedent_code_blocks(cleaned) + "\n"

        comment += (
            "\n<!-- cicaddy-footer -->\n---\n"
            "*Generated with [cicaddy-action]"
            "(https://github.com/redhat-community-ai-tools/cicaddy-action)*"
        )
        return comment

    def get_session_id(self) -> str:
        """Get unique session ID for this PR analysis."""
        return f"pr_{self.pr_number or 'unknown'}"
