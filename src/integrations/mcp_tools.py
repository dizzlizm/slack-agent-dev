"""
Unified MCP Tools - Core Logic
Provides integration tools for Freshservice, Meraki, and Intune.
All tools can be called directly (internal) or via HTTP (JSON-RPC).
"""
import logging
from typing import Optional, Dict, Any
import requests

from src.config import Config
from src.integrations.base_tools import retry_on_failure
from src.integrations.freshservice import FreshserviceTools


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
        if tool_name in [
            # User operations
            "get_user_by_email", "get_user_by_name",
            # Ticket operations  
            "list_tickets", "get_ticket_by_id", "create_ticket",
            "update_ticket", "add_ticket_note", "get_ticket_conversations",
            # Asset operations
            "list_assets", "get_asset_by_id",
            "get_asset_software", "get_asset_contracts",
            # Change operations
            "list_recent_changes",
            # Service Catalog operations
            "list_service_items", "get_service_item", "create_service_request",
            "list_service_categories", "get_service_request_status",
            # Problem Management operations
            "list_problems", "get_problem_by_id", "link_ticket_to_problem",
            "get_problem_tickets", "search_problems",
            # Solution operations
            "list_solution_articles", "get_solution_article", "search_solution_articles",
            "list_solution_categories", "list_solution_folders", "get_popular_articles"
        ]:
            return self.freshservice.execute_tool(tool_name, params)

        # Intune tools
        elif tool_name == "reboot_device":
            return self.intune.reboot_device(**params)

        else:
            available = [
                # User operations
                "get_user_by_email", "get_user_by_name",
                # Ticket operations
                "list_tickets", "get_ticket_by_id", "create_ticket",
                "update_ticket", "add_ticket_note", "get_ticket_conversations",
                # Asset operations
                "list_assets", "get_asset_by_id",
                "get_asset_software", "get_asset_contracts",
                # Change operations
                "list_recent_changes",
                # Service Catalog operations
                "list_service_items", "get_service_item", "create_service_request",
                "list_service_categories", "get_service_request_status",
                # Problem Management operations
                "list_problems", "get_problem_by_id", "link_ticket_to_problem",
                "get_problem_tickets", "search_problems",
                # Solution operations
                "list_solution_articles", "get_solution_article", "search_solution_articles",
                "list_solution_categories", "list_solution_folders", "get_popular_articles",
                # Intune operations
                "reboot_device"
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
