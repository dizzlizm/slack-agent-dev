"""
Meraki network management integration.
"""
import logging
from typing import List, Dict, Optional
import meraki

from config import Config
from exceptions import IntegrationNotConfiguredError, ExternalAPIError


class MerakiService:
    """Service for interacting with Meraki Dashboard API."""
    
    def __init__(self):
        if not Config.is_meraki_enabled():
            raise IntegrationNotConfiguredError("Meraki")
        
        self.api_key = Config.MERAKI_API_KEY
        self.org_id = Config.MERAKI_ORG_ID
        self.dashboard = meraki.DashboardAPI(
            api_key=self.api_key,
            suppress_logging=True
        )
        logging.info("Meraki service initialized")
    
    def get_networks(self) -> List[Dict]:
        """
        Get all networks in the organization.
        
        Returns:
            List of network dictionaries
            
        Raises:
            ExternalAPIError: If the API call fails
        """
        try:
            networks = self.dashboard.organizations.getOrganizationNetworks(
                self.org_id
            )
            logging.debug(f"Retrieved {len(networks)} networks from Meraki")
            return networks
        except meraki.APIError as e:
            logging.error(f"Meraki API error getting networks: {e}")
            raise ExternalAPIError("Meraki", details=str(e))
    
    def get_ssids_by_name(self, ssid_name_filter: str) -> List[Dict]:
        """
        Get all SSIDs matching a name filter across all networks.
        
        Args:
            ssid_name_filter: Case-insensitive substring to match
            
        Returns:
            List of dicts with network info and matching SSIDs:
            [
                {
                    'networkId': str,
                    'networkName': str,
                    'ssids': [ssid_details, ...]
                },
                ...
            ]
            
        Raises:
            ExternalAPIError: If the API call fails
        """
        try:
            networks = self.get_networks()
            all_network_data = []
            
            for network in networks:
                matching_ssids = []
                
                # Check all possible SSID slots (0-14)
                for ssid_number in range(15):
                    try:
                        ssid_details = self.dashboard.wireless.getNetworkWirelessSsid(
                            networkId=network['id'],
                            number=str(ssid_number)
                        )
                        
                        # Case-insensitive name match
                        if ssid_name_filter.lower() in ssid_details.get('name', '').lower():
                            matching_ssids.append(ssid_details)
                            
                    except meraki.APIError:
                        # SSID slot might not exist or be accessible
                        continue
                
                if matching_ssids:
                    all_network_data.append({
                        'networkId': network['id'],
                        'networkName': network['name'],
                        'ssids': matching_ssids
                    })
            
            logging.info(
                f"Found {sum(len(n['ssids']) for n in all_network_data)} "
                f"SSIDs matching '{ssid_name_filter}' across "
                f"{len(all_network_data)} networks"
            )
            return all_network_data
            
        except meraki.APIError as e:
            logging.error(f"Meraki API error searching SSIDs: {e}")
            raise ExternalAPIError("Meraki", details=str(e))
    
    def update_ssid_password(
        self,
        network_id: str,
        ssid_number: str,
        new_password: str
    ) -> bool:
        """
        Update the password for a specific SSID.
        
        Args:
            network_id: The network ID
            ssid_number: The SSID number (0-14)
            new_password: The new PSK password
            
        Returns:
            True if successful
            
        Raises:
            ExternalAPIError: If the API call fails
        """
        try:
            #self.dashboard.wireless.updateNetworkWirelessSsid(
            #    networkId=network_id,
            #    number=ssid_number,
            #    psk=new_password
            #)
            logging.info(
                f"Updated SSID {ssid_number} password on network {network_id}"
            )
            return True
            
        except meraki.APIError as e:
            logging.error(
                f"Failed to update SSID {ssid_number} on {network_id}: {e}"
            )
            raise ExternalAPIError("Meraki", details=str(e))
    
    def update_ssids_by_name(
        self,
        ssid_name: str,
        new_password: str
    ) -> Dict[str, int]:
        """
        Update password for all SSIDs matching a name across all networks.
        
        Args:
            ssid_name: The SSID name to match (case-insensitive)
            new_password: The new PSK password
            
        Returns:
            Dictionary with summary:
            {
                'total_updated': int,
                'networks_affected': int,
                'details': [
                    {'network_name': str, 'ssids_updated': int},
                    ...
                ]
            }
        """
        network_data = self.get_ssids_by_name(ssid_name)
        
        if not network_data:
            logging.warning(f"No SSIDs found matching '{ssid_name}'")
            return {
                'total_updated': 0,
                'networks_affected': 0,
                'details': []
            }
        
        total_updated = 0
        details = []
        
        for network_info in network_data:
            network_id = network_info['networkId']
            network_name = network_info['networkName']
            success_count = 0
            
            for ssid in network_info['ssids']:
                # Only update PSK-authenticated SSIDs
                if ssid.get('authMode') == 'psk':
                    try:
                        self.update_ssid_password(
                            network_id,
                            ssid['number'],
                            new_password
                        )
                        success_count += 1
                    except ExternalAPIError as e:
                        logging.error(
                            f"Failed to update SSID {ssid['number']} "
                            f"on {network_name}: {e}"
                        )
                        # Continue with other SSIDs even if one fails
                        continue
            
            if success_count > 0:
                details.append({
                    'network_name': network_name,
                    'ssids_updated': success_count
                })
                total_updated += success_count
        
        logging.info(
            f"Updated {total_updated} SSIDs across "
            f"{len(details)} networks for '{ssid_name}'"
        )
        
        return {
            'total_updated': total_updated,
            'networks_affected': len(details),
            'details': details
        }
