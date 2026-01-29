"""
Custom exceptions for the Slack bot application.

This module defines all custom exceptions used throughout the application.
All exceptions inherit from BotException and include user-friendly messages
for display in Slack conversations.
"""
from typing import Optional


class BotException(Exception):
    """Base exception for all bot-related errors."""

    def __init__(self, message: str, user_friendly_message: Optional[str] = None) -> None:
        super().__init__(message)
        self.user_friendly_message = user_friendly_message or message


class AuthorizationError(BotException):
    """Raised when a user is not authorized to perform an action."""

    def __init__(self, user_id: str) -> None:
        super().__init__(
            f"User {user_id} is not authorized",
            "Permission denied. You are not authorized to perform this action."
        )
        self.user_id = user_id


class IntegrationNotConfiguredError(BotException):
    """Raised when a required integration is not configured."""

    def __init__(self, integration_name: str) -> None:
        super().__init__(
            f"{integration_name} integration is not configured",
            f"Error: {integration_name} integration is not configured by the admin."
        )
        self.integration_name = integration_name


class InvalidCommandError(BotException):
    """Raised when a command is malformed or invalid."""

    def __init__(self, message: str, usage_hint: Optional[str] = None) -> None:
        user_msg = message
        if usage_hint:
            user_msg += f"\n\nUsage: `{usage_hint}`"
        super().__init__(message, user_msg)


class StorageError(BotException):
    """Raised when there's an error with storage operations."""

    def __init__(self, operation: str, details: str) -> None:
        super().__init__(
            f"Storage error during {operation}: {details}",
            "A database error occurred. Please try again later."
        )


class ExternalAPIError(BotException):
    """Raised when an external API call fails."""

    def __init__(self, service_name: str, status_code: Optional[int] = None, details: str = "") -> None:
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

    def __init__(self, retry_after: int) -> None:
        super().__init__(
            f"Rate limit exceeded, retry after {retry_after}s",
            f"You're making requests too quickly. Please wait {retry_after} seconds."
        )
        self.retry_after = retry_after


class SessionNotFoundError(BotException):
    """Raised when a triage session is not found."""

    def __init__(self, channel_id: str, thread_ts: str) -> None:
        super().__init__(
            f"Session not found: {channel_id}-{thread_ts}",
            "Session not found or already completed."
        )


class ToolExecutionError(BotException):
    """Raised when an MCP tool execution fails."""

    def __init__(self, tool_name: str, message: str, recoverable: bool = True) -> None:
        super().__init__(
            f"Tool '{tool_name}' failed: {message}",
            f"Error executing {tool_name}. {message if recoverable else 'Please contact support.'}"
        )
        self.tool_name = tool_name
        self.recoverable = recoverable


class ValidationError(BotException):
    """Raised when input validation fails."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(
            f"Validation failed for '{field}': {message}",
            f"Invalid {field}: {message}"
        )
        self.field = field


class QuotaExceededError(BotException):
    """Raised when an API quota is exceeded."""

    def __init__(self, service: str, retry_after: Optional[int] = None) -> None:
        message = f"{service} quota exceeded"
        user_message = f"{service} service quota exceeded. "
        if retry_after:
            user_message += f"Please try again in {retry_after} seconds."
        else:
            user_message += "Please try again later."

        super().__init__(message, user_message)
        self.service = service
        self.retry_after = retry_after


class ConfigurationError(BotException):
    """Raised when there's a configuration error."""

    def __init__(self, message: str) -> None:
        super().__init__(
            f"Configuration error: {message}",
            "System configuration error. Please contact your administrator."
        )
