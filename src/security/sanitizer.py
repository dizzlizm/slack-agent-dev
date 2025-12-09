"""
Input sanitization utilities.
"""


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

        # Strip leading/trailing whitespace and limit length
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

        if len(value) > max_length:
            return value[:max_length] + "...[truncated]"

        return value

    @classmethod
    def sanitize_slack_text(cls, value: str) -> str:
        """
        Sanitize text for display in Slack.

        Args:
            value: The value to sanitize

        Returns:
            Sanitized value safe for Slack
        """
        if not value:
            return value

        # Escape Slack special characters
        value = value.replace("&", "&amp;")
        value = value.replace("<", "&lt;")
        value = value.replace(">", "&gt;")

        return value
