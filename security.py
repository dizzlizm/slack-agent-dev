"""
Security utilities for the Slack bot.
Includes request verification, rate limiting, and message deduplication.
"""
import hashlib
import hmac
import logging
import time
from typing import Dict, Optional, Tuple
from cachetools import TTLCache
import threading

from config import Config


class SlackRequestVerifier:
    """
    Verifies Slack request signatures using HMAC-SHA256.

    Slack signs all requests with a signature computed from:
    - The signing secret
    - The request timestamp
    - The request body

    This prevents attackers from forging requests to the bot.
    """

    # Maximum age of a request (5 minutes) to prevent replay attacks
    MAX_REQUEST_AGE_SECONDS = 300

    def __init__(self, signing_secret: str):
        """
        Initialize the verifier with the Slack signing secret.

        Args:
            signing_secret: The Slack app's signing secret
        """
        self.signing_secret = signing_secret

    def verify_request(
        self,
        body: bytes,
        timestamp: str,
        signature: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify that a request came from Slack.

        Args:
            body: The raw request body (bytes)
            timestamp: The X-Slack-Request-Timestamp header value
            signature: The X-Slack-Signature header value

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not timestamp or not signature:
            return False, "Missing timestamp or signature headers"

        # Check timestamp to prevent replay attacks
        try:
            request_timestamp = int(timestamp)
            current_timestamp = int(time.time())

            if abs(current_timestamp - request_timestamp) > self.MAX_REQUEST_AGE_SECONDS:
                return False, f"Request timestamp too old (>{self.MAX_REQUEST_AGE_SECONDS}s)"
        except ValueError:
            return False, "Invalid timestamp format"

        # Compute expected signature
        sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
        expected_signature = 'v0=' + hmac.new(
            self.signing_secret.encode('utf-8'),
            sig_basestring.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(expected_signature, signature):
            return False, "Invalid signature"

        return True, None


class RateLimiter:
    """
    Per-user rate limiter using a sliding window algorithm.

    Prevents individual users from overwhelming the bot with requests,
    which could exhaust API quotas (Gemini, Freshservice, etc.).
    """

    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: int = 60
    ):
        """
        Initialize the rate limiter.

        Args:
            max_requests: Maximum requests allowed per user per window
            window_seconds: Size of the sliding window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds

        # Store request timestamps per user
        # Key: user_id, Value: list of timestamps
        self._requests: Dict[str, list] = {}
        self._lock = threading.Lock()

    def is_allowed(self, user_id: str) -> Tuple[bool, int]:
        """
        Check if a user is allowed to make a request.

        Args:
            user_id: The user identifier

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        current_time = time.time()
        window_start = current_time - self.window_seconds

        with self._lock:
            # Get or create request list for user
            if user_id not in self._requests:
                self._requests[user_id] = []

            # Remove old requests outside the window
            self._requests[user_id] = [
                ts for ts in self._requests[user_id]
                if ts > window_start
            ]

            # Check if under limit
            if len(self._requests[user_id]) >= self.max_requests:
                # Calculate retry-after (when oldest request expires)
                oldest = min(self._requests[user_id])
                retry_after = int(oldest + self.window_seconds - current_time) + 1
                return False, max(1, retry_after)

            # Record this request
            self._requests[user_id].append(current_time)
            return True, 0

    def get_remaining(self, user_id: str) -> int:
        """
        Get remaining requests for a user in the current window.

        Args:
            user_id: The user identifier

        Returns:
            Number of remaining requests
        """
        current_time = time.time()
        window_start = current_time - self.window_seconds

        with self._lock:
            if user_id not in self._requests:
                return self.max_requests

            # Count requests in current window
            current_requests = len([
                ts for ts in self._requests[user_id]
                if ts > window_start
            ])

            return max(0, self.max_requests - current_requests)


class MessageDeduplicator:
    """
    Prevents processing duplicate Slack events.

    Slack may send duplicate events during retries. This class uses
    a TTL cache to track recently processed messages and reject duplicates.
    """

    def __init__(self, ttl_seconds: int = 300, max_size: int = 10000):
        """
        Initialize the deduplicator.

        Args:
            ttl_seconds: How long to remember message IDs (default 5 minutes)
            max_size: Maximum number of message IDs to track
        """
        self._cache = TTLCache(maxsize=max_size, ttl=ttl_seconds)
        self._lock = threading.Lock()

    def is_duplicate(self, channel_id: str, message_ts: str) -> bool:
        """
        Check if a message has already been processed.

        Args:
            channel_id: The channel ID
            message_ts: The message timestamp

        Returns:
            True if this is a duplicate, False if it's new
        """
        message_key = f"{channel_id}:{message_ts}"

        with self._lock:
            if message_key in self._cache:
                logging.debug(f"Duplicate message detected: {message_key}")
                return True

            # Mark as seen
            self._cache[message_key] = True
            return False

    def clear(self) -> None:
        """Clear all tracked messages."""
        with self._lock:
            self._cache.clear()


class InputSanitizer:
    """
    Sanitizes user input to prevent injection attacks.

    Used primarily for inputs that will be embedded in API queries
    (e.g., Freshservice search queries).
    """

    # Characters that could be used for query injection in Freshservice
    FRESHSERVICE_DANGEROUS_CHARS = ["'", '"', ":", ";", "(", ")", "[", "]", "{", "}", "\\"]

    @classmethod
    def sanitize_freshservice_query(cls, value: str) -> str:
        """
        Sanitize a value for use in Freshservice API queries.

        Args:
            value: The user-provided value

        Returns:
            Sanitized value safe for query embedding
        """
        if not value:
            return value

        sanitized = value
        for char in cls.FRESHSERVICE_DANGEROUS_CHARS:
            sanitized = sanitized.replace(char, "")

        # Also strip leading/trailing whitespace and limit length
        sanitized = sanitized.strip()[:100]

        return sanitized

    @classmethod
    def sanitize_for_logging(cls, value: str, max_length: int = 200) -> str:
        """
        Sanitize a value for safe logging (remove potential secrets).

        Args:
            value: The value to sanitize
            max_length: Maximum length to include

        Returns:
            Sanitized value safe for logging
        """
        if not value:
            return value

        # Truncate long values
        if len(value) > max_length:
            return value[:max_length] + "...[truncated]"

        return value


# Singleton instances (initialized lazily)
_request_verifier: Optional[SlackRequestVerifier] = None
_rate_limiter: Optional[RateLimiter] = None
_message_deduplicator: Optional[MessageDeduplicator] = None


def get_request_verifier() -> SlackRequestVerifier:
    """Get or create the singleton request verifier."""
    global _request_verifier
    if _request_verifier is None:
        _request_verifier = SlackRequestVerifier(Config.SLACK_SIGNING_SECRET)
    return _request_verifier


def get_rate_limiter() -> RateLimiter:
    """Get or create the singleton rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(
            max_requests=Config.RATE_LIMIT_REQUESTS,
            window_seconds=Config.RATE_LIMIT_WINDOW_SECONDS
        )
    return _rate_limiter


def get_message_deduplicator() -> MessageDeduplicator:
    """Get or create the singleton message deduplicator."""
    global _message_deduplicator
    if _message_deduplicator is None:
        _message_deduplicator = MessageDeduplicator(
            ttl_seconds=Config.MESSAGE_DEDUP_TTL_SECONDS
        )
    return _message_deduplicator
