"""
Tests for configuration management and validation.
"""
import pytest
from unittest.mock import patch, MagicMock
from src.config import Config, ConfigValidator
from src.exceptions import ConfigurationError


class TestConfig:
    """Test configuration loading and management."""

    def test_environment_loading(self):
        """Test environment variable loading."""
        with patch.dict('os.environ', {
            'ENVIRONMENT': 'test',
            'SLACK_BOT_TOKEN': 'xoxb-test-token',
            'SLACK_SIGNING_SECRET': 'test-secret',
            'GEMINI_API_KEY': 'test-api-key'
        }):
            Config._loaded = False
            Config.load()
            assert Config.ENVIRONMENT == 'test'
            assert Config.SLACK_BOT_TOKEN == 'xoxb-test-token'
            assert Config.SLACK_SIGNING_SECRET == 'test-secret'
            assert Config.GEMINI_API_KEY == 'test-api-key'

    def test_table_name_prefixing(self):
        """Test DynamoDB table name prefixing."""
        Config.DYNAMODB_TABLE_PREFIX = 'slack-agent-dev-'
        assert Config.get_table_name('Users') == 'slack-agent-dev-Users'
        assert Config.get_table_name('Conversations') == 'slack-agent-dev-Conversations'

    def test_integration_enabled_checks(self):
        """Test integration enabled checks."""
        Config.GEMINI_API_KEY = 'test-key'
        assert Config.is_gemini_enabled() == True

        Config.GEMINI_API_KEY = None
        assert Config.is_gemini_enabled() == False

        Config.GEMINI_API_KEY = ''
        assert Config.is_gemini_enabled() == False

    def test_freshservice_enabled_check(self):
        """Test FreshService integration check requires both domain and API key."""
        Config.FRESHSERVICE_DOMAIN = 'test.freshservice.com'
        Config.FRESHSERVICE_API_KEY = 'test-key'
        assert Config.is_freshservice_enabled() == True

        Config.FRESHSERVICE_API_KEY = None
        assert Config.is_freshservice_enabled() == False

        Config.FRESHSERVICE_DOMAIN = None
        Config.FRESHSERVICE_API_KEY = 'test-key'
        assert Config.is_freshservice_enabled() == False


class TestConfigValidator:
    """Test configuration validation."""

    def setup_method(self):
        """Reset Config before each test."""
        Config._loaded = False
        Config.SLACK_BOT_TOKEN = ''
        Config.SLACK_SIGNING_SECRET = ''
        Config.GEMINI_API_KEY = ''
        Config.FRESHSERVICE_DOMAIN = None
        Config.FRESHSERVICE_API_KEY = None
        Config.INTUNE_REBOOT_WEBHOOK_URL = None
        Config.MONITORED_SLACK_CHANNEL_IDS = []
        Config.RATE_LIMIT_REQUESTS = 10
        Config.RATE_LIMIT_WINDOW_SECONDS = 60
        Config.MAX_CONVERSATION_HISTORY = 20

    def test_missing_required_config_raises_error(self):
        """Test that missing required config raises ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            ConfigValidator.validate_all()
        assert 'SLACK_BOT_TOKEN' in str(exc_info.value)

    def test_valid_config_returns_warnings_for_optional(self):
        """Test that valid required config returns warnings for optional."""
        Config.SLACK_BOT_TOKEN = 'xoxb-test'
        Config.SLACK_SIGNING_SECRET = 'test-secret'
        Config.GEMINI_API_KEY = 'test-key'

        warnings = ConfigValidator.validate_all()
        
        # Should have warnings for optional missing config
        assert any('FRESHSERVICE_API_KEY' in w for w in warnings)
        assert any('INTUNE_REBOOT_WEBHOOK_URL' in w for w in warnings)

    def test_freshservice_partial_config_raises_error(self):
        """Test that partial FreshService config raises error."""
        Config.SLACK_BOT_TOKEN = 'xoxb-test'
        Config.SLACK_SIGNING_SECRET = 'test-secret'
        Config.GEMINI_API_KEY = 'test-key'
        Config.FRESHSERVICE_API_KEY = 'test-api-key'
        # Missing FRESHSERVICE_DOMAIN

        with pytest.raises(ConfigurationError) as exc_info:
            ConfigValidator.validate_all()
        assert 'FRESHSERVICE_DOMAIN' in str(exc_info.value)

    def test_invalid_rate_limit_raises_error(self):
        """Test that invalid rate limit raises error."""
        Config.SLACK_BOT_TOKEN = 'xoxb-test'
        Config.SLACK_SIGNING_SECRET = 'test-secret'
        Config.GEMINI_API_KEY = 'test-key'
        Config.RATE_LIMIT_REQUESTS = 0  # Invalid

        with pytest.raises(ConfigurationError) as exc_info:
            ConfigValidator.validate_all()
        assert 'RATE_LIMIT_REQUESTS' in str(exc_info.value)

    def test_invalid_channel_ids_raises_error(self):
        """Test that invalid channel IDs raise error."""
        Config.SLACK_BOT_TOKEN = 'xoxb-test'
        Config.SLACK_SIGNING_SECRET = 'test-secret'
        Config.GEMINI_API_KEY = 'test-key'
        Config.MONITORED_SLACK_CHANNEL_IDS = ['C123', '']  # Empty string invalid

        with pytest.raises(ConfigurationError) as exc_info:
            ConfigValidator.validate_all()
        assert 'channel ID' in str(exc_info.value).lower()

    def test_validate_and_log_success(self, caplog):
        """Test validate_and_log logs success and warnings."""
        Config.SLACK_BOT_TOKEN = 'xoxb-test'
        Config.SLACK_SIGNING_SECRET = 'test-secret'
        Config.GEMINI_API_KEY = 'test-key'

        ConfigValidator.validate_and_log()

        assert 'Configuration validation passed' in caplog.text
        assert 'Enabled integrations' in caplog.text

    def test_validate_and_log_failure(self, caplog):
        """Test validate_and_log logs failure and re-raises."""
        # Missing required config
        with pytest.raises(ConfigurationError):
            ConfigValidator.validate_and_log()

        assert 'Configuration validation failed' in caplog.text

    def test_empty_string_treated_as_missing(self):
        """Test that empty strings are treated as missing config."""
        Config.SLACK_BOT_TOKEN = ''  # Empty string
        Config.SLACK_SIGNING_SECRET = 'test-secret'
        Config.GEMINI_API_KEY = 'test-key'

        with pytest.raises(ConfigurationError) as exc_info:
            ConfigValidator.validate_all()
        assert 'SLACK_BOT_TOKEN' in str(exc_info.value)

    def test_whitespace_string_treated_as_missing(self):
        """Test that whitespace-only strings are treated as missing."""
        Config.SLACK_BOT_TOKEN = '   '  # Whitespace only
        Config.SLACK_SIGNING_SECRET = 'test-secret'
        Config.GEMINI_API_KEY = 'test-key'

        with pytest.raises(ConfigurationError) as exc_info:
            ConfigValidator.validate_all()
        assert 'SLACK_BOT_TOKEN' in str(exc_info.value)
