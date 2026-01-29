"""
Tests for custom exception classes.
"""
import pytest
from src.exceptions import (
    BotException,
    AuthorizationError,
    IntegrationNotConfiguredError,
    InvalidCommandError,
    StorageError,
    ExternalAPIError,
    RateLimitError,
    SessionNotFoundError,
    ToolExecutionError,
    ValidationError,
    QuotaExceededError,
    ConfigurationError
)


class TestBotException:
    """Test base BotException."""

    def test_bot_exception_with_message(self):
        """Test BotException with custom message."""
        exc = BotException("Test error")
        assert str(exc) == "Test error"
        assert exc.user_friendly_message == "Test error"

    def test_bot_exception_with_user_friendly_message(self):
        """Test BotException with separate user-friendly message."""
        exc = BotException("Internal error", "Something went wrong")
        assert str(exc) == "Internal error"
        assert exc.user_friendly_message == "Something went wrong"


class TestAuthorizationError:
    """Test AuthorizationError."""

    def test_authorization_error_attributes(self):
        """Test AuthorizationError has user_id attribute."""
        exc = AuthorizationError("U12345")
        assert exc.user_id == "U12345"
        assert "U12345" in str(exc)
        assert "not authorized" in exc.user_friendly_message


class TestIntegrationNotConfiguredError:
    """Test IntegrationNotConfiguredError."""

    def test_integration_not_configured_attributes(self):
        """Test IntegrationNotConfiguredError has integration_name attribute."""
        exc = IntegrationNotConfiguredError("FreshService")
        assert exc.integration_name == "FreshService"
        assert "FreshService" in str(exc)
        assert "not configured" in exc.user_friendly_message


class TestInvalidCommandError:
    """Test InvalidCommandError."""

    def test_invalid_command_without_hint(self):
        """Test InvalidCommandError without usage hint."""
        exc = InvalidCommandError("Unknown command")
        assert "Unknown command" in str(exc)

    def test_invalid_command_with_hint(self):
        """Test InvalidCommandError with usage hint."""
        exc = InvalidCommandError("Missing parameter", "/help <command>")
        assert "Missing parameter" in str(exc)
        assert "/help <command>" in exc.user_friendly_message


class TestStorageError:
    """Test StorageError."""

    def test_storage_error_message(self):
        """Test StorageError message format."""
        exc = StorageError("save", "Connection timeout")
        assert "save" in str(exc)
        assert "Connection timeout" in str(exc)
        assert "database error" in exc.user_friendly_message.lower()


class TestExternalAPIError:
    """Test ExternalAPIError."""

    def test_external_api_error_basic(self):
        """Test ExternalAPIError with just service name."""
        exc = ExternalAPIError("Slack")
        assert exc.service_name == "Slack"
        assert "Slack" in str(exc)
        assert exc.status_code is None

    def test_external_api_error_with_status(self):
        """Test ExternalAPIError with status code."""
        exc = ExternalAPIError("FreshService", status_code=404)
        assert exc.service_name == "FreshService"
        assert exc.status_code == 404
        assert "404" in str(exc)

    def test_external_api_error_with_details(self):
        """Test ExternalAPIError with details."""
        exc = ExternalAPIError("Gemini", details="Rate limit exceeded")
        assert "Rate limit exceeded" in str(exc)


class TestRateLimitError:
    """Test RateLimitError."""

    def test_rate_limit_error_attributes(self):
        """Test RateLimitError has retry_after attribute."""
        exc = RateLimitError(retry_after=60)
        assert exc.retry_after == 60
        assert "60" in str(exc)
        assert "60 seconds" in exc.user_friendly_message


class TestSessionNotFoundError:
    """Test SessionNotFoundError."""

    def test_session_not_found_error(self):
        """Test SessionNotFoundError message."""
        exc = SessionNotFoundError("C123", "1234567890.123456")
        assert "C123" in str(exc)
        assert "1234567890.123456" in str(exc)
        assert "not found" in exc.user_friendly_message


class TestToolExecutionError:
    """Test ToolExecutionError."""

    def test_tool_execution_error_attributes(self):
        """Test ToolExecutionError has tool_name and recoverable attributes."""
        exc = ToolExecutionError("create_ticket", "API timeout", recoverable=True)
        assert exc.tool_name == "create_ticket"
        assert exc.recoverable == True
        assert "create_ticket" in str(exc)
        assert "API timeout" in str(exc)

    def test_tool_execution_error_not_recoverable(self):
        """Test ToolExecutionError with non-recoverable error."""
        exc = ToolExecutionError("reboot_device", "Device not found", recoverable=False)
        assert exc.recoverable == False
        assert "contact support" in exc.user_friendly_message.lower()

    def test_tool_execution_error_default_recoverable(self):
        """Test ToolExecutionError defaults to recoverable=True."""
        exc = ToolExecutionError("list_tickets", "Temporary failure")
        assert exc.recoverable == True


class TestValidationError:
    """Test ValidationError."""

    def test_validation_error_attributes(self):
        """Test ValidationError has field attribute."""
        exc = ValidationError("email", "Invalid format")
        assert exc.field == "email"
        assert "email" in str(exc)
        assert "Invalid format" in str(exc)
        assert "Invalid email" in exc.user_friendly_message


class TestQuotaExceededError:
    """Test QuotaExceededError."""

    def test_quota_exceeded_without_retry_after(self):
        """Test QuotaExceededError without retry_after."""
        exc = QuotaExceededError("Gemini")
        assert exc.service == "Gemini"
        assert exc.retry_after is None
        assert "Gemini" in str(exc)
        assert "try again later" in exc.user_friendly_message.lower()

    def test_quota_exceeded_with_retry_after(self):
        """Test QuotaExceededError with retry_after."""
        exc = QuotaExceededError("FreshService", retry_after=300)
        assert exc.service == "FreshService"
        assert exc.retry_after == 300
        assert "300 seconds" in exc.user_friendly_message


class TestConfigurationError:
    """Test ConfigurationError."""

    def test_configuration_error_message(self):
        """Test ConfigurationError message format."""
        exc = ConfigurationError("Missing API key")
        assert "Missing API key" in str(exc)
        assert "administrator" in exc.user_friendly_message.lower()


class TestExceptionHierarchy:
    """Test exception hierarchy."""

    def test_all_exceptions_inherit_from_bot_exception(self):
        """Test that all custom exceptions inherit from BotException."""
        exceptions = [
            AuthorizationError("U123"),
            IntegrationNotConfiguredError("Test"),
            InvalidCommandError("Test"),
            StorageError("test", "details"),
            ExternalAPIError("Test"),
            RateLimitError(60),
            SessionNotFoundError("C123", "123"),
            ToolExecutionError("test", "msg"),
            ValidationError("field", "msg"),
            QuotaExceededError("service"),
            ConfigurationError("msg")
        ]

        for exc in exceptions:
            assert isinstance(exc, BotException)
            assert isinstance(exc, Exception)

    def test_all_exceptions_have_user_friendly_message(self):
        """Test that all exceptions have user-friendly messages."""
        exceptions = [
            AuthorizationError("U123"),
            IntegrationNotConfiguredError("Test"),
            InvalidCommandError("Test"),
            StorageError("test", "details"),
            ExternalAPIError("Test"),
            RateLimitError(60),
            SessionNotFoundError("C123", "123"),
            ToolExecutionError("test", "msg"),
            ValidationError("field", "msg"),
            QuotaExceededError("service"),
            ConfigurationError("msg")
        ]

        for exc in exceptions:
            assert hasattr(exc, 'user_friendly_message')
            assert exc.user_friendly_message
            assert isinstance(exc.user_friendly_message, str)
