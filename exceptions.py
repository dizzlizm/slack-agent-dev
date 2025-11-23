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
            "⛔️ Permission Denied. You are not authorized to perform this action."
        )
        self.user_id = user_id


class IntegrationNotConfiguredError(BotException):
    """Raised when a required integration is not configured."""
    
    def __init__(self, integration_name: str):
        super().__init__(
            f"{integration_name} integration is not configured",
            f"❌ Error: {integration_name} integration is not configured by the admin."
        )
        self.integration_name = integration_name


class InvalidCommandError(BotException):
    """Raised when a command is malformed or invalid."""
    
    def __init__(self, message: str, usage_hint: str = None):
        user_msg = message
        if usage_hint:
            user_msg += f"\n\n💡 Usage: `{usage_hint}`"
        super().__init__(message, user_msg)


class StorageError(BotException):
    """Raised when there's an error with Azure Table Storage."""
    
    def __init__(self, operation: str, details: str):
        super().__init__(
            f"Storage error during {operation}: {details}",
            f"❌ A database error occurred. Please try again later."
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
            f"❌ Error communicating with {service_name}. Please try again later."
        )
        self.service_name = service_name
        self.status_code = status_code


class TimeoutError(BotException):
    """Raised when an operation times out."""
    
    def __init__(self, operation: str):
        super().__init__(
            f"Timeout during {operation}",
            f"❌ The operation timed out. Please try again."
        )


class SessionNotFoundError(BotException):
    """Raised when a triage session is not found."""
    
    def __init__(self, channel_id: str, thread_ts: str):
        super().__init__(
            f"Session not found: {channel_id}-{thread_ts}",
            "❌ Session not found or already completed."
        )
