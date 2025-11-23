"""
Authorization management for the Slack bot.
"""
import logging
from typing import Set
from azure.data.tables import TableClient, TableEntity
from azure.core.exceptions import ResourceNotFoundError, AzureError

from exceptions import AuthorizationError, StorageError


class AuthorizationManager:
    """Manages user authorization using Azure Table Storage."""
    
    def __init__(self, table_client: TableClient):
        self.table_client = table_client
        self._cache: Set[str] = set()
        self._cache_loaded = False
        
    def _load_cache(self) -> None:
        """Load all authorized users into memory cache."""
        if self._cache_loaded:
            return
        
        try:
            entities = self.table_client.list_entities()
            self._cache = {entity.get("RowKey") for entity in entities}
            self._cache_loaded = True
            logging.info(f"Loaded {len(self._cache)} authorized users into cache")
        except AzureError as e:
            logging.error(f"Failed to load authorization cache: {e}")
            # Continue with empty cache - will fall back to direct lookups
    
    def is_authorized(self, user_id: str) -> bool:
        """
        Check if a user is authorized.
        
        Args:
            user_id: The Slack user ID to check
            
        Returns:
            True if the user is authorized, False otherwise
        """
        # Check cache first
        if self._cache_loaded and user_id in self._cache:
            logging.debug(f"Authorization check PASSED (cached) for user {user_id}")
            return True
        
        # Fall back to direct lookup
        try:
            self.table_client.get_entity(partition_key="SlackUser", row_key=user_id)
            # Update cache
            self._cache.add(user_id)
            logging.info(f"Authorization check PASSED for user {user_id}")
            return True
        except ResourceNotFoundError:
            logging.warning(f"Authorization check FAILED for user {user_id}")
            return False
        except AzureError as e:
            logging.error(f"Error checking authorization for {user_id}: {e}")
            # Fail open or closed? Let's fail closed for security
            return False
    
    def require_authorization(self, user_id: str) -> None:
        """
        Require that a user is authorized, raising an exception if not.
        
        Args:
            user_id: The Slack user ID to check
            
        Raises:
            AuthorizationError: If the user is not authorized
        """
        if not self.is_authorized(user_id):
            raise AuthorizationError(user_id)
    
    def add_user(self, user_id: str) -> None:
        """
        Add a user to the authorized list.
        
        Args:
            user_id: The Slack user ID to authorize
            
        Raises:
            StorageError: If the operation fails
        """
        try:
            entity = TableEntity(PartitionKey="SlackUser", RowKey=user_id)
            self.table_client.upsert_entity(entity)
            self._cache.add(user_id)
            logging.info(f"Successfully added user {user_id} to authorized list")
        except AzureError as e:
            logging.error(f"Failed to add user {user_id}: {e}")
            raise StorageError("add_user", str(e))
    
    def remove_user(self, user_id: str) -> None:
        """
        Remove a user from the authorized list.
        
        Args:
            user_id: The Slack user ID to deauthorize
            
        Raises:
            StorageError: If the operation fails
        """
        try:
            self.table_client.delete_entity(partition_key="SlackUser", row_key=user_id)
            self._cache.discard(user_id)
            logging.info(f"Successfully removed user {user_id} from authorized list")
        except ResourceNotFoundError:
            logging.warning(f"User {user_id} was not in authorized list")
            # Not really an error - already removed
        except AzureError as e:
            logging.error(f"Failed to remove user {user_id}: {e}")
            raise StorageError("remove_user", str(e))
    
    def list_authorized_users(self) -> Set[str]:
        """
        Get a set of all authorized user IDs.
        
        Returns:
            Set of authorized user IDs
        """
        self._load_cache()
        return self._cache.copy()
