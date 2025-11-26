"""
Unified MCP Tools - Core Logic
Provides integration tools for Freshservice, Meraki, and Intune.
All tools can be called directly (internal) or via HTTP (JSON-RPC).
"""
import logging
import urllib.parse
import time
from typing import Optional, Dict, List, Any
import requests

from config import Config


def retry_on_failure(max_retries=3, backoff_factor=1.0):
    """
    Decorator to retry a function on transient failures.

    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff (seconds)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        # Check if it's a retryable error (5xx, timeouts, connection errors)
                        should_retry = False
                        if isinstance(e, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
                            should_retry = True
                        elif hasattr(e, 'response') and e.response is not None:
                            if 500 <= e.response.status_code < 600:
                                should_retry = True

                        if should_retry:
                            sleep_time = backoff_factor * (2 ** attempt)
                            logging.warning(f"API call failed (attempt {attempt + 1}/{max_retries}), retrying in {sleep_time}s: {e}")
                            time.sleep(sleep_time)
                        else:
                            # Non-retryable error, raise immediately
                            raise
                    else:
                        logging.error(f"API call failed after {max_retries} attempts: {e}")
                        raise
            raise last_exception
        return wrapper
    return decorator


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

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def get_user_by_name(self, first_name: Optional[str] = None, last_name: Optional[str] = None) -> List[Dict[str, Any]]:
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

        # Build search query
        query_parts = []
        if first_name:
            query_parts.append(f"first_name:'{first_name}'")
        if last_name:
            query_parts.append(f"last_name:'{last_name}'")

        query = " AND ".join(query_parts)
        encoded_query = urllib.parse.quote(query)

        results = []

        # Search Requesters
        url = f"https://{self.domain}/api/v2/requesters?query=\"{encoded_query}\""

        try:
            response = requests.get(url, auth=self._get_auth(), headers=self._get_headers(), timeout=10)

            if response.status_code == 200:
                requesters = response.json().get("requesters", [])
                for user in requesters:
                    results.append({
                        "id": user["id"],
                        "first_name": user["first_name"],
                        "last_name": user["last_name"],
                        "type": "requester",
                        "email": user["primary_email"]
                    })
        except requests.RequestException as e:
            logging.error(f"Error searching requesters by name: {e}")

        # Search Agents
        url_agent = f"https://{self.domain}/api/v2/agents?query=\"{encoded_query}\""

        try:
            response_agent = requests.get(url_agent, auth=self._get_auth(), headers=self._get_headers(), timeout=10)

            if response_agent.status_code == 200:
                agents = response_agent.json().get("agents", [])
                for agent in agents:
                    results.append({
                        "id": agent["id"],
                        "first_name": agent["first_name"],
                        "last_name": agent["last_name"],
                        "type": "agent",
                        "email": agent["email"]
                    })
        except requests.RequestException as e:
            logging.error(f"Error searching agents by name: {e}")

        if not results:
            name_str = f"{first_name or ''} {last_name or ''}".strip()
            raise ValueError(f"No users found matching name '{name_str}'")

        return results[:10]  # Limit to 10 results

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
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

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
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

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def get_ticket_by_id(self, ticket_id: int) -> Dict[str, Any]:
        """
        Get a specific ticket by its ID.

        Args:
            ticket_id: The numeric ticket ID

        Returns:
            Dictionary with ticket details

        Raises:
            ValueError: If ticket not found or configuration missing
        """
        self._ensure_configured()

        url = f"https://{self.domain}/api/v2/tickets/{ticket_id}"

        try:
            response = requests.get(url, auth=self._get_auth(), headers=self._get_headers(), timeout=10)

            if response.status_code == 404:
                raise ValueError(f"Ticket #{ticket_id} not found")

            response.raise_for_status()

            ticket = response.json().get("ticket", {})

            return {
                "id": ticket["id"],
                "subject": ticket["subject"],
                "description": ticket.get("description_text", ""),
                "status": ticket["status"],
                "priority": ticket["priority"],
                "requester_id": ticket.get("requester_id"),
                "agent_id": ticket.get("responder_id"),
                "created_at": ticket["created_at"],
                "updated_at": ticket["updated_at"]
            }
        except requests.RequestException as e:
            logging.error(f"Error getting ticket #{ticket_id}: {e}")
            raise ValueError(f"Failed to get ticket: {str(e)}")

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def get_asset_by_id(self, asset_id: int) -> Dict[str, Any]:
        """
        Get a specific asset by its ID.

        Args:
            asset_id: The numeric asset ID

        Returns:
            Dictionary with asset details

        Raises:
            ValueError: If asset not found or configuration missing
        """
        self._ensure_configured()

        url = f"https://{self.domain}/api/v2/assets/{asset_id}"

        try:
            response = requests.get(url, auth=self._get_auth(), headers=self._get_headers(), timeout=10)

            if response.status_code == 404:
                raise ValueError(f"Asset #{asset_id} not found")

            response.raise_for_status()

            asset = response.json().get("asset", {})

            return {
                "id": asset["id"],
                "name": asset["name"],
                "asset_tag": asset.get("asset_tag"),
                "asset_type_id": asset.get("asset_type_id"),
                "user_id": asset.get("user_id"),
                "location_id": asset.get("location_id"),
                "department_id": asset.get("department_id")
            }
        except requests.RequestException as e:
            logging.error(f"Error getting asset #{asset_id}: {e}")
            raise ValueError(f"Failed to get asset: {str(e)}")

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def create_ticket(
        self,
        subject: str,
        description: str,
        requester_email: str,
        priority: int = 1,
        status: int = 2,
        group_id: Optional[int] = None,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new ticket in Freshservice.

        Args:
            subject: Ticket subject/title
            description: Ticket description
            requester_email: Email of the requester
            priority: Priority level (1=Low, 2=Medium, 3=High, 4=Urgent)
            status: Ticket status (2=Open, 3=Pending, 4=Resolved, 5=Closed)
            group_id: Optional group/queue ID to assign to
            category: Optional category name

        Returns:
            Dictionary with ticket_id and ticket_url

        Raises:
            ValueError: If creation fails or configuration missing
        """
        self._ensure_configured()

        # Input validation
        if not subject or not description or not requester_email:
            raise ValueError("subject, description, and requester_email are required")

        if priority not in [1, 2, 3, 4]:
            raise ValueError("priority must be 1 (Low), 2 (Medium), 3 (High), or 4 (Urgent)")

        # Look up requester ID
        try:
            requester_info = self.get_user_by_email(requester_email)
            requester_id = requester_info["id"]
        except ValueError:
            raise ValueError(f"Could not find user with email {requester_email}")

        url = f"https://{self.domain}/api/v2/tickets"

        payload = {
            "subject": subject,
            "description": description,
            "requester_id": requester_id,
            "priority": priority,
            "status": status
        }

        if group_id:
            payload["group_id"] = group_id

        if category:
            payload["category"] = category

        try:
            response = requests.post(
                url,
                auth=self._get_auth(),
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )
            response.raise_for_status()

            ticket = response.json().get("ticket", {})
            ticket_id = ticket["id"]
            ticket_url = f"https://{self.domain}/a/tickets/{ticket_id}"

            return {
                "ticket_id": ticket_id,
                "ticket_url": ticket_url,
                "subject": ticket["subject"],
                "status": ticket["status"],
                "priority": ticket["priority"]
            }
        except requests.RequestException as e:
            logging.error(f"Error creating ticket: {e}")
            raise ValueError(f"Failed to create ticket: {str(e)}")

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
            "get_user_by_name": self.get_user_by_name,
            "list_tickets": self.list_tickets,
            "list_assets": self.list_assets,
            "list_recent_changes": self.list_recent_changes,
            "get_ticket_by_id": self.get_ticket_by_id,
            "get_asset_by_id": self.get_asset_by_id,
            "create_ticket": self.create_ticket
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


# =========================================================================
# INTUNE TOOLS
# =========================================================================

class IntuneTools:
    """Core Intune tool implementations for device management."""

    def __init__(self):
        """Initialize Intune tools with configuration."""
        self.webhook_url = Config.INTUNE_REBOOT_WEBHOOK_URL

        if not self.webhook_url:
            logging.warning("Intune not configured. Tools will return errors.")

    def _ensure_configured(self) -> None:
        """Raise error if Intune is not configured."""
        if not self.webhook_url:
            raise ValueError("Intune configuration missing (INTUNE_REBOOT_WEBHOOK_URL required).")

    @retry_on_failure(max_retries=2, backoff_factor=2.0)
    def reboot_device(self, serial_number: str) -> Dict[str, Any]:
        """
        Reboot a device via Intune webhook.

        Args:
            serial_number: The device serial number

        Returns:
            Dictionary with reboot result

        Raises:
            ValueError: If configuration missing or operation fails
        """
        self._ensure_configured()

        # Input validation
        if not serial_number or not isinstance(serial_number, str):
            raise ValueError("Serial number must be a non-empty string")

        url = f"{self.webhook_url}&serialNumber={serial_number}"

        try:
            response = requests.post(url, timeout=120)

            if response.status_code == 200:
                return {
                    "success": True,
                    "message": f"Reboot command sent successfully for device {serial_number}",
                    "details": response.text
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to reboot device: HTTP {response.status_code}",
                    "details": response.text
                }

        except requests.exceptions.Timeout:
            raise ValueError("Request timed out after 120 seconds")
        except requests.RequestException as e:
            logging.error(f"Error rebooting device: {e}")
            raise ValueError(f"Failed to reboot device: {str(e)}")


# =========================================================================
# UNIFIED TOOL REGISTRY
# =========================================================================

class UnifiedTools:
    """
    Unified tool registry that combines all available tools.
    This allows Gemini to intelligently route to any backend service.
    """

    def __init__(self):
        """Initialize all tool instances."""
        self.freshservice = FreshserviceTools()
        self.intune = IntuneTools()

    def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """
        Execute any tool by name with given parameters.

        Args:
            tool_name: The name of the tool to execute
            params: Dictionary of parameters

        Returns:
            The tool result

        Raises:
            ValueError: If tool not found or execution fails
        """
        # Freshservice tools
        if tool_name in ["get_user_by_email", "get_user_by_name", "list_tickets", "list_assets", "list_recent_changes",
                         "get_ticket_by_id", "get_asset_by_id", "create_ticket"]:
            return self.freshservice.execute_tool(tool_name, params)

        # Intune tools
        elif tool_name == "reboot_device":
            return self.intune.reboot_device(**params)

        else:
            available = [
                "get_user_by_email", "get_user_by_name", "list_tickets", "list_assets", "list_recent_changes",
                "get_ticket_by_id", "get_asset_by_id", "create_ticket", "reboot_device"
            ]
            raise ValueError(f"Tool '{tool_name}' not found. Available tools: {available}")


# =========================================================================
# SINGLETON INSTANCES
# =========================================================================

_freshservice_tools: Optional[FreshserviceTools] = None
_unified_tools: Optional[UnifiedTools] = None


def get_freshservice_tools() -> FreshserviceTools:
    """Get or create the singleton FreshserviceTools instance."""
    global _freshservice_tools
    if _freshservice_tools is None:
        _freshservice_tools = FreshserviceTools()
    return _freshservice_tools


def get_unified_tools() -> UnifiedTools:
    """Get or create the singleton UnifiedTools instance (all services)."""
    global _unified_tools
    if _unified_tools is None:
        _unified_tools = UnifiedTools()
    return _unified_tools
