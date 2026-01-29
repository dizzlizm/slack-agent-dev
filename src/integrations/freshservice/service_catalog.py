"""
Freshservice Service Catalog operations.

The Service Catalog in FreshService provides pre-configured service request types
with built-in workflows, approvals, and automations. This module leverages those
existing workflows rather than duplicating work.
"""
import logging
from typing import Dict, List, Any, Optional
import requests

from .client import FreshserviceClient
from src.integrations.base_tools import retry_on_failure


class ServiceCatalogOperations(FreshserviceClient):
    """Handles Service Catalog operations in Freshservice."""

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def list_service_items(
        self,
        category_id: Optional[int] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        List available service catalog items.

        Service items represent predefined request types with workflows
        (e.g., "New Laptop", "Software License", "Building Access").
        Each has its own custom fields, approval flows, and automation.

        Args:
            category_id: Optional category ID to filter by
            limit: Maximum number of items to return (default 20)

        Returns:
            List of service item dictionaries with id, name, description, category

        Raises:
            ValueError: If retrieval fails or configuration missing
        """
        self._ensure_configured()

        url = f"{self.base_url}/service_catalog/items"

        params = {}
        if category_id:
            params["category_id"] = category_id

        try:
            response = requests.get(
                url,
                auth=self._get_auth(),
                headers=self._get_headers(),
                params=params,
                timeout=10
            )
            response.raise_for_status()

            items = response.json().get("service_items", [])

            # Return formatted items (limit results)
            return [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "description": item.get("short_description", ""),
                    "category_id": item.get("category_id"),
                    "category_name": item.get("category_name", ""),
                    "cost": item.get("cost", 0),
                    "delivery_time": item.get("delivery_time"),  # In hours
                    "icon_url": item.get("icon_url"),
                    "visibility": item.get("visibility", "public")  # public/internal
                }
                for item in items[:limit]
            ]
        except requests.RequestException as e:
            logging.error(f"Error listing service items: {e}")
            raise ValueError(f"Failed to list service catalog items: {str(e)}")

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def search_service_items(
        self,
        search_term: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search service catalog items by keyword.

        Args:
            search_term: The keywords to search for in item names/descriptions
            limit: Maximum number of items to return (default 20)

        Returns:
            List of matching service item dictionaries

        Raises:
            ValueError: If search_term is empty or retrieval fails
        """
        self._ensure_configured()

        if not search_term or not search_term.strip():
            raise ValueError("Search term cannot be empty")

        # Freshservice API v2 uses /service_catalog/items/search endpoint
        url = f"{self.base_url}/service_catalog/items/search?search_term={requests.utils.quote(search_term)}&per_page={limit}"

        try:
            response = requests.get(
                url,
                auth=self._get_auth(),
                headers=self._get_headers(),
                timeout=10
            )
            response.raise_for_status()

            items = response.json().get("service_items", [])

            return [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "description": item.get("short_description", ""),
                    "category_id": item.get("category_id"),
                    "category_name": item.get("category_name", ""),
                    "cost": item.get("cost", 0),
                    "delivery_time": item.get("delivery_time"),
                    "icon_url": item.get("icon_url"),
                    "visibility": item.get("visibility", "public")
                }
                for item in items[:limit]
            ]
        except requests.RequestException as e:
            logging.error(f"Error searching service items: {e}")
            raise ValueError(f"Failed to search service catalog items: {str(e)}")

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def get_service_item(
        self,
        item_id: int
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific service catalog item.
        
        Includes custom fields, approval requirements, and workflow details.
        
        Args:
            item_id: The service item ID
            
        Returns:
            Dictionary with complete item details including custom_fields schema
            
        Raises:
            ValueError: If item not found or retrieval fails
        """
        self._ensure_configured()
        
        url = f"{self.base_url}/service_catalog/items/{item_id}"
        
        try:
            response = requests.get(
                url,
                auth=self._get_auth(),
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 404:
                raise ValueError(f"Service item #{item_id} not found")
            
            response.raise_for_status()
            
            item = response.json().get("service_item", {})
            
            return {
                "id": item["id"],
                "name": item["name"],
                "description": item.get("short_description", ""),
                "long_description": item.get("description", ""),
                "category_id": item.get("category_id"),
                "category_name": item.get("category_name", ""),
                "cost": item.get("cost", 0),
                "delivery_time": item.get("delivery_time"),
                "custom_fields": item.get("custom_fields", []),  # Field definitions
                "icon_url": item.get("icon_url"),
                "create_child_ticket": item.get("create_child_ticket", False),
                "child_ticket_config": item.get("child_ticket_config", {})
            }
        except requests.RequestException as e:
            logging.error(f"Error getting service item #{item_id}: {e}")
            raise ValueError(f"Failed to get service item: {str(e)}")

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def create_service_request(
        self,
        service_item_id: int,
        requester_email: str,
        quantity: int = 1,
        requested_for_email: Optional[str] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
        child_tickets: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Submit a service request from the catalog.
        
        This creates a ticket using the service item's predefined workflow,
        which may include:
        - Automatic approval routing
        - Asset provisioning
        - Sub-task creation
        - Integration with external systems
        
        Args:
            service_item_id: The service catalog item ID
            requester_email: Email of person requesting
            quantity: Number of items requested (default 1)
            requested_for_email: Email of person receiving (if different from requester)
            custom_fields: Dictionary of custom field values specific to this item
            child_tickets: Optional list of child ticket configurations
            
        Returns:
            Dictionary with service_request_id, ticket_id, approval_status
            
        Raises:
            ValueError: If request creation fails or invalid parameters
        """
        self._ensure_configured()
        
        if not requester_email or quantity < 1:
            raise ValueError("requester_email is required and quantity must be >= 1")
        
        url = f"{self.base_url}/service_catalog/items/{service_item_id}/place_request"
        
        payload = {
            "email": requester_email,
            "quantity": quantity
        }
        
        if requested_for_email:
            payload["requested_for"] = requested_for_email
        
        if custom_fields:
            payload["custom_fields"] = custom_fields
        
        if child_tickets:
            payload["child_tickets"] = child_tickets
        
        try:
            response = requests.post(
                url,
                auth=self._get_auth(),
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )
            
            if response.status_code == 404:
                raise ValueError(f"Service item #{service_item_id} not found")
            
            response.raise_for_status()
            
            data = response.json()
            service_request = data.get("service_request", {})
            
            return {
                "service_request_id": service_request.get("id"),
                "ticket_id": service_request.get("ticket_id"),
                "display_id": service_request.get("display_id"),
                "quantity": service_request.get("quantity", quantity),
                "stage": service_request.get("stage"),  # requested, submitted, fulfilled, etc.
                "approval_status": service_request.get("approval_status"),  # pending, approved, rejected
                "requester_email": requester_email,
                "created_at": service_request.get("created_at")
            }
        except requests.RequestException as e:
            logging.error(f"Error creating service request for item #{service_item_id}: {e}")
            raise ValueError(f"Failed to create service request: {str(e)}")

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def list_service_categories(self) -> List[Dict[str, Any]]:
        """
        List all service catalog categories.
        
        Categories organize service items (e.g., "Hardware", "Software", "Access Management").
        
        Returns:
            List of category dictionaries with id and name
            
        Raises:
            ValueError: If retrieval fails
        """
        self._ensure_configured()
        
        url = f"{self.base_url}/service_catalog/items/categories"
        
        try:
            response = requests.get(
                url,
                auth=self._get_auth(),
                headers=self._get_headers(),
                timeout=10
            )
            response.raise_for_status()
            
            categories = response.json().get("categories", [])
            
            return [
                {
                    "id": cat["id"],
                    "name": cat["name"],
                    "description": cat.get("description", ""),
                    "position": cat.get("position", 0)
                }
                for cat in categories
            ]
        except requests.RequestException as e:
            logging.error(f"Error listing service categories: {e}")
            raise ValueError(f"Failed to list service categories: {str(e)}")

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def get_service_request_status(
        self,
        service_request_id: int
    ) -> Dict[str, Any]:
        """
        Get the status of a service request.
        
        Useful for tracking approval and fulfillment progress.
        
        Args:
            service_request_id: The service request ID
            
        Returns:
            Dictionary with current stage, approval status, and progress
            
        Raises:
            ValueError: If request not found or retrieval fails
        """
        self._ensure_configured()
        
        url = f"{self.base_url}/service_catalog/requested_items/{service_request_id}"
        
        try:
            response = requests.get(
                url,
                auth=self._get_auth(),
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 404:
                raise ValueError(f"Service request #{service_request_id} not found")
            
            response.raise_for_status()
            
            sr = response.json().get("service_request", {})
            
            return {
                "service_request_id": sr["id"],
                "ticket_id": sr.get("ticket_id"),
                "display_id": sr.get("display_id"),
                "stage": sr.get("stage"),  # requested, submitted, fulfilled, cancelled
                "approval_status": sr.get("approval_status"),  # pending, approved, rejected
                "quantity": sr.get("quantity"),
                "cost": sr.get("cost"),
                "requester_id": sr.get("requester_id"),
                "created_at": sr.get("created_at"),
                "updated_at": sr.get("updated_at")
            }
        except requests.RequestException as e:
            logging.error(f"Error getting service request status #{service_request_id}: {e}")
            raise ValueError(f"Failed to get service request status: {str(e)}")
