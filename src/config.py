"""
Environment-aware configuration management.
Supports both AWS (Secrets Manager) and local development.
"""
import os
import json
import logging
from typing import Optional, List


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""
    pass


class Config:
    """
    Centralized configuration management with multi-environment support.

    Supports:
    - AWS Secrets Manager (production)
    - Environment variables (local development)
    - Multiple environments (dev, prod)
    """

    # Environment
    ENVIRONMENT: str = "dev"  # 'dev' or 'prod'

    # Slack Configuration
    SLACK_BOT_TOKEN: str = ""
    SLACK_BOT_USER_ID: str = ""
    SLACK_SIGNING_SECRET: str = ""
    MONITORED_SLACK_CHANNEL_IDS: List[str] = []

    # Security Settings
    RATE_LIMIT_REQUESTS: int = 10
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    MESSAGE_DEDUP_TTL_SECONDS: int = 300

    # AWS Configuration
    AWS_REGION: str = "us-east-1"
    DYNAMODB_TABLE_PREFIX: str = ""  # Set based on environment

    # Gemini Configuration
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL_TRIAGE: str = "gemini-2.5-flash"
    GEMINI_MODEL_ASK: str = "gemini-2.5-flash"
    GEMINI_MODEL_TICKET: str = "gemini-2.5-flash"

    # Freshservice Configuration
    FRESHSERVICE_DOMAIN: Optional[str] = None
    FRESHSERVICE_API_KEY: Optional[str] = None

    # Intune Configuration
    INTUNE_REBOOT_WEBHOOK_URL: Optional[str] = None

    # Application Settings
    APP_VERSION: str = "2.0.0"
    MAX_CONVERSATION_HISTORY: int = 20
    TRIAGE_SESSION_TIMEOUT_HOURS: int = 24
    REQUEST_TIMEOUT_SECONDS: int = 30
    CONVERSATION_HISTORY_TTL_DAYS: int = 30
    AUTH_CACHE_TTL_SECONDS: int = 300

    _loaded = False

    @classmethod
    def load(cls) -> None:
        """
        Load configuration from environment variables or AWS Secrets Manager.
        """
        if cls._loaded:
            return

        # Determine environment
        cls.ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
        cls.AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
        cls.DYNAMODB_TABLE_PREFIX = f"slack-agent-{cls.ENVIRONMENT}-"

        logging.info(f"Loading configuration for environment: {cls.ENVIRONMENT}")

        # Check if we should use AWS Secrets Manager
        use_secrets_manager = os.environ.get("USE_AWS_SECRETS", "false").lower() == "true"

        if use_secrets_manager:
            cls._load_from_secrets_manager()
        else:
            cls._load_from_environment()

        cls._loaded = True
        logging.info(f"Configuration loaded successfully for {cls.ENVIRONMENT}")

    @classmethod
    def _load_from_secrets_manager(cls) -> None:
        """Load secrets from AWS Secrets Manager."""
        try:
            import boto3
            from botocore.exceptions import ClientError

            client = boto3.client('secretsmanager', region_name=cls.AWS_REGION)
            secret_name = f"slack-agent-systems-bot/{cls.ENVIRONMENT}"

            try:
                response = client.get_secret_value(SecretId=secret_name)
                secrets = json.loads(response['SecretString'])

                # Map secrets to config
                cls.SLACK_BOT_TOKEN = secrets.get("SLACK_BOT_TOKEN", "")
                cls.SLACK_BOT_USER_ID = secrets.get("SLACK_BOT_USER_ID", "")
                cls.SLACK_SIGNING_SECRET = secrets.get("SLACK_SIGNING_SECRET", "")
                cls.GEMINI_API_KEY = secrets.get("GEMINI_API_KEY")
                cls.FRESHSERVICE_DOMAIN = secrets.get("FRESHSERVICE_DOMAIN")
                cls.FRESHSERVICE_API_KEY = secrets.get("FRESHSERVICE_API_KEY")
                cls.INTUNE_REBOOT_WEBHOOK_URL = secrets.get("INTUNE_REBOOT_WEBHOOK_URL")

                # Validate required secrets are present
                errors = []
                if not cls.SLACK_BOT_TOKEN:
                    errors.append("SLACK_BOT_TOKEN is missing or empty in Secrets Manager")
                if not cls.SLACK_BOT_USER_ID:
                    errors.append("SLACK_BOT_USER_ID is missing or empty in Secrets Manager")
                if not cls.SLACK_SIGNING_SECRET:
                    errors.append("SLACK_SIGNING_SECRET is missing or empty in Secrets Manager")

                if errors:
                    raise ConfigurationError(
                        f"Missing required secrets in {secret_name}:\n" +
                        "\n".join(f"  - {err}" for err in errors)
                    )

                logging.info(f"Loaded secrets from AWS Secrets Manager: {secret_name}")

            except ClientError as e:
                logging.error(f"Failed to load secrets from AWS: {e}")
                raise ConfigurationError(f"Failed to load secrets: {e}")

        except ImportError:
            logging.warning("boto3 not available, falling back to environment variables")
            cls._load_from_environment()

        # Load non-secret config from environment
        cls._load_non_secrets_from_environment()

    @classmethod
    def _load_from_environment(cls) -> None:
        """Load all configuration from environment variables."""
        errors = []

        # Required Slack configuration
        cls.SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
        if not cls.SLACK_BOT_TOKEN:
            errors.append("SLACK_BOT_TOKEN is required")

        cls.SLACK_BOT_USER_ID = os.environ.get("SLACK_BOT_USER_ID", "")
        if not cls.SLACK_BOT_USER_ID:
            errors.append("SLACK_BOT_USER_ID is required")

        cls.SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")
        if not cls.SLACK_SIGNING_SECRET:
            errors.append("SLACK_SIGNING_SECRET is required")

        # Optional integrations
        cls.GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
        cls.FRESHSERVICE_DOMAIN = os.environ.get("FRESHSERVICE_DOMAIN")
        cls.FRESHSERVICE_API_KEY = os.environ.get("FRESHSERVICE_API_KEY")
        cls.INTUNE_REBOOT_WEBHOOK_URL = os.environ.get("INTUNE_REBOOT_WEBHOOK_URL")

        cls._load_non_secrets_from_environment()

        if errors:
            raise ConfigurationError(
                "Missing required configuration:\n" + "\n".join(f"  - {err}" for err in errors)
            )

    @classmethod
    def _load_non_secrets_from_environment(cls) -> None:
        """Load non-secret configuration from environment variables."""
        # Parse monitored channels
        monitored_channels_str = os.environ.get("MONITORED_SLACK_CHANNEL_IDS", "")
        cls.MONITORED_SLACK_CHANNEL_IDS = [
            cid.strip() for cid in monitored_channels_str.split(',') if cid.strip()
        ]

        # Rate limiting settings
        if rate_limit := os.environ.get("RATE_LIMIT_REQUESTS"):
            try:
                cls.RATE_LIMIT_REQUESTS = int(rate_limit)
            except ValueError:
                pass

        if rate_window := os.environ.get("RATE_LIMIT_WINDOW_SECONDS"):
            try:
                cls.RATE_LIMIT_WINDOW_SECONDS = int(rate_window)
            except ValueError:
                pass

        # Application settings
        if max_history := os.environ.get("MAX_CONVERSATION_HISTORY"):
            try:
                cls.MAX_CONVERSATION_HISTORY = int(max_history)
            except ValueError:
                pass

        if timeout := os.environ.get("TRIAGE_SESSION_TIMEOUT_HOURS"):
            try:
                cls.TRIAGE_SESSION_TIMEOUT_HOURS = int(timeout)
            except ValueError:
                pass

    @classmethod
    def is_gemini_enabled(cls) -> bool:
        """Check if Gemini integration is configured."""
        return bool(cls.GEMINI_API_KEY)

    @classmethod
    def is_freshservice_enabled(cls) -> bool:
        """Check if Freshservice integration is configured."""
        return bool(cls.FRESHSERVICE_DOMAIN and cls.FRESHSERVICE_API_KEY)

    @classmethod
    def is_intune_enabled(cls) -> bool:
        """Check if Intune integration is configured."""
        return bool(cls.INTUNE_REBOOT_WEBHOOK_URL)

    @classmethod
    def get_table_name(cls, base_name: str) -> str:
        """
        Get the environment-prefixed DynamoDB table name.

        Args:
            base_name: Base table name (e.g., 'AuthorizedUsers')

        Returns:
            Prefixed table name (e.g., 'slack-agent-dev-AuthorizedUsers')
        """
        return f"{cls.DYNAMODB_TABLE_PREFIX}{base_name}"


class ConfigValidator:
    """
    Validate configuration at startup to fail fast.
    
    This class checks all required configuration values and provides
    clear error messages when configuration is missing or invalid.
    """

    # Required secrets for basic operation
    REQUIRED_SECRETS = {
        'SLACK_BOT_TOKEN': 'Slack bot token',
        'SLACK_SIGNING_SECRET': 'Slack signing secret for request verification',
        'GEMINI_API_KEY': 'Google Gemini API key for AI functionality'
    }

    # Optional secrets that enable additional features
    OPTIONAL_SECRETS = {
        'FRESHSERVICE_API_KEY': 'FreshService integration',
        'FRESHSERVICE_DOMAIN': 'FreshService domain',
        'INTUNE_REBOOT_WEBHOOK_URL': 'Intune device management'
    }

    @classmethod
    def validate_all(cls) -> List[str]:
        """
        Validate all configuration and return warnings.
        
        Returns:
            List of warning messages for optional missing configuration
            
        Raises:
            ConfigurationError: If required configuration is missing
        """
        from src.exceptions import ConfigurationError
        
        warnings = []

        # Check required secrets
        for secret_name, description in cls.REQUIRED_SECRETS.items():
            value = getattr(Config, secret_name, None)
            if not value or (isinstance(value, str) and not value.strip()):
                raise ConfigurationError(
                    f"Missing required configuration: {secret_name} ({description})"
                )

        # Check optional secrets and collect warnings
        for secret_name, description in cls.OPTIONAL_SECRETS.items():
            value = getattr(Config, secret_name, None)
            if not value or (isinstance(value, str) and not value.strip()):
                warnings.append(
                    f"Optional configuration missing: {secret_name} ({description} will be disabled)"
                )

        # Validate monitored channels if specified
        if Config.MONITORED_SLACK_CHANNEL_IDS:
            if not isinstance(Config.MONITORED_SLACK_CHANNEL_IDS, list):
                raise ConfigurationError(
                    "MONITORED_SLACK_CHANNEL_IDS must be a list"
                )
            for channel_id in Config.MONITORED_SLACK_CHANNEL_IDS:
                if not isinstance(channel_id, str) or not channel_id.strip():
                    raise ConfigurationError(
                        f"Invalid channel ID in MONITORED_SLACK_CHANNEL_IDS: {channel_id}"
                    )

        # Validate numeric settings
        if Config.RATE_LIMIT_REQUESTS <= 0:
            raise ConfigurationError("RATE_LIMIT_REQUESTS must be positive")
        
        if Config.RATE_LIMIT_WINDOW_SECONDS <= 0:
            raise ConfigurationError("RATE_LIMIT_WINDOW_SECONDS must be positive")
        
        if Config.MAX_CONVERSATION_HISTORY <= 0:
            raise ConfigurationError("MAX_CONVERSATION_HISTORY must be positive")

        # Validate FreshService configuration consistency
        if Config.FRESHSERVICE_API_KEY and not Config.FRESHSERVICE_DOMAIN:
            raise ConfigurationError(
                "FRESHSERVICE_API_KEY provided but FRESHSERVICE_DOMAIN is missing"
            )
        if Config.FRESHSERVICE_DOMAIN and not Config.FRESHSERVICE_API_KEY:
            raise ConfigurationError(
                "FRESHSERVICE_DOMAIN provided but FRESHSERVICE_API_KEY is missing"
            )

        return warnings

    @classmethod
    def validate_and_log(cls) -> None:
        """
        Validate configuration and log results.
        
        This is the recommended method to call during application startup.
        It validates configuration, logs warnings, and raises errors for
        critical missing configuration.
        """
        logging.info("Validating configuration...")
        
        try:
            warnings = cls.validate_all()
            
            logging.info("✓ Configuration validation passed")
            
            # Log enabled integrations
            integrations = []
            if Config.is_gemini_enabled():
                integrations.append("Gemini")
            if Config.is_freshservice_enabled():
                integrations.append("FreshService")
            if Config.is_intune_enabled():
                integrations.append("Intune")
            
            logging.info(f"Enabled integrations: {', '.join(integrations) if integrations else 'None'}")
            
            # Log warnings for optional missing configuration
            for warning in warnings:
                logging.warning(f"⚠ {warning}")
                
        except Exception as e:
            logging.error(f"✗ Configuration validation failed: {e}")
            raise
