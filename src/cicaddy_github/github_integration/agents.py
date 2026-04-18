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
from cicaddy_github.github_integration.go_dep_review_tools import get_all_go_dep_review_tools
from cicaddy_github.github_integration.tools import get_all_tools
from cicaddy_github.security.leak_detector import LeakDetector

logger = get_logger(__name__)

BOT_COMMENT_MARKER_PR_REVIEW = "<!-- cicaddy-action:pr-review -->"
BOT_COMMENT_MARKER_GO_DEP_REVIEW = "<!-- cicaddy-action:go-dep-review -->"

# Pattern to detect a review verdict in the AI analysis output.
# The AI is instructed to include a line like "VERDICT: APPROVE" or
# "VERDICT: REQUEST_CHANGES" in its output.
_VERDICT_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:<!--\s*)?VERDICT:\s*(APPROVE|REQUEST_CHANGES)(?:\s*-->)?",
    re.IGNORECASE,
)

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


def extract_review_verdict(ai_text: str) -> str:
    """Extract the review verdict from AI analysis output.

    Looks for a ``VERDICT: APPROVE`` or ``VERDICT: REQUEST_CHANGES`` line
    (optionally wrapped in an HTML comment).  Defaults to ``COMMENT`` when
    no explicit verdict is found.
    """
    m = _VERDICT_PATTERN.search(ai_text)
    if m:
        return m.group(1).upper()
    return "COMMENT"


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
                if getattr(self.settings, "submit_review", False):
                    dspy_prompt += self._verdict_instruction()
                return dspy_prompt

        pr_data = context["pull_request"]
        diff_content = context["diff"]

        submit_review = getattr(self.settings, "submit_review", False)
        verdict_block = self._verdict_instruction() if submit_review else ""

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
{verdict_block}"""

    @staticmethod
    def _verdict_instruction() -> str:
        """Return the prompt snippet that asks the AI to emit a verdict."""
        return (
            "\n\nIMPORTANT: At the very end of your analysis, you MUST include a verdict line "
            "in an HTML comment with the format:\n"
            "<!-- VERDICT: APPROVE -->\n"
            "or\n"
            "<!-- VERDICT: REQUEST_CHANGES -->\n\n"
            "Use REQUEST_CHANGES when there are bugs, security issues, or significant problems "
            "that must be fixed before merging. Use APPROVE when the changes look good overall "
            "(minor suggestions are OK with APPROVE)."
        )

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
        """Send notifications via PR comment, formal review, and Slack."""
        # Sanitize outputs
        if "ai_analysis" in analysis_result:
            analysis_result["ai_analysis"] = self.leak_detector.sanitize_text(
                analysis_result["ai_analysis"]
            )

        # Post PR comment if enabled (updates existing bot comment in-place)
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

        # Submit formal PR review if enabled
        submit_review = getattr(self.settings, "submit_review", False)
        if submit_review and self.platform_analyzer and self.pr_number:
            try:
                ai_text = analysis_result.get("ai_analysis", "")
                verdict = extract_review_verdict(ai_text)
                review_body = self._format_review_body(analysis_result)
                await self.platform_analyzer.submit_pr_review(
                    int(self.pr_number), review_body, event=verdict
                )
                logger.info(f"Submitted {verdict} review on PR #{self.pr_number}")
            except Exception as e:
                logger.error(
                    f"Failed to submit PR review: {self.leak_detector.sanitize_text(str(e))}"
                )
                logger.debug("PR review submit traceback:", exc_info=True)

        # Send Slack notification using parent class
        await super().send_notifications(report, analysis_result)

    def _format_review_body(self, analysis_result: dict[str, Any]) -> str:
        """Format analysis results as a PR review body.

        Strips the VERDICT line from the output so it does not appear in
        the rendered review.
        """
        body = ""
        if "ai_analysis" in analysis_result:
            cleaned = strip_markdown_wrapper(analysis_result["ai_analysis"])
            cleaned = dedent_code_blocks(cleaned)
            # Remove the VERDICT line from the review body
            cleaned = _VERDICT_PATTERN.sub("", cleaned).strip()
            body = cleaned

        body += (
            "\n\n---\n"
            "*Generated with [cicaddy-action]"
            "(https://github.com/redhat-community-ai-tools/cicaddy-action)*"
        )
        return body

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

        # Add delegation metadata if delegation mode was used
        if analysis_result.get("delegation_mode") == "auto":
            delegation_plan = analysis_result.get("delegation_plan", {})
            agents = delegation_plan.get("agents", [])
            if agents:
                agent_names = [a["name"] for a in agents]
                succeeded = analysis_result.get("agents_succeeded", 0)
                failed = analysis_result.get("agents_failed", 0)
                exec_time = analysis_result.get("total_execution_time", 0)
                comment += (
                    f"\n<details><summary>Delegation details: "
                    f"{succeeded} agent(s) succeeded"
                    f"{f', {failed} failed' if failed else ''}"
                    f" ({exec_time:.1f}s)</summary>\n\n"
                    f"Agents: {', '.join(agent_names)}\n\n"
                )
                for agent in agents:
                    comment += f"- **{agent['name']}**: {agent.get('rationale', '')}\n"
                comment += "\n</details>\n"

        comment += (
            "\n<!-- cicaddy-footer -->\n---\n"
            "*Generated with [cicaddy-action]"
            "(https://github.com/redhat-community-ai-tools/cicaddy-action)*"
        )
        return comment

    def get_session_id(self) -> str:
        """Get unique session ID for this PR analysis."""
        return f"pr_{self.pr_number or 'unknown'}"


class GitHubGoDepReviewAgent(BaseAIAgent):
    """AI Agent for Go dependency impact analysis on pull requests.

    Collects Go dependency context (diffs, usage via go mod, changelogs,
    advisories, govulncheck) and uses an LLM to produce a structured
    risk assessment comment.
    """

    def __init__(self, settings: Settings | None = None):
        super().__init__(settings)
        self.pr_number = getattr(settings, "github_pr_number", None) if settings else None
        self.leak_detector = LeakDetector()

    async def _setup_local_tools(self):
        """Setup local tools including git and dependency review tools."""
        await super()._setup_local_tools()
        if self.local_tool_registry is None:
            self.local_tool_registry = ToolRegistry(server_name="local")
        # Register git tools
        for t in get_all_tools():
            self.local_tool_registry.register(t)
        # Register dependency review tools
        for t in get_all_go_dep_review_tools():
            self.local_tool_registry.register(t)
        logger.info(f"Registered tools: {self.local_tool_registry.list_tool_names()}")

    async def _setup_platform_integration(self):
        """Setup GitHub analyzer for API access."""
        token = getattr(self.settings, "github_token", "") or ""
        repository = getattr(self.settings, "github_repository", "") or ""
        working_dir = getattr(self.settings, "local_tools_working_dir", None) or "."

        if token and repository:
            try:
                self.platform_analyzer = GitHubAnalyzer(
                    token=token, repository=repository, working_dir=working_dir
                )
                logger.info(f"GitHub analyzer initialized for {repository}")
            except Exception as e:
                logger.warning(f"Failed to initialize GitHub analyzer: {e}")

    async def get_analysis_context(self) -> dict[str, Any]:
        """Get dependency review context including PR data."""
        context: dict[str, Any] = {
            "analysis_type": "go_dependency_review",
            "repository": getattr(self.settings, "github_repository", "") or "",
            "ref": getattr(self.settings, "github_ref", "") or "",
            "sha": getattr(self.settings, "github_sha", "") or "",
            "pr_number": self.pr_number,
        }

        # Get PR metadata if available
        if self.platform_analyzer and self.pr_number:
            try:
                pr_data = await self.platform_analyzer.get_pull_request_data(int(self.pr_number))
                context["pull_request"] = pr_data
            except Exception as e:
                logger.warning(f"Failed to get PR data: {e}")

        return context

    def build_analysis_prompt(self, context: dict[str, Any]) -> str:
        """Build analysis prompt for dependency impact review.

        Supports DSPy YAML task definitions via AI_TASK_FILE.
        Falls back to inline prompt.
        """
        task_file = os.getenv("AI_TASK_FILE")
        if task_file:
            dep_context = self._prepare_dep_review_context(context)
            dspy_prompt = self.build_dspy_prompt(task_file, dep_context)
            if dspy_prompt:
                return dspy_prompt

        task_prompt = os.getenv("AI_TASK_PROMPT", "")
        if task_prompt:
            return task_prompt

        pr_data = context.get("pull_request", {})
        return f"""You are an AI agent performing dependency impact analysis on a pull request.

Repository: {context.get("repository", "Unknown")}
Pull Request: {pr_data.get("title", "Unknown")}
Description: {pr_data.get("description", "No description")}
Author: {
            pr_data.get("author", {}).get("name", "Unknown")
            if isinstance(pr_data.get("author"), dict)
            else "Unknown"
        }

Instructions:
1. Use get_dependency_diff to get the structured dependency changes between the PR base and head
2. For each changed dependency:
   a. Use get_dependency_usage to check if it is directly imported
   b. Use get_upstream_changelog to fetch release notes between versions
   c. Use get_security_advisories to check for known vulnerabilities
3. Optionally use run_govulncheck for reachability analysis
4. Classify overall risk as LOW, MEDIUM, or HIGH
5. Provide a structured impact assessment

Format your response as markdown with these sections:
- Risk Classification (LOW/MEDIUM/HIGH)
- Changelog Summary
- Impact Assessment (which APIs/types we use are affected)
- Impacted Files
- Recommended Action (auto-merge / quick-review / full-review)
"""

    def _prepare_dep_review_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """Prepare context with PR-specific data for DSPy prompt building."""
        dep_context = context.copy()
        pr_data = context.get("pull_request", {})
        dep_context["pr_title"] = pr_data.get("title", "Unknown")
        dep_context["pr_description"] = pr_data.get("description", "")
        dep_context["pr_author"] = pr_data.get("author", {}).get("name", "Unknown")
        dep_context["target_branch"] = pr_data.get("target_branch", "Unknown")
        dep_context["source_branch"] = pr_data.get("source_branch", "Unknown")
        dep_context["pr_number"] = self.pr_number
        return dep_context

    async def send_notifications(self, report: dict[str, Any], analysis_result: dict[str, Any]):
        """Send notifications via PR comment and Slack (sanitized)."""
        # Sanitize outputs
        if "ai_analysis" in analysis_result:
            analysis_result["ai_analysis"] = self.leak_detector.sanitize_text(
                analysis_result["ai_analysis"]
            )

        # Post PR comment if enabled
        post_comment = getattr(self.settings, "post_pr_comment", False)
        if post_comment and self.platform_analyzer and self.pr_number:
            try:
                comment = self._format_dep_review_comment(analysis_result)
                await self.platform_analyzer.post_pr_comment(
                    int(self.pr_number), comment, comment_marker=BOT_COMMENT_MARKER_GO_DEP_REVIEW
                )
                logger.info(f"Posted dep review to PR #{self.pr_number}")
            except Exception as e:
                logger.error(
                    f"Failed to post dep review comment: {self.leak_detector.sanitize_text(str(e))}"
                )
                logger.debug("Dep review comment post traceback:", exc_info=True)

        # Send Slack notification using parent class
        await super().send_notifications(report, analysis_result)

    def _format_dep_review_comment(self, analysis_result: dict[str, Any]) -> str:
        """Format analysis results as a dep review PR comment."""
        comment = f"{BOT_COMMENT_MARKER_GO_DEP_REVIEW}\n"

        if "ai_analysis" in analysis_result:
            cleaned = strip_markdown_wrapper(analysis_result["ai_analysis"])
            comment += dedent_code_blocks(cleaned) + "\n"

        comment += (
            "\n<!-- cicaddy-footer -->\n---\n"
            "*Generated with [cicaddy-action]"
            "(https://github.com/redhat-community-ai-tools/cicaddy-action) "
            "— Dependency Impact Analysis*"
        )
        return comment

    def get_session_id(self) -> str:
        """Get unique session ID for this dep review."""
        return f"go_dep_review_{self.pr_number or 'unknown'}"
