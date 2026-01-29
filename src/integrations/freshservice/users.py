"""
Freshservice user-related operations.
"""
import logging
import urllib.parse
from typing import Dict, List, Any, Optional
import requests

from .client import FreshserviceClient
from src.security import InputSanitizer
from src.integrations.base_tools import retry_on_failure


class UserOperations(FreshserviceClient):
    """Handles user lookups and searches in Freshservice."""

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def get_user_by_email(self, email: str) -> Dict[str, Any]:
        """
        Finds a requester or agent by email to get their ID.

        Args:
            email: The email address to search for

        Returns:
            Dictionary with user information including id, first_name, last_name, type, email

        Raises:
            ValueError: If user not found or configuration missing
        """
        self._ensure_configured()

        # Input validation
        if not email or not isinstance(email, str):
            raise ValueError("Email must be a non-empty string")
        if "@" not in email:
            raise ValueError(f"Invalid email format: {email}")

        # Search Requesters
        encoded_email = urllib.parse.quote(email)
        url = f"{self.base_url}/requesters?email={encoded_email}"

        try:
            response = requests.get(
                url, auth=self._get_auth(), headers=self._get_headers(), timeout=10
            )

            if response.status_code == 200:
                requesters = response.json().get("requesters", [])
                if requesters:
                    user = requesters[0]
                    return {
                        "id": user["id"],
                        "first_name": user["first_name"],
                        "last_name": user["last_name"],
                        "type": "requester",
                        "email": user["primary_email"],
                    }
        except requests.RequestException as e:
            logging.error(f"Error searching requesters: {e}")
            raise ValueError(f"Failed to search for user: {str(e)}")

        # If not found, try Agents
        url_agent = f"{self.base_url}/agents?email={encoded_email}"

        try:
            response_agent = requests.get(
                url_agent, auth=self._get_auth(), headers=self._get_headers(), timeout=10
            )

            if response_agent.status_code == 200:
                agents = response_agent.json().get("agents", [])
                if agents:
                    agent = agents[0]
                    return {
                        "id": agent["id"],
                        "first_name": agent["first_name"],
                        "last_name": agent["last_name"],
                        "type": "agent",
                        "email": agent["email"],
                    }
        except requests.RequestException as e:
            logging.error(f"Error searching agents: {e}")
            raise ValueError(f"Failed to search for agent: {str(e)}")

        raise ValueError(f"User with email '{email}' not found.")

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def get_user_by_name(
        self, first_name: Optional[str] = None, last_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for users by first and/or last name.

        Args:
            first_name: Optional first name to search for
            last_name: Optional last name to search for

        Returns:
            List of matching user dictionaries with id, first_name, last_name, type, email

        Raises:
            ValueError: If neither name provided or configuration missing
        """
        self._ensure_configured()

        # Input validation
        if not first_name and not last_name:
            raise ValueError("Must provide at least first_name or last_name")

        # SECURITY: Sanitize inputs to prevent query injection
        sanitized_first = (
            InputSanitizer.sanitize_freshservice_query(first_name)
            if first_name
            else None
        )
        sanitized_last = (
            InputSanitizer.sanitize_freshservice_query(last_name) if last_name else None
        )

        # Re-check after sanitization
        if not sanitized_first and not sanitized_last:
            raise ValueError("Invalid name input after sanitization")

        # Build search query with sanitized values
        query_parts = []
        if sanitized_first:
            query_parts.append(f"first_name:'{sanitized_first}'")
        if sanitized_last:
            query_parts.append(f"last_name:'{sanitized_last}'")

        query = " AND ".join(query_parts)
        encoded_query = urllib.parse.quote(query)

        results = []

        # Search Requesters
        url = f'{self.base_url}/requesters?query="{encoded_query}"'

        try:
            response = requests.get(
                url, auth=self._get_auth(), headers=self._get_headers(), timeout=10
            )

            if response.status_code == 200:
                requesters = response.json().get("requesters", [])
                for user in requesters:
                    results.append(
                        {
                            "id": user["id"],
                            "first_name": user["first_name"],
                            "last_name": user["last_name"],
                            "type": "requester",
                            "email": user["primary_email"],
                        }
                    )
        except requests.RequestException as e:
            logging.error(f"Error searching requesters by name: {e}")

        # Search Agents
        url_agent = f'{self.base_url}/agents?query="{encoded_query}"'

        try:
            response_agent = requests.get(
                url_agent, auth=self._get_auth(), headers=self._get_headers(), timeout=10
            )

            if response_agent.status_code == 200:
                agents = response_agent.json().get("agents", [])
                for agent in agents:
                    results.append(
                        {
                            "id": agent["id"],
                            "first_name": agent["first_name"],
                            "last_name": agent["last_name"],
                            "type": "agent",
                            "email": agent["email"],
                        }
                    )
        except requests.RequestException as e:
            logging.error(f"Error searching agents by name: {e}")

        if not results:
            name_str = f"{first_name or ''} {last_name or ''}".strip()
            raise ValueError(f"No users found matching name '{name_str}'")

        return results[:10]  # Limit to 10 results
