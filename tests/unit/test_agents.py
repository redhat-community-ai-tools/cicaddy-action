"""Tests for dedent_code_blocks, strip_markdown_wrapper, and review decision extraction."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cicaddy_github.config.settings import Settings
from cicaddy_github.github_integration.agents import (
    GitHubPRAgent,
    dedent_code_blocks,
    strip_markdown_wrapper,
)


class TestDedentCodeBlocks:
    """Test code block dedenting for AI-generated markdown."""

    def test_dedents_indented_code_block(self):
        """Code block content indented by list nesting is dedented."""
        text = (
            "*   **Example:**\n"
            "    ```diff\n"
            "        --- a/file.txt\n"
            "        +++ b/file.txt\n"
            "        @@ -1,3 +1,4 @@\n"
            "    ```"
        )
        result = dedent_code_blocks(text)
        assert "```diff\n--- a/file.txt\n+++ b/file.txt" in result

    def test_preserves_relative_indentation(self):
        """Relative indentation within the code block is preserved."""
        text = "    ```python\n        def foo():\n            return 42\n    ```"
        result = dedent_code_blocks(text)
        assert "```python\ndef foo():\n    return 42\n```" in result

    def test_no_change_for_unindented_blocks(self):
        """Already flush code blocks are unchanged."""
        text = "```python\ndef foo():\n    return 42\n```"
        result = dedent_code_blocks(text)
        assert result == text

    def test_multiple_code_blocks(self):
        """Multiple code blocks in the same text are all dedented."""
        text = (
            "Item 1:\n"
            "    ```python\n"
            "        print('a')\n"
            "    ```\n"
            "\n"
            "Item 2:\n"
            "    ```bash\n"
            "        echo hello\n"
            "    ```"
        )
        result = dedent_code_blocks(text)
        assert "```python\nprint('a')\n```" in result
        assert "```bash\necho hello\n```" in result

    def test_tilde_delimiters(self):
        """Tilde-fenced code blocks are also dedented."""
        text = "    ~~~python\n        print('hello')\n    ~~~"
        result = dedent_code_blocks(text)
        assert "~~~python\nprint('hello')\n~~~" in result

    def test_trailing_whitespace_on_closer(self):
        """Trailing whitespace after closing fence is tolerated."""
        text = "    ```python\n        x = 1\n    ```   "
        result = dedent_code_blocks(text)
        assert "```python\nx = 1\n```" in result

    def test_text_without_code_blocks(self):
        """Plain text without code blocks is unchanged."""
        text = "This is plain markdown with **bold** and *italic*."
        assert dedent_code_blocks(text) == text

    def test_mixed_content_preserves_surrounding_text(self):
        """List structure around code blocks is preserved."""
        text = "* Item one\n    ```diff\n        +added line\n    ```\n* Item two"
        result = dedent_code_blocks(text)
        assert result.startswith("* Item one\n")
        assert result.endswith("* Item two")
        assert "+added line" in result


class TestStripMarkdownWrapper:
    """Test stripping wrapping ```markdown fences from AI output."""

    def test_strips_markdown_wrapper(self):
        """Output wrapped in ```markdown is unwrapped."""
        text = "```markdown\n### Summary\nSome analysis.\n```"
        result = strip_markdown_wrapper(text)
        assert result == "### Summary\nSome analysis."

    def test_strips_md_wrapper(self):
        """Output wrapped in ```md is also unwrapped."""
        text = "```md\n## Title\nContent.\n```"
        result = strip_markdown_wrapper(text)
        assert result == "## Title\nContent."

    def test_strips_case_insensitive(self):
        """Output wrapped in ```Markdown or ```MD is also unwrapped."""
        for tag in ("Markdown", "MARKDOWN", "MD", "Md"):
            text = f"```{tag}\nContent here.\n```"
            result = strip_markdown_wrapper(text)
            assert result == "Content here.", f"Failed for tag: {tag}"

    def test_no_change_without_wrapper(self):
        """Plain markdown without wrapper is unchanged."""
        text = "### Summary\nSome analysis."
        assert strip_markdown_wrapper(text) == text

    def test_preserves_internal_code_blocks(self):
        """Code blocks inside the markdown wrapper are preserved."""
        text = "```markdown\n### Example\n```python\nprint('hi')\n```\n```"
        result = strip_markdown_wrapper(text)
        assert "```python\nprint('hi')\n```" in result

    def test_no_change_for_non_markdown_fence(self):
        """A ```python wrapper is NOT stripped."""
        text = "```python\nprint('hi')\n```"
        assert strip_markdown_wrapper(text) == text


class TestExtractReviewDecision:
    """Test review decision extraction from AI analysis results."""

    def test_extracts_from_structured_outputs(self):
        """Extracts review_decision from structured outputs (DSPy)."""
        agent = GitHubPRAgent()
        analysis_result = {"outputs": {"review_decision": "APPROVE"}}

        decision = agent._extract_review_decision(analysis_result)
        assert decision == "APPROVE"

    def test_extracts_from_ai_analysis_text_colon_format(self):
        """Extracts review_decision from AI text using colon format."""
        agent = GitHubPRAgent()
        analysis_result = {
            "ai_analysis": "## Review\n\nreview_decision: REQUEST_CHANGES\n\nSome feedback"
        }

        decision = agent._extract_review_decision(analysis_result)
        assert decision == "REQUEST_CHANGES"

    def test_extracts_from_ai_analysis_text_bold_format(self):
        """Extracts review_decision from AI text using bold markdown format."""
        agent = GitHubPRAgent()
        analysis_result = {
            "ai_analysis": "## Summary\n\n**Review Decision**: COMMENT\n\nDetails here"
        }

        decision = agent._extract_review_decision(analysis_result)
        assert decision == "COMMENT"

    def test_extracts_case_insensitive(self):
        """Extracts review_decision case-insensitively."""
        agent = GitHubPRAgent()
        analysis_result = {"ai_analysis": "review_decision: approve"}

        decision = agent._extract_review_decision(analysis_result)
        assert decision == "APPROVE"

    def test_returns_none_when_not_found(self):
        """Returns None when no review decision is found."""
        agent = GitHubPRAgent()
        analysis_result = {"ai_analysis": "Some analysis without a decision"}

        decision = agent._extract_review_decision(analysis_result)
        assert decision is None

    def test_returns_none_for_invalid_decision(self):
        """Returns None when decision value is invalid."""
        agent = GitHubPRAgent()
        analysis_result = {"outputs": {"review_decision": "INVALID"}}

        decision = agent._extract_review_decision(analysis_result)
        assert decision is None

    def test_prefers_structured_output_over_text(self):
        """Prefers structured outputs over text parsing."""
        agent = GitHubPRAgent()
        analysis_result = {
            "outputs": {"review_decision": "APPROVE"},
            "ai_analysis": "review_decision: REQUEST_CHANGES",
        }

        decision = agent._extract_review_decision(analysis_result)
        assert decision == "APPROVE"


class TestReviewSubmission:
    """Test PR review submission in send_notifications."""

    @pytest.mark.asyncio
    async def test_submits_review_when_enabled(self):
        """Submits formal review when submit_pr_review is enabled."""
        settings = Settings(
            github_pr_number="42",
            submit_pr_review=True,
        )
        agent = GitHubPRAgent(settings=settings)
        agent.platform_analyzer = MagicMock()
        agent.platform_analyzer.create_review = AsyncMock(
            return_value={"id": 12345, "state": "APPROVED", "html_url": "https://..."}
        )

        analysis_result = {
            "outputs": {"review_decision": "APPROVE"},
            "ai_analysis": "LGTM!",
        }

        await agent.send_notifications({}, analysis_result)

        agent.platform_analyzer.create_review.assert_called_once()
        call_args = agent.platform_analyzer.create_review.call_args
        assert call_args[0][0] == 42  # pr_number
        assert call_args[1]["event"] == "APPROVE"

    @pytest.mark.asyncio
    async def test_falls_back_to_comment_when_no_decision(self):
        """Falls back to comment mode when no review decision found."""
        settings = Settings(
            github_pr_number="42",
            submit_pr_review=True,
            post_pr_comment=True,
        )
        agent = GitHubPRAgent(settings=settings)
        agent.platform_analyzer = MagicMock()
        agent.platform_analyzer.create_review = AsyncMock()
        agent.platform_analyzer.post_pr_comment = AsyncMock()

        analysis_result = {"ai_analysis": "Some feedback without decision"}

        await agent.send_notifications({}, analysis_result)

        agent.platform_analyzer.create_review.assert_not_called()
        agent.platform_analyzer.post_pr_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_comment_mode_when_review_disabled(self):
        """Uses comment mode when submit_pr_review is disabled."""
        settings = Settings(
            github_pr_number="42",
            submit_pr_review=False,
            post_pr_comment=True,
        )
        agent = GitHubPRAgent(settings=settings)
        agent.platform_analyzer = MagicMock()
        agent.platform_analyzer.create_review = AsyncMock()
        agent.platform_analyzer.post_pr_comment = AsyncMock()

        analysis_result = {
            "outputs": {"review_decision": "APPROVE"},
            "ai_analysis": "LGTM!",
        }

        await agent.send_notifications({}, analysis_result)

        agent.platform_analyzer.create_review.assert_not_called()
        agent.platform_analyzer.post_pr_comment.assert_called_once()
