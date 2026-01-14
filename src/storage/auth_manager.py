"""
Authorization management using DynamoDB.
"""
import logging
import time
from typing import Optional, Set

from src.config import Config
from src.exceptions import AuthorizationError, StorageError


class AuthorizationManager:
    """Manages user authorization using DynamoDB with TTL-based cache."""

    def __init__(self, table=None):
        """
        Initialize the authorization manager.

        Args:
            table: DynamoDB table resource (optional, will create if not provided)
        """
        self._table = table
        self._cache: Set[str] = set()
        self._cache_loaded = False
        self._cache_timestamp: Optional[float] = None

    @property
    def table(self):
        """Lazy-load DynamoDB table."""
        if self._table is None:
            import boto3
            dynamodb = boto3.resource('dynamodb', region_name=Config.AWS_REGION)
            table_name = Config.get_table_name('AuthorizedUsers')
            self._table = dynamodb.Table(table_name)
        return self._table

    def _is_cache_stale(self) -> bool:
        """Check if the cache has expired and needs refresh."""
        if not self._cache_loaded or self._cache_timestamp is None:
            return True
        return (time.time() - self._cache_timestamp) > Config.AUTH_CACHE_TTL_SECONDS

    def _load_cache(self, force: bool = False) -> None:
        """
        Load all authorized users into memory cache.

        Args:
            force: If True, refresh cache even if not stale
        """
        if not force and self._cache_loaded and not self._is_cache_stale():
            return

        try:
            response = self.table.scan(
                ProjectionExpression='SK'
            )
            self._cache = {
                item['SK'].replace('USER#', '')
                for item in response.get('Items', [])
                if item.get('SK', '').startswith('USER#')
            }
            self._cache_loaded = True
            self._cache_timestamp = time.time()
            logging.info(f"Loaded {len(self._cache)} authorized users into cache")
        except Exception as e:
            logging.error(f"Failed to load authorization cache: {e}")

    def is_authorized(self, user_id: str) -> bool:
        """
        Check if a user is authorized.

        Args:
            user_id: The Slack user ID to check

        Returns:
            True if the user is authorized, False otherwise
        """
        # Refresh cache if stale
        if self._is_cache_stale():
            self._load_cache(force=True)

        # Check cache first
        if self._cache_loaded and user_id in self._cache:
            logging.debug(f"Authorization check PASSED (cached) for user {user_id}")
            return True

        # Fall back to direct lookup
        try:
            response = self.table.get_item(
                Key={
                    'PK': 'AUTH',
                    'SK': f'USER#{user_id}'
                }
            )
            if 'Item' in response:
                self._cache.add(user_id)
                logging.info(f"Authorization check PASSED for user {user_id}")
                return True

            logging.warning(f"Authorization check FAILED for user {user_id}")
            return False

        except Exception as e:
            logging.error(f"Error checking authorization: {e}")
            return False  # Fail closed for security

    def require_authorization(self, user_id: str) -> None:
        """
        Require that a user is authorized.

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
        """
        try:
            self.table.put_item(
                Item={
                    'PK': 'AUTH',
                    'SK': f'USER#{user_id}',
                    'UserID': user_id,
                    'AddedAt': int(time.time())
                }
            )
            self._cache.add(user_id)
            logging.info(f"Added user {user_id} to authorized list")
        except Exception as e:
            logging.error(f"Failed to add user {user_id}: {e}")
            raise StorageError("add_user", str(e))

    def remove_user(self, user_id: str) -> None:
        """
        Remove a user from the authorized list.

        Args:
            user_id: The Slack user ID to deauthorize
        """
        try:
            self.table.delete_item(
                Key={
                    'PK': 'AUTH',
                    'SK': f'USER#{user_id}'
                }
            )
            self._cache.discard(user_id)
            logging.info(f"Removed user {user_id} from authorized list")
        except Exception as e:
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
