"""
Freshservice change management operations.
"""
import logging
from typing import Dict, List, Any
import requests

from .client import FreshserviceClient
from src.integrations.base_tools import retry_on_failure


class ChangeOperations(FreshserviceClient):
    """Handles change management operations in Freshservice."""

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def list_recent_changes(self) -> List[Dict[str, Any]]:
        """
        Lists recent open changes (useful for checking outages/maintenance).

        Returns:
            List of change dictionaries with id, subject, status, planned_start_date, planned_end_date

        Raises:
            ValueError: If configuration missing
        """
        self._ensure_configured()

        url = f"{self.base_url}/changes?sort_by=created_at&sort_type=desc"

        try:
            response = requests.get(
                url, auth=self._get_auth(), headers=self._get_headers(), timeout=10
            )
            response.raise_for_status()

            changes = response.json().get("changes", [])

            # Filter for open changes only (Status 1=Open, 2=Planning, etc.)
            open_changes = [c for c in changes if c.get("status", 999) < 3]

            return [
                {
                    "id": c["id"],
                    "subject": c["subject"],
                    "status": c["status"],
                    "planned_start_date": c.get("planned_start_date"),
                    "planned_end_date": c.get("planned_end_date"),
                }
                for c in open_changes[:10]
            ]
        except requests.RequestException as e:
            logging.error(f"Error listing changes: {e}")
            # Return empty list instead of failing
            return []
