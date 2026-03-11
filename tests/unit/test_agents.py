"""Tests for dedent_code_blocks in agents module."""

from cicaddy_github.github_integration.agents import dedent_code_blocks


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
