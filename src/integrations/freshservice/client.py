"""
Freshservice API client with authentication and base configuration.
"""
import logging
from typing import Dict
from src.config import Config


class FreshserviceClient:
    """Base client for Freshservice API interactions."""

    def __init__(self):
        """Initialize Freshservice client with configuration."""
        self.domain = Config.FRESHSERVICE_DOMAIN
        self.api_key = Config.FRESHSERVICE_API_KEY

        if not self.domain or not self.api_key:
            logging.warning("Freshservice not configured. Tools will return errors.")

    def _get_headers(self) -> Dict[str, str]:
        """Get standard headers for Freshservice API."""
        return {"Content-Type": "application/json"}

    def _get_auth(self) -> tuple:
        """Get authentication tuple for Freshservice API."""
        return (self.api_key, "X")

    def _ensure_configured(self) -> None:
        """Raise error if Freshservice is not configured."""
        if not self.domain or not self.api_key:
            raise ValueError(
                "Freshservice configuration missing "
                "(FRESHSERVICE_DOMAIN and FRESHSERVICE_API_KEY required)."
            )

    @property
    def base_url(self) -> str:
        """Get the base URL for API requests."""
        return f"https://{self.domain}/api/v2"
