"""
Freshservice MCP Tools - Core Logic
Provides Freshservice integration tools that can be called directly or via HTTP.
"""
import logging
import urllib.parse
from typing import Optional, Dict, List, Any
import requests

from config import Config


class FreshserviceTools:
    """
    Core Freshservice tool implementations.
    These can be called directly (for internal use) or via JSON-RPC (for external MCP).
    """

    def __init__(self):
        """Initialize Freshservice tools with configuration."""
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
            raise ValueError("Freshservice configuration missing (FRESHSERVICE_DOMAIN and FRESHSERVICE_API_KEY required).")

    # --- TOOL IMPLEMENTATIONS ---

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

        # Search Requesters
        encoded_email = urllib.parse.quote(email)
        url = f"https://{self.domain}/api/v2/requesters?email={encoded_email}"

        try:
            response = requests.get(url, auth=self._get_auth(), headers=self._get_headers(), timeout=10)

            if response.status_code == 200:
                requesters = response.json().get("requesters", [])
                if requesters:
                    user = requesters[0]
                    return {
                        "id": user["id"],
                        "first_name": user["first_name"],
                        "last_name": user["last_name"],
                        "type": "requester",
                        "email": user["primary_email"]
                    }
        except requests.RequestException as e:
            logging.error(f"Error searching requesters: {e}")
            raise ValueError(f"Failed to search for user: {str(e)}")

        # If not found, try Agents
        url_agent = f"https://{self.domain}/api/v2/agents?email={encoded_email}"

        try:
            response_agent = requests.get(url_agent, auth=self._get_auth(), headers=self._get_headers(), timeout=10)

            if response_agent.status_code == 200:
                agents = response_agent.json().get("agents", [])
                if agents:
                    agent = agents[0]
                    return {
                        "id": agent["id"],
                        "first_name": agent["first_name"],
                        "last_name": agent["last_name"],
                        "type": "agent",
                        "email": agent["email"]
                    }
        except requests.RequestException as e:
            logging.error(f"Error searching agents: {e}")
            raise ValueError(f"Failed to search for agent: {str(e)}")

        raise ValueError(f"User with email '{email}' not found.")

    def list_tickets(self, requester_id: Optional[int] = None, agent_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Lists tickets filtered by requester or agent.

        Args:
            requester_id: Optional requester (user) ID
            agent_id: Optional agent (tech) ID

        Returns:
            List of ticket dictionaries with id, subject, status, priority, created_at

        Raises:
            ValueError: If neither requester_id nor agent_id provided, or configuration missing
        """
        self._ensure_configured()

        if not requester_id and not agent_id:
            raise ValueError("Must provide either requester_id or agent_id.")

        query_params = []
        if requester_id:
            query_params.append(f"requester_id={requester_id}")
        if agent_id:
            query_params.append(f"agent_id={agent_id}")

        url = f"https://{self.domain}/api/v2/tickets?{'&'.join(query_params)}&include=stats"

        try:
            response = requests.get(url, auth=self._get_auth(), headers=self._get_headers(), timeout=10)
            response.raise_for_status()

            tickets = response.json().get("tickets", [])

            # Return simplified ticket info (limit to 10 for performance)
            return [
                {
                    "id": t["id"],
                    "subject": t["subject"],
                    "status": t["status"],  # 2: Open, 3: Pending, 4: Resolved, 5: Closed
                    "priority": t["priority"],
                    "created_at": t["created_at"]
                }
                for t in tickets[:10]
            ]
        except requests.RequestException as e:
            logging.error(f"Error listing tickets: {e}")
            raise ValueError(f"Failed to list tickets: {str(e)}")

    def list_assets(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Lists assets assigned to a specific user.

        Args:
            user_id: The numeric ID of the user

        Returns:
            List of asset dictionaries with id, name, asset_tag, asset_type

        Raises:
            ValueError: If configuration missing
        """
        self._ensure_configured()

        url = f"https://{self.domain}/api/v2/assets?filter=\"user_id:{user_id}\""

        try:
            response = requests.get(url, auth=self._get_auth(), headers=self._get_headers(), timeout=10)
            response.raise_for_status()

            assets = response.json().get("assets", [])

            return [
                {
                    "id": a["id"],
                    "name": a["name"],
                    "asset_tag": a.get("asset_tag"),
                    "asset_type": a.get("asset_type_id")
                }
                for a in assets
            ]
        except requests.RequestException as e:
            logging.error(f"Error listing assets: {e}")
            # Return empty list instead of failing (assets might not be enabled)
            return []

    def list_recent_changes(self) -> List[Dict[str, Any]]:
        """
        Lists recent open changes (useful for checking outages/maintenance).

        Returns:
            List of change dictionaries with id, subject, status, planned_start_date, planned_end_date

        Raises:
            ValueError: If configuration missing
        """
        self._ensure_configured()

        url = f"https://{self.domain}/api/v2/changes?sort_by=created_at&sort_type=desc"

        try:
            response = requests.get(url, auth=self._get_auth(), headers=self._get_headers(), timeout=10)
            response.raise_for_status()

            changes = response.json().get("changes", [])

            # Filter for open changes only (Status 1=Open, 2=Planning, etc.)
            open_changes = [c for c in changes if c.get('status', 999) < 3]

            return [
                {
                    "id": c["id"],
                    "subject": c["subject"],
                    "status": c["status"],
                    "planned_start_date": c.get("planned_start_date"),
                    "planned_end_date": c.get("planned_end_date")
                }
                for c in open_changes[:10]
            ]
        except requests.RequestException as e:
            logging.error(f"Error listing changes: {e}")
            # Return empty list instead of failing
            return []

    # --- TOOL DISPATCH ---

    def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """
        Execute a tool by name with given parameters.
        This is used for JSON-RPC dispatch and internal calls.

        Args:
            tool_name: The name of the tool to execute
            params: Dictionary of parameters

        Returns:
            The tool result

        Raises:
            ValueError: If tool not found or execution fails
        """
        tool_map = {
            "get_user_by_email": self.get_user_by_email,
            "list_tickets": self.list_tickets,
            "list_assets": self.list_assets,
            "list_recent_changes": self.list_recent_changes
        }

        if tool_name not in tool_map:
            raise ValueError(f"Tool '{tool_name}' not found. Available tools: {list(tool_map.keys())}")

        tool_func = tool_map[tool_name]

        try:
            # Call the tool with unpacked parameters
            result = tool_func(**params)
            return result
        except TypeError as e:
            raise ValueError(f"Invalid parameters for tool '{tool_name}': {str(e)}")


# Singleton instance
_freshservice_tools: Optional[FreshserviceTools] = None


def get_freshservice_tools() -> FreshserviceTools:
    """Get or create the singleton FreshserviceTools instance."""
    global _freshservice_tools
    if _freshservice_tools is None:
        _freshservice_tools = FreshserviceTools()
    return _freshservice_tools
