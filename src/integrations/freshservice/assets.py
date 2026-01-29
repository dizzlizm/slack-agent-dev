"""
Freshservice asset-related operations.
"""
import logging
from typing import Dict, List, Any
import requests

from .client import FreshserviceClient
from src.integrations.base_tools import retry_on_failure


class AssetOperations(FreshserviceClient):
    """Handles asset operations in Freshservice."""

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def list_assets(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Lists assets assigned to a specific user.

        Args:
            user_id: The numeric ID of the user

        Returns:
            List of comprehensive asset dictionaries with all available fields

        Raises:
            ValueError: If configuration missing
        """
        self._ensure_configured()

        # Include type_fields to get serial_number and other custom fields
        url = f'{self.base_url}/assets?filter="user_id:{user_id}"&include=type_fields'

        try:
            response = requests.get(
                url, auth=self._get_auth(), headers=self._get_headers(), timeout=10
            )
            response.raise_for_status()

            assets = response.json().get("assets", [])

            return [
                {
                    # Core identification
                    "id": a["id"],
                    "name": a["name"],
                    "display_id": a.get("display_id"),
                    "asset_tag": a.get("asset_tag"),
                    # Product information (from type_fields and direct fields)
                    "serial_number": a.get("type_fields", {}).get("serial_number")
                    or a.get("serial_number"),
                    "product_name": a.get("type_fields", {}).get("product_name")
                    or a.get("product_name"),
                    "manufacturer": a.get("type_fields", {}).get("manufacturer")
                    or a.get("manufacturer"),
                    "model": a.get("type_fields", {}).get("model") or a.get("model"),
                    "description": a.get("description"),
                    # Type and classification
                    "asset_type_id": a.get("asset_type_id"),
                    "impact": a.get("impact"),
                    "usage_type": a.get("usage_type"),
                    # Assignment and location
                    "user_id": a.get("user_id"),
                    "location_id": a.get("location_id"),
                    "department_id": a.get("department_id"),
                    "assigned_on": a.get("assigned_on"),
                    # Status and lifecycle
                    "asset_state": a.get("asset_state"),
                    "acquisition_date": a.get("acquisition_date"),
                    "warranty_expiry_date": a.get("warranty_expiry_date"),
                    "last_audit_date": a.get("last_audit_date"),
                    # Metadata
                    "created_at": a.get("created_at"),
                    "updated_at": a.get("updated_at"),
                    # Include all type_fields for reference
                    "type_fields": a.get("type_fields", {}),
                }
                for a in assets
            ]
        except requests.RequestException as e:
            logging.error(f"Error listing assets: {e}")
            # Return empty list instead of failing (assets might not be enabled)
            return []

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def get_asset_by_id(self, asset_id: int) -> Dict[str, Any]:
        """
        Get a specific asset by its ID.

        Args:
            asset_id: The numeric asset ID

        Returns:
            Dictionary with comprehensive asset details

        Raises:
            ValueError: If asset not found or configuration missing
        """
        self._ensure_configured()

        # Include type_fields to get serial_number and other custom fields
        url = f"{self.base_url}/assets/{asset_id}?include=type_fields"

        try:
            response = requests.get(
                url, auth=self._get_auth(), headers=self._get_headers(), timeout=10
            )

            if response.status_code == 404:
                raise ValueError(f"Asset #{asset_id} not found")

            response.raise_for_status()

            asset = response.json().get("asset", {})

            return {
                # Core identification
                "id": asset["id"],
                "name": asset["name"],
                "display_id": asset.get("display_id"),
                "asset_tag": asset.get("asset_tag"),
                # Product information (from type_fields and direct fields)
                "serial_number": asset.get("type_fields", {}).get("serial_number")
                or asset.get("serial_number"),
                "product_name": asset.get("type_fields", {}).get("product_name")
                or asset.get("product_name"),
                "manufacturer": asset.get("type_fields", {}).get("manufacturer")
                or asset.get("manufacturer"),
                "model": asset.get("type_fields", {}).get("model")
                or asset.get("model"),
                "description": asset.get("description"),
                # Type and classification
                "asset_type_id": asset.get("asset_type_id"),
                "impact": asset.get("impact"),
                "usage_type": asset.get("usage_type"),
                # Assignment and location
                "user_id": asset.get("user_id"),
                "location_id": asset.get("location_id"),
                "department_id": asset.get("department_id"),
                "assigned_on": asset.get("assigned_on"),
                # Status and lifecycle
                "asset_state": asset.get("asset_state"),
                "acquisition_date": asset.get("acquisition_date"),
                "warranty_expiry_date": asset.get("warranty_expiry_date"),
                "last_audit_date": asset.get("last_audit_date"),
                # Metadata
                "created_at": asset.get("created_at"),
                "updated_at": asset.get("updated_at"),
                "author_type": asset.get("author_type"),
                # Include all type_fields for reference
                "type_fields": asset.get("type_fields", {}),
            }
        except requests.RequestException as e:
            logging.error(f"Error getting asset #{asset_id}: {e}")
            raise ValueError(f"Failed to get asset: {str(e)}")
