"""Tests for agent classes and text formatting helpers."""

from unittest.mock import patch

from cicaddy_github.github_integration.agents import (
    GitHubGoDepReviewAgent,
    GitHubPRAgent,
    GitHubTaskAgent,
    dedent_code_blocks,
    extract_review_verdict,
    strip_markdown_wrapper,
)


class TestAgentType:
    """Test _get_agent_type() returns correct delegation registry type."""

    @patch("cicaddy_github.github_integration.agents.GitHubAnalyzer")
    def test_pr_agent_returns_review_type(self, _mock_analyzer):
        agent = GitHubPRAgent.__new__(GitHubPRAgent)
        assert agent._get_agent_type() == "review"

    @patch("cicaddy_github.github_integration.agents.GitHubAnalyzer")
    def test_go_dep_review_agent_returns_review_type(self, _mock_analyzer):
        agent = GitHubGoDepReviewAgent.__new__(GitHubGoDepReviewAgent)
        assert agent._get_agent_type() == "review"

    @patch("cicaddy_github.github_integration.agents.GitHubAnalyzer")
    def test_task_agent_returns_task_type(self, _mock_analyzer):
        agent = GitHubTaskAgent.__new__(GitHubTaskAgent)
        assert agent._get_agent_type() == "task"


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


class TestExtractReviewVerdict:
    """Test extraction of review verdict from AI analysis output."""

    def test_extracts_approve(self):
        text = "Analysis looks good.\n<!-- VERDICT: APPROVE -->"
        assert extract_review_verdict(text) == "APPROVE"

    def test_extracts_request_changes(self):
        text = "Found bugs.\n<!-- VERDICT: REQUEST_CHANGES -->"
        assert extract_review_verdict(text) == "REQUEST_CHANGES"

    def test_extracts_plain_verdict(self):
        """Verdict without HTML comment wrapper."""
        text = "Analysis.\nVERDICT: APPROVE"
        assert extract_review_verdict(text) == "APPROVE"

    def test_case_insensitive(self):
        text = "Analysis.\n<!-- verdict: request_changes -->"
        assert extract_review_verdict(text) == "REQUEST_CHANGES"

    def test_defaults_to_comment(self):
        """No verdict line returns COMMENT."""
        text = "Just some analysis text without a verdict."
        assert extract_review_verdict(text) == "COMMENT"

    def test_verdict_with_leading_whitespace(self):
        text = "Analysis.\n  <!-- VERDICT: APPROVE -->"
        assert extract_review_verdict(text) == "APPROVE"

    def test_verdict_in_middle_of_text(self):
        text = "Start.\n<!-- VERDICT: REQUEST_CHANGES -->\nEnd."
        assert extract_review_verdict(text) == "REQUEST_CHANGES"
