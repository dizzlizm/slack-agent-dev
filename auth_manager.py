"""
Authorization management for the Slack bot.
"""
import logging
import time
from typing import Set, Optional
from azure.data.tables import TableClient, TableEntity
from azure.core.exceptions import ResourceNotFoundError, AzureError

from exceptions import AuthorizationError, StorageError


class AuthorizationManager:
    """Manages user authorization using Azure Table Storage with TTL-based cache."""

    # Cache TTL in seconds (5 minutes)
    CACHE_TTL_SECONDS = 300

    def __init__(self, table_client: TableClient):
        self.table_client = table_client
        self._cache: Set[str] = set()
        self._cache_loaded = False
        self._cache_timestamp: Optional[float] = None

    def _is_cache_stale(self) -> bool:
        """Check if the cache has expired and needs refresh."""
        if not self._cache_loaded or self._cache_timestamp is None:
            return True
        return (time.time() - self._cache_timestamp) > self.CACHE_TTL_SECONDS

    def _load_cache(self, force: bool = False) -> None:
        """
        Load all authorized users into memory cache.

        Args:
            force: If True, refresh cache even if not stale
        """
        if not force and self._cache_loaded and not self._is_cache_stale():
            return

        try:
            entities = self.table_client.list_entities()
            self._cache = {entity.get("RowKey") for entity in entities}
            self._cache_loaded = True
            self._cache_timestamp = time.time()
            logging.info(f"Loaded {len(self._cache)} authorized users into cache (TTL: {self.CACHE_TTL_SECONDS}s)")
        except AzureError as e:
            logging.error(f"Failed to load authorization cache: {e}")
            # Continue with existing cache if available, otherwise empty
    
    def is_authorized(self, user_id: str) -> bool:
        """
        Check if a user is authorized.

        Args:
            user_id: The Slack user ID to check

        Returns:
            True if the user is authorized, False otherwise
        """
        # Refresh cache if stale (handles removed users)
        if self._is_cache_stale():
            self._load_cache(force=True)

        # Check cache first
        if self._cache_loaded and user_id in self._cache:
            logging.debug(f"Authorization check PASSED (cached) for user {user_id}")
            return True

        # Fall back to direct lookup (for users added after cache load)
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
