"""
Unit tests for security modules.
"""
import time
import hmac
import hashlib
import pytest
from unittest.mock import patch, MagicMock


class TestSlackRequestVerifier:
    """Tests for SlackRequestVerifier."""

    def test_verify_valid_signature(self):
        """Test verification of a valid Slack signature."""
        from src.security.signature import SlackRequestVerifier

        signing_secret = "test-secret"
        verifier = SlackRequestVerifier(signing_secret)

        timestamp = str(int(time.time()))
        body = b'{"test": "data"}'

        # Generate valid signature
        sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
        expected_sig = 'v0=' + hmac.new(
            signing_secret.encode('utf-8'),
            sig_basestring.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        is_valid, error = verifier.verify_request(body, timestamp, expected_sig)

        assert is_valid is True
        assert error is None

    def test_reject_invalid_signature(self):
        """Test rejection of invalid signature."""
        from src.security.signature import SlackRequestVerifier

        verifier = SlackRequestVerifier("test-secret")
        timestamp = str(int(time.time()))
        body = b'{"test": "data"}'

        is_valid, error = verifier.verify_request(body, timestamp, "v0=invalid")

        assert is_valid is False
        assert error == "Invalid signature"

    def test_reject_old_timestamp(self):
        """Test rejection of requests with old timestamps."""
        from src.security.signature import SlackRequestVerifier

        verifier = SlackRequestVerifier("test-secret")
        old_timestamp = str(int(time.time()) - 600)  # 10 minutes ago
        body = b'{"test": "data"}'

        is_valid, error = verifier.verify_request(body, old_timestamp, "v0=test")

        assert is_valid is False
        assert "too old" in error

    def test_reject_missing_headers(self):
        """Test rejection when headers are missing."""
        from src.security.signature import SlackRequestVerifier

        verifier = SlackRequestVerifier("test-secret")
        body = b'{"test": "data"}'

        is_valid, error = verifier.verify_request(body, "", "")

        assert is_valid is False
        assert "Missing timestamp or signature" in error


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_allows_requests_under_limit(self):
        """Test that requests under the limit are allowed."""
        from src.security.rate_limiter import RateLimiter

        limiter = RateLimiter(max_requests=5, window_seconds=60)

        for i in range(5):
            allowed, retry_after = limiter.is_allowed("user1")
            assert allowed is True
            assert retry_after == 0

    def test_blocks_requests_over_limit(self):
        """Test that requests over the limit are blocked."""
        from src.security.rate_limiter import RateLimiter

        limiter = RateLimiter(max_requests=3, window_seconds=60)

        # Use up the limit
        for _ in range(3):
            limiter.is_allowed("user1")

        # Next request should be blocked
        allowed, retry_after = limiter.is_allowed("user1")
        assert allowed is False
        assert retry_after > 0

    def test_different_users_have_separate_limits(self):
        """Test that rate limits are per-user."""
        from src.security.rate_limiter import RateLimiter

        limiter = RateLimiter(max_requests=2, window_seconds=60)

        # User 1 uses their limit
        limiter.is_allowed("user1")
        limiter.is_allowed("user1")
        allowed1, _ = limiter.is_allowed("user1")

        # User 2 should still have their limit
        allowed2, _ = limiter.is_allowed("user2")

        assert allowed1 is False
        assert allowed2 is True

    def test_get_remaining(self):
        """Test getting remaining requests."""
        from src.security.rate_limiter import RateLimiter

        limiter = RateLimiter(max_requests=5, window_seconds=60)

        assert limiter.get_remaining("user1") == 5

        limiter.is_allowed("user1")
        limiter.is_allowed("user1")

        assert limiter.get_remaining("user1") == 3


class TestMessageDeduplicator:
    """Tests for MessageDeduplicator."""

    def test_first_message_not_duplicate(self):
        """Test that first occurrence is not a duplicate."""
        from src.security.rate_limiter import MessageDeduplicator

        dedup = MessageDeduplicator(ttl_seconds=300)

        is_dup = dedup.is_duplicate("C123", "1234567890.123")

        assert is_dup is False

    def test_second_message_is_duplicate(self):
        """Test that second occurrence is a duplicate."""
        from src.security.rate_limiter import MessageDeduplicator

        dedup = MessageDeduplicator(ttl_seconds=300)

        dedup.is_duplicate("C123", "1234567890.123")
        is_dup = dedup.is_duplicate("C123", "1234567890.123")

        assert is_dup is True

    def test_different_messages_not_duplicates(self):
        """Test that different messages are not duplicates."""
        from src.security.rate_limiter import MessageDeduplicator

        dedup = MessageDeduplicator(ttl_seconds=300)

        dedup.is_duplicate("C123", "1234567890.123")
        is_dup = dedup.is_duplicate("C123", "1234567890.456")

        assert is_dup is False


class TestInputSanitizer:
    """Tests for InputSanitizer."""

    def test_sanitize_removes_dangerous_chars(self):
        """Test that dangerous characters are removed."""
        from src.security.sanitizer import InputSanitizer

        result = InputSanitizer.sanitize_freshservice_query("John'; DROP TABLE users;--")

        assert "'" not in result
        assert ";" not in result
        assert "DROP" in result  # Only special chars removed

    def test_sanitize_truncates_long_input(self):
        """Test that long inputs are truncated."""
        from src.security.sanitizer import InputSanitizer

        long_input = "a" * 200
        result = InputSanitizer.sanitize_freshservice_query(long_input)

        assert len(result) == 100

    def test_sanitize_handles_empty_input(self):
        """Test handling of empty input."""
        from src.security.sanitizer import InputSanitizer

        assert InputSanitizer.sanitize_freshservice_query("") == ""
        assert InputSanitizer.sanitize_freshservice_query(None) is None
