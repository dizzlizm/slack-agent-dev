"""
Intune device management integration.
"""
import logging
import requests

from config import Config
from exceptions import IntegrationNotConfiguredError, ExternalAPIError


class IntuneService:
    """Service for interacting with Intune webhook for device management."""
    
    def __init__(self):
        if not Config.is_intune_enabled():
            raise IntegrationNotConfiguredError("Intune")
        
        self.webhook_url = Config.INTUNE_REBOOT_WEBHOOK_URL
        logging.info("Intune service initialized")
    
    def reboot_device(self, serial_number: str) -> tuple[bool, str]:
        """
        Send a reboot command to a device via Intune webhook.
        
        Args:
            serial_number: The device serial number
            
        Returns:
            Tuple of (success: bool, message: str)
            
        Raises:
            ExternalAPIError: If the API call fails critically
        """
        # Note: Original implementation used URL parameter
        # Adjust if your webhook expects a different format
        url = f"{self.webhook_url}&serialNumber={serial_number}"
        
        try:
            response = requests.post(
                url,
                timeout=120  # Intune operations can take time
            )
            
            if response.status_code == 200:
                logging.info(f"Successfully sent reboot command for {serial_number}")
                return True, response.text
            else:
                logging.error(
                    f"Intune webhook error (Status {response.status_code}): {response.text}"
                )
                return False, f"Error (Status {response.status_code}): {response.text}"
                
        except requests.exceptions.Timeout:
            logging.error(f"Intune webhook timeout for {serial_number}")
            raise ExternalAPIError("Intune", details="Request timed out after 120 seconds")
        except requests.exceptions.RequestException as e:
            logging.error(f"Intune webhook request failed: {e}")
            raise ExternalAPIError("Intune", details=str(e))
