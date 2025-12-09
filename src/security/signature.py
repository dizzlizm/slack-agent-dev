"""
Slack request signature verification.
"""
import hashlib
import hmac
import time
import logging
from typing import Tuple, Optional

from src.config import Config


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

    def __init__(self, signing_secret: str = None):
        """
        Initialize the verifier with the Slack signing secret.

        Args:
            signing_secret: The Slack app's signing secret (defaults to Config)
        """
        self.signing_secret = signing_secret or Config.SLACK_SIGNING_SECRET

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
        body_str = body.decode('utf-8') if isinstance(body, bytes) else body
        sig_basestring = f"v0:{timestamp}:{body_str}"
        expected_signature = 'v0=' + hmac.new(
            self.signing_secret.encode('utf-8'),
            sig_basestring.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(expected_signature, signature):
            return False, "Invalid signature"

        return True, None


# Singleton instance
_verifier: Optional[SlackRequestVerifier] = None


def get_request_verifier() -> SlackRequestVerifier:
    """Get or create the singleton request verifier."""
    global _verifier
    if _verifier is None:
        _verifier = SlackRequestVerifier()
    return _verifier
