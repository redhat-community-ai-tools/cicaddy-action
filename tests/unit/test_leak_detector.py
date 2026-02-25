"""Tests for LeakDetector secret redaction."""

from unittest.mock import MagicMock


class TestLeakDetector:
    """Test secret detection and redaction."""

    def test_sanitize_empty_text(self):
        from cicaddy_github.security.leak_detector import LeakDetector

        detector = LeakDetector()
        assert detector.sanitize_text("") == ""
        assert detector.sanitize_text(None) is None

    def test_sanitize_text_without_secrets(self):
        from cicaddy_github.security.leak_detector import LeakDetector

        detector = LeakDetector()
        text = "This is a normal text without any secrets."
        assert detector.sanitize_text(text) == text

    def test_detect_secrets_returns_list(self):
        from cicaddy_github.security.leak_detector import LeakDetector

        detector = LeakDetector()
        result = detector._detect_secrets("normal text")
        assert isinstance(result, list)

    def test_find_secret_positions_with_value(self):
        from cicaddy_github.security.leak_detector import LeakDetector

        detector = LeakDetector()
        mock_secret = MagicMock()
        mock_secret.secret_value = "test_secret"

        positions = detector._find_secret_positions("key=test_secret", mock_secret)
        assert len(positions) == 1
        assert positions[0] == (4, 15)

    def test_find_secret_positions_multiple_occurrences(self):
        from cicaddy_github.security.leak_detector import LeakDetector

        detector = LeakDetector()
        mock_secret = MagicMock()
        mock_secret.secret_value = "abc"

        positions = detector._find_secret_positions("abc def abc", mock_secret)
        assert len(positions) == 2

    def test_find_secret_positions_no_match(self):
        from cicaddy_github.security.leak_detector import LeakDetector

        detector = LeakDetector()
        mock_secret = MagicMock()
        mock_secret.secret_value = "not_here"

        positions = detector._find_secret_positions("some other text", mock_secret)
        assert len(positions) == 0
