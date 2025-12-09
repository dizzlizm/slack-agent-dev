"""
Configuration management for the Slack bot.
Validates all required environment variables at startup.
"""
import os
import logging
from typing import Optional, List


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""
    pass


class Config:
    """Centralized configuration management."""

    # Slack Configuration
    SLACK_BOT_TOKEN: str
    SLACK_BOT_USER_ID: str
    SLACK_SIGNING_SECRET: str  # Required for request verification
    MONITORED_SLACK_CHANNEL_IDS: List[str]

    # Security Settings
    RATE_LIMIT_REQUESTS: int = 10  # Max requests per user per window
    RATE_LIMIT_WINDOW_SECONDS: int = 60  # Window size in seconds
    MESSAGE_DEDUP_TTL_SECONDS: int = 300  # 5 minutes for message deduplication
    
    # Azure Configuration
    AZURE_STORAGE_CONNECTION_STRING: str
    AUTH_TABLE_NAME: str = "AuthorizedUsers"
    CONVO_TABLE_NAME: str = "ConversationHistory"
    TRIAGE_TABLE_NAME: str = "ActiveTriageSessions"

    # Gemini Configuration
    GEMINI_API_KEY: Optional[str] = None
    
    # MCP Server Configuration
    MCP_TOOL_SERVER_URL: Optional[str] = None

    # Freshservice Configuration (for legacy direct API access)
    FRESH_DOMAIN: Optional[str] = None
    FRESH_API_KEY: Optional[str] = None

    # Freshservice Configuration (for MCP tools)
    FRESHSERVICE_DOMAIN: Optional[str] = None
    FRESHSERVICE_API_KEY: Optional[str] = None
    
    # Intune Configuration
    INTUNE_REBOOT_WEBHOOK_URL: Optional[str] = None
    
    # Application Settings
    MAX_CONVERSATION_HISTORY: int = 20
    TRIAGE_SESSION_TIMEOUT_HOURS: int = 24
    REQUEST_TIMEOUT_SECONDS: int = 30
    GEMINI_MODEL_TRIAGE: str = "gemini-2.5-flash"
    GEMINI_MODEL_ASK: str = "gemini-2.5-flash"
    GEMINI_MODEL_TICKET: str = "gemini-2.5-flash"
    
    @classmethod
    def load(cls) -> None:
        """
        Load and validate all configuration from environment variables.
        Raises ConfigurationError if required variables are missing.
        """
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
            errors.append("SLACK_SIGNING_SECRET is required for request verification")

        # Parse monitored channels
        monitored_channels_str = os.environ.get("MONITORED_SLACK_CHANNEL_IDS", "")
        cls.MONITORED_SLACK_CHANNEL_IDS = [
            cid.strip() for cid in monitored_channels_str.split(',') if cid.strip()
        ]
        
        # Required Azure configuration
        cls.AZURE_STORAGE_CONNECTION_STRING = os.environ.get("AzureWebJobsStorage", "")
        if not cls.AZURE_STORAGE_CONNECTION_STRING:
            errors.append("AzureWebJobsStorage is required")
        
        # Optional integrations
        cls.GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
        cls.FRESH_DOMAIN = os.environ.get("FRESH_DOMAIN")
        cls.FRESH_API_KEY = os.environ.get("FRESH_API_KEY")
        cls.FRESHSERVICE_DOMAIN = os.environ.get("FRESHSERVICE_DOMAIN", cls.FRESH_DOMAIN)  # Fallback to FRESH_DOMAIN
        cls.FRESHSERVICE_API_KEY = os.environ.get("FRESHSERVICE_API_KEY", cls.FRESH_API_KEY)  # Fallback to FRESH_API_KEY
        cls.INTUNE_REBOOT_WEBHOOK_URL = os.environ.get("INTUNE_REBOOT_WEBHOOK_URL")
        cls.MCP_TOOL_SERVER_URL = os.environ.get("MCP_TOOL_SERVER_URL")
        
        # Optional overrides
        if max_history := os.environ.get("MAX_CONVERSATION_HISTORY"):
            try:
                cls.MAX_CONVERSATION_HISTORY = int(max_history)
            except ValueError:
                logging.warning(f"Invalid MAX_CONVERSATION_HISTORY value: {max_history}")
        
        if timeout := os.environ.get("TRIAGE_SESSION_TIMEOUT_HOURS"):
            try:
                cls.TRIAGE_SESSION_TIMEOUT_HOURS = int(timeout)
            except ValueError:
                logging.warning(f"Invalid TRIAGE_SESSION_TIMEOUT_HOURS value: {timeout}")
        
        # Raise if critical config is missing
        if errors:
            raise ConfigurationError(
                "Missing required configuration:\n" + "\n".join(f"  - {err}" for err in errors)
            )
        
        # Log warnings for optional features
        if not cls.GEMINI_API_KEY:
            logging.warning("GEMINI_API_KEY not set. AI features will be disabled.")

        if not cls.FRESH_DOMAIN or not cls.FRESH_API_KEY:
            logging.warning("FRESH_DOMAIN or FRESH_API_KEY not set. Freshservice features disabled.")
        
        if not cls.INTUNE_REBOOT_WEBHOOK_URL:
            logging.warning("INTUNE_REBOOT_WEBHOOK_URL not set. Intune features disabled.")
        
        logging.info("Configuration loaded successfully")

    @classmethod
    def is_gemini_enabled(cls) -> bool:
        """Check if Gemini integration is configured."""
        return bool(cls.GEMINI_API_KEY)
    
    @classmethod
    def is_freshservice_enabled(cls) -> bool:
        """Check if Freshservice integration is configured."""
        return bool(cls.FRESH_DOMAIN and cls.FRESH_API_KEY)
    
    @classmethod
    def is_intune_enabled(cls) -> bool:
        """Check if Intune integration is configured."""
        return bool(cls.INTUNE_REBOOT_WEBHOOK_URL)
