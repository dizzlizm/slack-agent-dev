"""
Custom exceptions for the Slack bot application.
"""


class BotException(Exception):
    """Base exception for all bot-related errors."""

    def __init__(self, message: str, user_friendly_message: str = None):
        super().__init__(message)
        self.user_friendly_message = user_friendly_message or message


class AuthorizationError(BotException):
    """Raised when a user is not authorized to perform an action."""

    def __init__(self, user_id: str):
        super().__init__(
            f"User {user_id} is not authorized",
            "Permission denied. You are not authorized to perform this action."
        )
        self.user_id = user_id


class IntegrationNotConfiguredError(BotException):
    """Raised when a required integration is not configured."""

    def __init__(self, integration_name: str):
        super().__init__(
            f"{integration_name} integration is not configured",
            f"Error: {integration_name} integration is not configured by the admin."
        )
        self.integration_name = integration_name


class InvalidCommandError(BotException):
    """Raised when a command is malformed or invalid."""

    def __init__(self, message: str, usage_hint: str = None):
        user_msg = message
        if usage_hint:
            user_msg += f"\n\nUsage: `{usage_hint}`"
        super().__init__(message, user_msg)


class StorageError(BotException):
    """Raised when there's an error with storage operations."""

    def __init__(self, operation: str, details: str):
        super().__init__(
            f"Storage error during {operation}: {details}",
            "A database error occurred. Please try again later."
        )


class ExternalAPIError(BotException):
    """Raised when an external API call fails."""

    def __init__(self, service_name: str, status_code: int = None, details: str = ""):
        message = f"Error calling {service_name}"
        if status_code:
            message += f" (Status {status_code})"
        if details:
            message += f": {details}"

        super().__init__(
            message,
            f"Error communicating with {service_name}. Please try again later."
        )
        self.service_name = service_name
        self.status_code = status_code


class RateLimitError(BotException):
    """Raised when a rate limit is exceeded."""

    def __init__(self, retry_after: int):
        super().__init__(
            f"Rate limit exceeded, retry after {retry_after}s",
            f"You're making requests too quickly. Please wait {retry_after} seconds."
        )
        self.retry_after = retry_after


class SessionNotFoundError(BotException):
    """Raised when a triage session is not found."""

    def __init__(self, channel_id: str, thread_ts: str):
        super().__init__(
            f"Session not found: {channel_id}-{thread_ts}",
            "Session not found or already completed."
        )
