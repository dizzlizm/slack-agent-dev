"""
Per-user rate limiting using sliding window algorithm.
"""
import time
import threading
import logging
from typing import Dict, Tuple, Optional
from cachetools import TTLCache

from src.config import Config


class RateLimiter:
    """
    Per-user rate limiter using a sliding window algorithm.

    Prevents individual users from overwhelming the bot with requests,
    which could exhaust API quotas (Gemini, Freshservice, etc.).
    """

    def __init__(
        self,
        max_requests: int = None,
        window_seconds: int = None
    ):
        """
        Initialize the rate limiter.

        Args:
            max_requests: Maximum requests allowed per user per window
            window_seconds: Size of the sliding window in seconds
        """
        self.max_requests = max_requests or Config.RATE_LIMIT_REQUESTS
        self.window_seconds = window_seconds or Config.RATE_LIMIT_WINDOW_SECONDS

        # Store request timestamps per user
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
                oldest = min(self._requests[user_id])
                retry_after = int(oldest + self.window_seconds - current_time) + 1
                logging.debug(f"Rate limit exceeded for {user_id}, retry after {retry_after}s")
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

            current_requests = len([
                ts for ts in self._requests[user_id]
                if ts > window_start
            ])

            return max(0, self.max_requests - current_requests)

    def reset(self, user_id: str = None) -> None:
        """
        Reset rate limit for a user or all users.

        Args:
            user_id: Optional specific user to reset (None = all users)
        """
        with self._lock:
            if user_id:
                self._requests.pop(user_id, None)
            else:
                self._requests.clear()


class MessageDeduplicator:
    """
    Prevents processing duplicate Slack events.

    Slack may send duplicate events during retries. This class uses
    a TTL cache to track recently processed messages and reject duplicates.
    """

    def __init__(self, ttl_seconds: int = None, max_size: int = 10000):
        """
        Initialize the deduplicator.

        Args:
            ttl_seconds: How long to remember message IDs
            max_size: Maximum number of message IDs to track
        """
        ttl = ttl_seconds or Config.MESSAGE_DEDUP_TTL_SECONDS
        self._cache = TTLCache(maxsize=max_size, ttl=ttl)
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

            self._cache[message_key] = True
            return False

    def clear(self) -> None:
        """Clear all tracked messages."""
        with self._lock:
            self._cache.clear()


# Singleton instances
_rate_limiter: Optional[RateLimiter] = None
_deduplicator: Optional[MessageDeduplicator] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the singleton rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def get_message_deduplicator() -> MessageDeduplicator:
    """Get or create the singleton message deduplicator."""
    global _deduplicator
    if _deduplicator is None:
        _deduplicator = MessageDeduplicator()
    return _deduplicator
