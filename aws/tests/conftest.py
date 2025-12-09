"""
Pytest configuration and fixtures.
"""
import os
import pytest
from unittest.mock import MagicMock, patch

# Set test environment before importing modules
os.environ['ENVIRONMENT'] = 'test'
os.environ['USE_AWS_SECRETS'] = 'false'
os.environ['SLACK_BOT_TOKEN'] = 'xoxb-test-token'
os.environ['SLACK_BOT_USER_ID'] = 'U12345TEST'
os.environ['SLACK_SIGNING_SECRET'] = 'test-signing-secret'


@pytest.fixture
def mock_config():
    """Fixture that provides a mocked Config."""
    with patch('src.config.Config') as mock:
        mock.ENVIRONMENT = 'test'
        mock.SLACK_BOT_TOKEN = 'xoxb-test-token'
        mock.SLACK_BOT_USER_ID = 'U12345TEST'
        mock.SLACK_SIGNING_SECRET = 'test-signing-secret'
        mock.AWS_REGION = 'us-east-1'
        mock.DYNAMODB_TABLE_PREFIX = 'test-'
        mock.RATE_LIMIT_REQUESTS = 10
        mock.RATE_LIMIT_WINDOW_SECONDS = 60
        mock.MESSAGE_DEDUP_TTL_SECONDS = 300
        mock.is_gemini_enabled.return_value = False
        mock.is_freshservice_enabled.return_value = False
        mock.is_intune_enabled.return_value = False
        yield mock


@pytest.fixture
def mock_dynamodb_table():
    """Fixture that provides a mocked DynamoDB table."""
    mock_table = MagicMock()
    mock_table.get_item.return_value = {}
    mock_table.put_item.return_value = {}
    mock_table.delete_item.return_value = {}
    mock_table.scan.return_value = {'Items': []}
    return mock_table


@pytest.fixture
def sample_slack_event():
    """Fixture that provides a sample Slack event."""
    return {
        'body': '{"type": "event_callback", "event": {"type": "message", "user": "U123", "channel": "C123", "text": "hello", "ts": "1234567890.123456"}}',
        'headers': {
            'x-slack-request-timestamp': '1234567890',
            'x-slack-signature': 'v0=test-signature'
        },
        'isBase64Encoded': False
    }


@pytest.fixture
def sample_url_verification():
    """Fixture that provides a URL verification challenge."""
    return {
        'body': '{"type": "url_verification", "challenge": "test-challenge-string"}',
        'headers': {},
        'isBase64Encoded': False
    }
